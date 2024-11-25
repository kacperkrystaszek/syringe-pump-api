import socket
import time


def test_bad_arg():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        data = sock.recv(1024)
        sock.sendall("start COM1!".encode())
        data = sock.recv(1024)
        sock.sendall("pump COM1 DRUG_LIB^100!".encode())
        data = sock.recv(1024)
        print(data.decode())
        
test_bad_arg()