import socket


def test_bad_server_command():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        data = sock.recv(1024)
        sock.sendall("NON EXISTENT SERVER COMMAND!".encode())
        data = sock.recv(1024)
        print(data.decode())
        
test_bad_server_command()