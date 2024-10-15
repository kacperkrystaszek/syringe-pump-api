import json
import serial
from crc import Calculator, Configuration


class ArgumentError(Exception):
    pass

class CommandError(Exception):
    pass

class PumpHandler:
    SERIAL_NUMBER = "1231-32423"
    def __init__(self, port: str) -> None:
        self.pump = serial.Serial(
            port=port,
            baudrate=9600,
            parity="N",
            stopbits=1,
            bytesize=8,
            timeout=2
        )
        self.calculator = Calculator(self._get_crc_config())
        self._commands = self._get_commands()
        
    def _get_commands(self):
        commands = None
        with open("command_list.json", "r", encoding="utf-8") as file:
            commands = json.load(file)
        return commands
        
    def _get_crc_config(self) -> Configuration:
        return Configuration(
            width=16,
            polynomial=0x11021,
            init_value=0xFFFF,
            final_xor_value=0x0000,
            reverse_input=False,
            reverse_output=False
        )
        
    def convert_to_hex(self, not_converted_message: str) -> str:
        message_to_sent = []
        for char in not_converted_message:
            message_to_sent.append(str(hex(ord(char)).lstrip("0x")).upper())
        message_to_sent.append("0D")
        return " ".join(message_to_sent)
    
    def _check_command_correctness(self, command: str, *args) -> None:
        if command not in self._commands:
            raise CommandError("Command doesn't exist")
        available_arguments = self._commands[command]['arguments']
        if available_arguments is None or len(available_arguments) == 0:
            return
        if len(available_arguments) != len(args):
            raise ArgumentError("Not enough arguments passed")
        for available_arg, passed_arg in zip(available_arguments, args):
            arg_name, values = available_arg
            if "float" == values:
                try:
                    float(passed_arg)
                except ValueError:
                    raise ArgumentError(f"Wrong argument ({passed_arg}) passed to float conversion")
            elif "int" == values:
                try:
                    int(passed_arg)
                except ValueError:
                    raise ArgumentError(f"Wrong argument ({passed_arg}) passed to int conversion")
            else:
                if passed_arg not in values:
                    raise ArgumentError(f"Wrong argument passed ({passed_arg}); Available args {values}")
        
    def _construct_command(self, command: str, *args) -> str:
        message_to_server: str = self._commands[command]["messageToServer"]
        parts_of_command = message_to_server.split("^")
        arguments = parts_of_command[1:]
        
        for passed_arg, arg_alias in zip(args, arguments):
            message_to_server = message_to_server.replace(arg_alias, str(passed_arg))
            
        return message_to_server        
        ''
    def send_message(self, command: str, *args) -> None:
        try:
            self._check_command_correctness(command, *args)
        except (ArgumentError, CommandError) as exc:
            return str(exc)
        command_to_sent = self._construct_command(command, *args)
        frame_check_sequence = self.calculator.checksum(self.SERIAL_NUMBER.encode())
        not_converted_message = f"!{command_to_sent}|{frame_check_sequence}"
        message_to_sent = self.convert_to_hex(not_converted_message).encode()
        print(f"SENT: {message_to_sent}")
        self.pump.write(message_to_sent)
        # response = self.pump.read_until("0D".encode())
        response = "response"
        return response