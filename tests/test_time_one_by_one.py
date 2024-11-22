import socket
import time

commands = ["INF", "INF_BOLUS_CAP_RATE^1.356^ml/h", "INF_VTBI^ACTIV^1.356^ml^STOP", "INF_PURGE_RATE^1.356^ml/h", "INF_CAP_RATE^1.356^ml"]

def one_by_one():
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        sock.recv(1024)
        sock.sendall("start COM1!".encode())
        sock.recv(1024)
        for command in commands*20:
            sock.sendall(f"pump COM1 {command}!".encode())
            start = time.perf_counter()
            sock.recv(1024)
            end = time.perf_counter() - start
            results.append(end)
            
    mean = sum(results)/len(results)
    maximum = max(results)
    minimum = min(results)
    print(f"srednia {mean:10f}")
    print(f"min {maximum:10f}")
    print(f"min {minimum:10f}")
    print(results)
        
    
one_by_one()
