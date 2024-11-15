import logging
import re
import threading
import time
import serial
from crc import Calculator, Configuration

from Loopback import Loopback
from exceptions.ArgumentError import ArgumentError
from exceptions.CommandError import CommandError
from exceptions.CommunicationLostError import ConnectionLostError
from exceptions.ConfigError import ConfigError
from exceptions.NoResponseError import NoResponseError


class PumpHandler:    
    def __init__(self, port: str, pump: serial.Serial | Loopback, crc_config: dict|None, command_set: dict, arguments: dict) -> None:        
        self.pump = pump
        self.logger = logging.getLogger(f"Server.PumpHandler.{port}")
        self.logger.setLevel(logging.DEBUG)
        self._commands = command_set 
        self._arguments = arguments
        self._to_send_queue = []
        self._response_queue = []
        self._thread = threading.Thread(target=self._run, name=port)
        self._kill_thread = False
        
        self._packet_terminator = chr(int("0x0D", 16))
        
        if crc_config is not None:
            self.calculator = Calculator(self._get_crc_config(crc_config))
        else:
            self.calculator = None
        
    def _get_crc_config(self, crc_config: dict[str, int|bool]) -> Configuration:
        return Configuration(**crc_config)
    
    def _translate_to_hex(self, value: str) -> str:
        return str(hex(ord(value)).lstrip("0x")).upper()
    
    def _translate_from_hex(self, value: str) -> str:
        return str(chr(int(f"0x{value}", 16))).upper()
        
    def _create_possible_values(self, argument: str, argument_meta: dict) -> str:
        if isinstance(argument_meta['values'], list):
            return r"|".join(argument_meta['values'])
        
        float_pattern = r"float\((?P<length>\d+)(,(?P<decimal>\d))?\)(,(?P<OffValue>OFF))?"
        int_pattern = r"int\((?P<length>\d+)\)(,(?P<OffValue>OFF))?"
        str_pattern = r"str\((?P<length>\d+)\)(,(?P<OffValue>OFF))?"
        datetime_pattern = r"DateAndTimeStamp"
        date_pattern = r"DateStamp"
        duration_pattern = r"DurationStamp"
        own_re_pattern = r"re\((?P<pattern>.+)\)"
        
        match = re.match(float_pattern, argument_meta['values'])
        if match is not None:
            length = match.group("length")
            decimal = match.groupdict().get("decimal") 
            decimal = decimal if decimal is not None else "1"
            off_value = match.groupdict().get("OffValue") is not None
            result = r"(?=.{1,length}$)\d+\.\d{decimal,}".replace("length", length).replace("decimal", decimal)
            result = rf"{result}|OFF" if off_value else result
            return result
        
        match = re.match(int_pattern, argument_meta['values'])
        if match is not None:
            length = match.group("length")
            off_value = match.groupdict().get("OffValue") is not None
            result = r"\d{1,length}".replace("length", length)
            result = rf"{result}|OFF" if off_value else result
            return result
        
        match = re.match(str_pattern, argument_meta['values'])
        if match is not None:
            length = match.group("length")
            off_value = match.groupdict().get("OffValue") is not None
            result = r"[^\^]{1,length}".replace("length", length)
            result = rf"{result}|OFF" if off_value else result
            return result
        
        match = re.match(datetime_pattern, argument_meta['values'])
        if match is not None:
            return r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        
        match = re.match(date_pattern, argument_meta['values'])
        if match is not None:
            return r'\d{4}-\d{2}-\d{2}'
        
        match = re.match(duration_pattern, argument_meta['values'])
        if match is not None:
            return r'\d{2}:\d{2}:\d{2}|24h\+'
        
        match = re.match(own_re_pattern, argument_meta['values'])
        if match is not None:
            return match.group("pattern")
        
        raise ArgumentError(f"Bad values provided for argument. Must be int(length), float(length,decimal_places), str(max_chars_length), DateAndTimeStamp(ISO 8601), DurationStamp(ISO 8601), DateStamp(ISO 8601), own regex pattern i.e. re(my_pattern) or list. Argument: {argument}")
    
    def _create_pattern(self, command: str) -> str:
        parts = command.split("^")
        
        result = [parts[0]]
        
        for part in parts[1:]:
            if not part.startswith("<") and not part.endswith(">"):
                raise ConfigError(
                    f"Argument badly described in command template in config.json. Should be '<ARGUMENT_NAME>' Command: {command}"
                )
            argument_meta = self._arguments.get(part)
            if argument_meta is None:
                raise ConfigError(
                    f"Provided argument from command is not described in arguments part in config.json. Command: {command}"
                )
            possible_values = self._create_possible_values(part, argument_meta)
            to_add = rf"^{possible_values}$"
            result.append(rf"{to_add}")
        
        return result
    
    def convert_to_hex(self, not_converted_message: str) -> str:
        translated = map(self._translate_to_hex, not_converted_message)
        return "".join(translated)
    
    def convert_from_hex(self, response: str) -> str:
        characters = []
        current = response[0]
        for index, char in enumerate(response[1:], start=1):
            if index % 2 == 0:
                characters.append(current)
                current = char
                continue
            current += char
            
        result = []
        for char in characters:
            result.append(chr(int(f"0x{char}", 16)))
            
        return "".join(result)
    
    def _match_patterns(self, patterns: str, parts: str) -> bool:
        for pattern, part in zip(patterns, parts):
            match = re.match(pattern, part)
            if match is None:
                return False
            
        return True
    
    def validate_command(self, passed_command: str) -> None:
        parts = passed_command.split("^")
        for command in self._commands:
            patterns = self._create_pattern(command)
            if len(parts) != len(patterns):
                continue
            found = self._match_patterns(patterns, parts)
            if found:
                return
            
        raise CommandError(f"Provided command pattern does not exist in config.json. Command: {passed_command}")
        
    def translate_command(self, command: str) -> bytes:
        if self.calculator is not None:
            frame_check_sequence = self.calculator.checksum(command.encode())
        else:
            frame_check_sequence = ""
        return self.convert_to_hex(f"!{command}|{frame_check_sequence}{self._packet_terminator}").encode()
    
    def _checksum_check(self, response: str) -> None:
        parts = response.split("|")
        command = parts[0].lstrip("!")
        
        frame_check_sequence_from_response = parts[-1]
        frame_check_sequence_from_response = frame_check_sequence_from_response.rstrip(self._packet_terminator)
        
        calculated_frame_check = self.calculator.checksum(command.encode())
        
        if calculated_frame_check != int(frame_check_sequence_from_response):
            raise RuntimeError(
                f"Checksum does not expectation.\nResponse: {response}\nExpected: {calculated_frame_check}\nReceived: {frame_check_sequence_from_response}"
            )
            
    def _check_for_escape_command(self, command: str):
        try:
            return ord(command) == int("0x1B", 16)
        except TypeError:
            return False

    def push_message(self, command: str, time_signature: int) -> None:
        self._to_send_queue.append((command, time_signature))
        self._to_send_queue.sort(key=lambda elem: elem[1])
        
    def get_response(self) -> str:
        while len(self._response_queue) == 0:
            ...
        return self._response_queue.pop(0)
    
    def _read_response(self, command_to_sent: str) -> str:
        start_time = time.time()
        response = self.pump.read_until(self._packet_terminator.encode()).decode()
        elapsed = time.time() - start_time
        
        if elapsed >= 3 and not response:
            start_time = time.time()
            self.pump.write(command_to_sent)
            response = self.pump.read_until(self._packet_terminator.encode()).decode()
            elapsed = time.time() - start_time
            if elapsed >= 3 and not response:
                raise ConnectionLostError("Device disconnected")
        elif not response:
            raise NoResponseError("No response from pump")
        
        return response

    def send_message(self, command: str) -> None:
        if self._check_for_escape_command(command):
            self.pump.write(command.encode())
            self._response_queue.append("Escape character sent. Aborting all current actions.")
            return
        self.validate_command(command)        
        
        command_to_sent = self.translate_command(command)
        self.logger.info(f"SENT: {command}")
        self.pump.write(command_to_sent)
        
        response = self._read_response(command_to_sent)
        
        if self._check_for_escape_command(response):
            self._response_queue.append("ACK: ESCAPE COMMAND RECEIVED")
            return
        
        converted_response = self.convert_from_hex(response)
        response_to_sent = converted_response.split("|")[0].lstrip("!")
        
        if self.calculator is not None:
            self._checksum_check(converted_response)
        response = f"ACK: {response_to_sent}"
        
        self._response_queue.append(response)
    
    def close(self):
        self.pump.close()
        self._kill_thread = True
        
    def start(self):
        self._thread.start()
        
    def is_killed(self):
        return self._kill_thread
        
    def _run(self):
        while True:
            if self._kill_thread:
                return
            if len(self._to_send_queue) == 0:
                continue
            try:
                self.send_message(self._to_send_queue.pop(0)[0])
            except (RuntimeError, ArgumentError, CommandError, ConfigError) as exc:
                self._response_queue.append("ERROR: " + str(exc))
            except ConnectionLostError as exc:
                self._kill_thread = True
                self._response_queue.append("ERROR: " + str(exc))
            except NoResponseError as exc:
                self._response_queue.append("ERROR: " + str(exc))
        