import logging
from multiprocessing.pool import ThreadPool
import random
import socket
import re
import time
import traceback

import serial

from Loopback import Loopback
from PumpHandler import PumpHandler


class Server:    
    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self.COMMAND_DELIMITER = config['server_config']['command_delimiter']
        self.START_PUMP_COMMAND = re.compile(
            rf"start (?P<port>(\/[a-z]+\/[a-zA-Z0-9]+)|COM\d+){self.COMMAND_DELIMITER}$"
        )
        self.PUMP_COMMAND = re.compile(
            rf"pump (?P<port>(\/[a-z]+\/[a-zA-Z0-9]+)|COM\d+) (?P<command>\S+){self.COMMAND_DELIMITER}$"
        )
        self.CLOSE_PUMP_COMMAND = re.compile(
            rf"close (?P<port>(\/[a-z]+\/[a-zA-Z0-9]+)|COM\d+){self.COMMAND_DELIMITER}$"
        )
        
        self._logger = logger
        self._config = config
        
        self._MAX_PUMPS = config['server_config']['max_pumps']
        self._loopback = config['server_config'].get("loopback", False)
        self._pool = ThreadPool(processes=self._MAX_PUMPS)
        
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((config['server_config']['server_ip'], config['server_config']['port']))
        
        self._pumps: dict[str, PumpHandler] = {}
        self._buffer = b""
        
        self._logger.info("Server initialized")
        
    def handle_start_command(self, clientsocket: socket.socket, match: re.Match) -> None:
        port = match.group("port")
        try:
            if self._pumps.get(port) is not None:
                raise RuntimeError("Pump is already initialized at this port")
            if len(self._pumps) == self._MAX_PUMPS:
                raise ValueError("Max number of pumps if connected.")
            
            if self._loopback:
                time.sleep(random.uniform(0.5, 1))
                port_handler = Loopback(
                    port=port, 
                    crc_config=self._config['pump_config']['crc_config'],
                    command_set=self._config['pump_config']['command_set'], 
                    arguments=self._config['pump_config']['arguments']
                )
            else:
                port_handler = serial.Serial(port=port, **self._config['pump_config']['serial_port_config'])
            
            self._pumps[port] = PumpHandler(
                port=port,
                pump=port_handler,
                crc_config=self._config['pump_config']['crc_config'],
                command_set=self._config['pump_config']['command_set'],
                arguments=self._config['pump_config']['arguments']
            )
            self._pumps[port].start()
            self.send(clientsocket, f"Pump handler started for port {port}")
        except Exception as exc:
            self._logger.error(traceback.print_exc())
            self.send(clientsocket, str(exc), logging.ERROR)
        
    def handle_pump_command(self, clientsocket: socket.socket, match: re.Match, time_signature: int) -> None:
        port = match.group("port")
        command = match.group("command")
        
        pump_handler = self._pumps.get(port)
        if pump_handler is None:
            self.send(clientsocket, "No pump started at this port")
            return
        
        pump_handler.push_message(command, time_signature)
        response = pump_handler.get_response()
        level = logging.ERROR if "ERROR" in response else logging.INFO
        self.send(clientsocket, response, level=level)
        
        if pump_handler.is_killed():
            self.send(clientsocket, "Pump removed from server port mapping.")
            self._pumps.pop(port)
        
    def handle_close_command(self, clientsocket: socket.socket, match: re.Match) -> None:
        port = match.group("port")
        pump_handler = self._pumps.get(port)
        
        if pump_handler is not None:
            pump_handler.close()
            self._pumps.pop(port)
            self.send(clientsocket, f"Pump at port {port} is closed")
        else:
            self.send(clientsocket, f"No pump initialized at port {port}")
        
    def handle_request(self, clientsocket: socket.socket, message: str, time_signature: int) -> None:
        self._logger.info(f"Handling message: {message}")
        
        if self.START_PUMP_COMMAND.match(message):
            match = self.START_PUMP_COMMAND.match(message)
            self.handle_start_command(clientsocket, match)
            
        elif self.PUMP_COMMAND.match(message):
            match = self.PUMP_COMMAND.match(message)
            self.handle_pump_command(clientsocket, match, time_signature)
            
        elif self.CLOSE_PUMP_COMMAND.match(message):
            match = self.CLOSE_PUMP_COMMAND.match(message)
            self.handle_close_command(clientsocket, match)
            
        else:
            self.send(clientsocket, "Unvalid message")
        
    def run(self) -> None:
        self._socket.listen(1)
        clientsocket, address = self._socket.accept()
        ack_message = f"Accepted connection from {address}. Ready to work. \nTo start at port: start PORT(i.e. /dev/ttyUSB0 or COM1)!\nTo send command: pump PORT COMMAND(see config.json)!\nTo close pump: close PORT!\nRemember that '!' is command delimiter"
        self.send(clientsocket, ack_message)
        
        while True:
            message = self.receive(clientsocket)
            if message is None:
                self._logger.info("Connection broken.")
                break
            time_signature = time.time()
            self._pool.apply_async(self.handle_request, [clientsocket, message, time_signature])
            
        self.close()
    
    def receive(self, clientsocket: socket.socket):
        command_delimiter = bytes(f"{self.COMMAND_DELIMITER}", encoding="utf-8")
        
        while command_delimiter not in self._buffer:
            data = clientsocket.recv(1024)
            if not data:
                return None
            self._buffer += data
            
        line, _, self._buffer = self._buffer.partition(command_delimiter)
        return line.decode().strip("\n") + self.COMMAND_DELIMITER
            
    def send(self, clientsocket: socket.socket, message: str, level=logging.INFO) -> None:
        self._logger.log(level, message)
        sent = clientsocket.send(f"{message}\n".encode())
        if sent == 0:
            self._logger.info("Connection broken.")
            self.close()
            
    def close(self) -> None:
        self._logger.info("Closing server")
        for pump in self._pumps.values():
            pump: serial.Serial | Loopback
            pump.close()
        self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()
        self._pool.close()
        