import socket
import time


def test_bad_pump_command():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        sock.sendall("start COM1!".encode())
        time.sleep(2)
        sock.sendall("pump COM1 BAD_COMMAND!".encode())
        data = sock.recv(1024)
        print(data.decode())
    
    
test_bad_pump_command()