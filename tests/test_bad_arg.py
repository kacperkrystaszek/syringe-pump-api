import socket
import time


def test_bad_arg():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        sock.sendall("start COM1!".encode())
        time.sleep(2)
        sock.sendall("pump COM1 INF_HANDSFREE^BAD_ARG!".encode())
        data = sock.recv(1024)
        print(data.decode())
        
test_bad_arg()