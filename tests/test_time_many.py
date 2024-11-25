import random
import socket
import time


commands = ["INF", "ALARM", "AUDIO_QUIET", "AUDIO_VOL", "COMMS_PROTOCOL", "DISPLAY_ILLUM", "DRUG_LIB_NUMDRUGS", "DRUG_SELECT"]

def many_at_once():
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('localhost', 4000))
        sock.recv(1024)
        
        for x in range(1, 9):
            sock.sendall(f"start COM{x}!".encode())
            sock.recv(1024)
        
        for y in range(10):
            str_result = ""
            for x in range(1, 9):
                random_command = random.choice(commands)
                str_result += f"pump COM{x} {random_command}!"
            print(str_result)
            sock.sendall(str_result.encode())
            start = time.perf_counter()
            print(start)
            d = sock.recv(1024)
            end = time.perf_counter() - start
            print(end)
            print(d.decode())
            results.append(end)
            
            for x in range(1, 8):
                sock.recv(1024)
            
    mean = sum(results)/len(results)
    maximum = max(results)
    minimum = min(results)
    print(f"srednia {mean:10f}")
    print(f"max {maximum:10f}")
    print(f"min {minimum:10f}")
    print(results)
    
many_at_once()