import threading
import socket
import time
import sys

HOST = 'localhost'  
PORT = 8000
PATH = '/docs'
NUM_REQUESTS = 100

if len(sys.argv) != 2:
    print("Usage: python client.py [spammer|slowpoke]")
    sys.exit(1)

def wait_for_server(host, port, timeout=20):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[INFO] Server is ready at {host}:{port}")
                return
        except Exception:
            print(f"[WAIT] Waiting for server {host}:{port}...")
            time.sleep(1)
    raise Exception(f"Timeout: Could not connect to server at {host}:{port}")

wait_for_server(HOST, PORT)

mode = sys.argv[1].lower()
delay = 0 if mode == 'spammer' else 0.2  

success_count = 0
lock = threading.Lock()

def make_request(index):
    global success_count
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((HOST, PORT))
            request = f"GET {PATH} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode('iso-8859-1'))

            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data

            with lock:
                if b"200 OK" in response:
                    success_count += 1
                    print(f"[{mode}] Request {index}:   200 OK")
                elif b"429 Too Many Requests" in response:
                    print(f"[{mode}] Request {index}:   429 Too Many Requests")
                else:
                    print(f"[{mode}] Request {index}:   Unknown response")
        except Exception as e:
            print(f"[{mode}] Request {index}:  Error - {e}")

threads = []
start = time.time()

for i in range(NUM_REQUESTS):
    t = threading.Thread(target=make_request, args=(i + 1,))
    t.start()
    threads.append(t)
    if delay > 0:
        time.sleep(delay)

for t in threads:
    t.join()

end = time.time()
elapsed = end - start
print(f"\n[{mode}]  {success_count} successful out of {NUM_REQUESTS} in {elapsed:.2f} sec → {success_count / elapsed:.2f} req/sec")
