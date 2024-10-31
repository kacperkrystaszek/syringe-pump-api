import socket
import re
import subprocess
import sys
import time

from serial import SerialException

from loopback import Loopback
from pump import PumpHandler


class Server:
    SERVER_IP = "localhost"
    PORT = 4000
    STARTPUMP = re.compile(r"start (?P<port>\S+)")
    COMMAND = re.compile(r"pump (?P<port>\S+) (?P<command>[A-Z0-9\_]+)(?P<args>\s.+)?")
    CLOSEPUMP = re.compile(r"stop (?P<port>\S+)")
    
    def __init__(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((self.SERVER_IP, self.PORT))
        self._socket.listen()
        self._pumps: dict[str, PumpHandler] = {}
        self.loopback: dict[str, subprocess.Popen] = {}
        
    def run(self) -> None:
        clientsocket, address = self._socket.accept()
        while True:
            message = clientsocket.recv(1024)
            message = message.decode().strip("\n")
            
            if self.STARTPUMP.match(message):
                port = self.STARTPUMP.match(message).group("port")
                try:
                    self.loopback[port] = subprocess.Popen(
                        ["virtualserialports", "-l", "1"], 
                        stdout=sys.stdout, 
                        stderr=sys.stderr
                    )
                    time.sleep(2)
                    self._pumps[port] = PumpHandler(port)
                except SerialException as exc:
                    self.send(clientsocket, str(exc).encode())
                
            elif self.COMMAND.match(message):
                match_object = self.COMMAND.match(message)
                port = match_object.group("port")
                command = match_object.group("command")
                args = match_object.group("args")
                if args is not None:
                    args = args.split()
                else:
                    args = []
                pump_handler = self._pumps.get(port)
                if pump_handler is not None:
                    response = pump_handler.send_message(command, *args)
                    self.send(clientsocket, response)
                else:
                    self.send(clientsocket, "No pump started at this port")
                    continue
            elif self.CLOSEPUMP.match(message):
                port = self.CLOSEPUMP.match(message).group("port")
                pump_handler = self._pumps.get(port)
                loopback = self.loopback.get(port)
                if pump_handler is not None:
                    self._pumps.pop(port)
                if loopback is not None:
                    loopback.kill()
                    self.loopback.pop(port)
                
            else:
                self.send(clientsocket, "Unvalid message")
                continue
            
    def send(self, socket: socket.socket, message: str) -> None:
        socket.send(f"{message}\n".encode())
            
    def close(self) -> None:
        self._socket.close()