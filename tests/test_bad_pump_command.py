import socket
import time


def test_bad_pump_command():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        data = sock.recv(1024)
        sock.sendall("start COM1!".encode())
        data = sock.recv(1024)
        sock.sendall("pump COM1 NON_EXISTENT_COMMAND_IN_CONFIG!".encode())
        data = sock.recv(1024)
        print(data.decode())
    
    
test_bad_pump_command()