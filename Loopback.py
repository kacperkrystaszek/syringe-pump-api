import random
import string
import time

from crc import Calculator, Configuration


class Loopback:
    def __init__(self, port: str, command_set: dict, arguments: dict, crc_config: dict|None):
        self._port = port
        self._commands = command_set
        self._arguments = arguments
        self._parameters = {}
        
        self._packet_terminator = "0D"
        self._response = self._set_default_response()
        
        if crc_config is not None:
            self.calculator = Calculator(self._get_crc_config(crc_config))
        else:
            self.calculator = None
            
    def _set_default_response(self):
        return bytes(self._packet_terminator, encoding="utf-8")
        
    def _get_crc_config(self, crc_config: dict[str, int|bool]) -> Configuration:
        return Configuration(**crc_config)
    
    def _checksum_check(self, message: str) -> None:
        parts = message.split("|")
        command = parts[0].lstrip("!")
        
        frame_check_sequence_from_response = parts[-1]
        frame_check_sequence_from_response = frame_check_sequence_from_response.rstrip(self._packet_terminator)
        
        calculated_frame_check = self.calculator.checksum(command.encode())
        
        if calculated_frame_check != int(frame_check_sequence_from_response):
            raise RuntimeError(
                f"Checksums does not match.\nResponse: {message}\nExpected: {calculated_frame_check}\nReceived: {frame_check_sequence_from_response}"
            )
    
    def write(self, message: bytes) -> bytes:
        decoded_message = message.decode()
        converted_command = self.convert_from_hex(decoded_message)
        
        if self.calculator is not None:
            self._checksum_check(converted_command)
        
        command = converted_command.split("|")[0].lstrip("!")
        splitted = command.split("^")
        main_part = splitted[0]
        parameters = splitted[1:]
        caret_count = converted_command.count("^")
        
        response = None
        
        for command_from_config, description in self._commands.items():
            if not (main_part in command_from_config and command_from_config.count("^") == caret_count):
                continue
            response: str = description['response']
            arguments = command_from_config.split("^")[1:]
            for argument, received in zip(arguments, parameters):
                self._parameters[argument] = received
            if response == command_from_config:
                self._response = message
                return
            break
        
        arguments = response.split("^")[1:]
        
        for argument in arguments:
            replacement = None
            saved_parameter = self._parameters.get(argument)
            
            if saved_parameter is not None:
                replacement = saved_parameter
            else:
                arg_from_config: dict = self._arguments.get(argument)
                replacement = self._create_random_replacement(arg_from_config)
                
            response = response.replace(argument, replacement)
            
        frame_check_sequence = self.calculator.checksum(response.encode()) if self.calculator is not None else ""
        
        self._response = bytes(
            self.convert_to_hex(f"!{response}|{frame_check_sequence}")+self._packet_terminator,
            encoding="utf-8"
        )

    def _create_random_replacement(self, arg_from_config: dict):
        if "float" in arg_from_config['values']:
            replacement = str(random.uniform(1.0, 10.0))[:6]
        elif "int" in arg_from_config['values']:
            max_value = int(arg_from_config['values'].split("(")[-1].rstrip(")"))
            replacement = str(random.randint(1, 10**max_value))
        elif isinstance(arg_from_config['values'], list):
            replacement = random.choice(arg_from_config['values'])
        elif "str" in arg_from_config['values']:
            max_length = int(arg_from_config['values'].split("(")[-1].rstrip(")"))
            replacement = "".join(
                        random.choice(
                            string.ascii_lowercase + string.ascii_uppercase + string.digits
                        ) for _ in range(random.randint(1, max_length))
                    )
        elif "DateAndTimeStamp" in arg_from_config['values']:
            year = 2024
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            replacement = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
        elif "DateStamp" in arg_from_config['values']:
            year = 2024
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            replacement = f"{year}-{month}-{day}"
        elif "DurationStamp" in arg_from_config['values']:
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            replacement = f"{hour}:{minute}:{second}"
        else:
            replacement = ""
        return replacement
        
    def _translate_to_hex(self, value: str) -> str:
        return str(hex(ord(value)).lstrip("0x")).upper()
    
    def _translate_from_hex(self, value: str) -> str:
        return str(chr(int(f"0x{value}", 16))).upper()
    
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
        
    def read_until(self, _):
        try:
            rand = random.randint(1, 50)
            if rand == 1:
                return bytes("", encoding="utf-8")
            elif rand == 2:
                return bytes(chr(int("0x1B", 16)), encoding="utf-8")
            elif rand == 3:
                time.sleep(3.1)
                return bytes("", encoding="utf-8")
            time.sleep(random.uniform(0.2, 0.5))
            return self._response
        finally:
            self._response = self._set_default_response()
            
    def cancel_read(self):
        ...
    
    def close(self) -> None:
        ...
        