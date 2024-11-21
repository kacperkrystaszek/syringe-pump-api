import random
import socket
import time


commands = ["INF", "INF_BOLUS_CAP_RATE^1.356^ml/h", "INF_VTBI^ACTIV^1.356^ml^STOP", "INF_PURGE_RATE^1.356^ml/h", "INF_CAP_RATE^1.356^ml"]

def many_at_once():
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        
        for x in range(1, 17):
            sock.sendall(f"start COM{x}!".encode())
        time.sleep(2)
        
        for y in range(100):
            for x in range(1, 17):
                random_command = random.choice(commands)
                sock.sendall(f"pump COM{x} {random_command}!".encode())
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
    
many_at_once()