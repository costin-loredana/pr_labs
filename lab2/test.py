import threading
import socket
import time

HOST = 'localhost'
PORT = 8000
PATH = '/'  # or /site_pages/test.html if that file exists
NUM_REQUESTS = 10
VERBOSE = True  # Set False to suppress per-request logs

def make_request(index):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HOST, PORT))
            request = f"GET {PATH} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode('utf-8'))

            # Read full response
            while True:
                data = sock.recv(4096)
                if not data:
                    break

            if VERBOSE:
                print(f"Request {index} completed.")

    except Exception as e:
        print(f"Request {index} failed: {e}")

def run_load_test():
    print(f"\nStarting test with {NUM_REQUESTS} concurrent requests...")

    start_time = time.time()
    threads = []

    for i in range(NUM_REQUESTS):
        t = threading.Thread(target=make_request, args=(i + 1,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    print(f"\nAll {NUM_REQUESTS} requests completed in {elapsed:.2f} seconds.")

if __name__ == '__main__':
    run_load_test()
