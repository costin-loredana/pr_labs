import socket
import os
import mimetypes
import sys
import time
from datetime import datetime
from email.utils import formatdate
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, deque
import posixpath

#how many workers are optimal
MAX_WORKERS = 10
HOST, PORT = '0.0.0.0', 8000

request_counts = {}
counter_lock = threading.Lock()
USE_LOCK = True  

rate_limits = defaultdict(deque)
rate_limit_lock = threading.Lock()
RATE_LIMIT = 5
WINDOW_SECONDS = 1

if len(sys.argv) != 2:
    print("Usage: python web-server.py <directory_to_serve>")
    sys.exit(1)

serve_dir = os.path.abspath(sys.argv[1])
if not os.path.isdir(serve_dir):
    print("Error: not a valid directory")
    sys.exit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((HOST, PORT))
sock.listen(20)

print(f"Serving directory: '{serve_dir}'")
print(f"Server running at: http://{HOST}:{PORT}\n")

def build_headers(status_code, content_type=None, content_length=0):
    reason_phrases = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        429: "Too Many Requests",
        500: "Internal Server Error",
    }
    reason = reason_phrases.get(status_code, "Unknown")
    headers = [
        f"HTTP/1.1 {status_code} {reason}",
        f"Date: {formatdate(timeval=None, localtime=False, usegmt=True)}",
        "Server: SimplePythonServer/1.1",
        "Connection: close",
    ]
    if content_type:
        headers.append(f"Content-Type: {content_type}")
    if content_length:
        headers.append(f"Content-Length: {content_length}")
    headers.append("")
    headers.append("")
    return "\r\n".join(headers).encode('iso-8859-1')

def generate_directory_listing(path, request_path):
    entries = os.listdir(path)
    html = [
        "<html><head><title>Directory listing</title></head><body>",
        f"<h2>Directory listing for {request_path}</h2>",
        "<table border='1'><tr><th>File / Directory</th><th>Hits</th></tr>"
    ]

    if request_path != "/":
        parent = posixpath.normpath(request_path.rstrip("/"))
        parent = posixpath.dirname(parent)
        if not parent.startswith("/"):
            parent = "/" + parent
        html.append(f'<tr><td><a href="{parent}">.. (parent directory)</a></td><td>-</td></tr>')

    for entry in entries:
        full_path = os.path.join(path, entry)
        display_name = entry + "/" if os.path.isdir(full_path) else entry
        link = os.path.join(request_path, entry).replace("\\", "/")
        if os.path.isdir(full_path):
            link += "/"

        hit_count = request_counts.get(link, 0)
        html.append(f'<tr><td><a href="{link}">{display_name}</a></td><td>{hit_count}</td></tr>')

    html.append("</table></body></html>")
    return "\n".join(html).encode("utf-8")

def handle_client(conn, addr):
    time.sleep(1)  
    ip = addr[0]
    current_time = time.time()
    with rate_limit_lock:
        timestamps = rate_limits[ip]
        while timestamps and (current_time - timestamps[0]) > WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= RATE_LIMIT:
            print(f"Rate limit exceeded for {ip}. Closing connection.")
            conn.sendall(build_headers(429, "text/plain", 0))
            conn.sendall(b"429 Too Many Requests")
            conn.close()
            return
        timestamps.append(current_time)
        print(f" [ALLOWED] {ip} request accepted.")

    print(f"Connection from {addr}")

    try:
        request = conn.recv(2048).decode('iso-8859-1')
        if not request:
            conn.close()
            return

        if request.splitlines():
            print(f"Request: {request.splitlines()[0]}")

        try:
            method, path, version = request.splitlines()[0].split()
        except ValueError:
            conn.sendall(build_headers(400))
            conn.sendall(b"Bad Request")
            return

        print(f"Requested path: '{path}'")
        safe_path = os.path.realpath(os.path.join(serve_dir, path.lstrip('/')))

        if not safe_path.startswith(serve_dir):
            conn.sendall(build_headers(403))
            conn.sendall(b"Forbidden")
            return

        time.sleep(0.01)
        if USE_LOCK:
            with counter_lock:
                request_counts[path] = request_counts.get(path, 0) + 1
        else:
            request_counts[path] = request_counts.get(path, 0) + 1

        if os.path.isdir(safe_path):
            index_path = os.path.join(safe_path, "index.html")
            if os.path.isfile(index_path):
                safe_path = index_path
            else:
                listing_html = generate_directory_listing(safe_path, path)
                conn.sendall(build_headers(200, "text/html", len(listing_html)) + listing_html)
                return

        if not os.path.isfile(safe_path):
            conn.sendall(build_headers(404))
            conn.sendall(b"404 Not Found")
            return

        mime_type, _ = mimetypes.guess_type(safe_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        with open(safe_path, 'rb') as f:
            body = f.read()

        conn.sendall(build_headers(200, mime_type, len(body)) + body)

    except Exception as e:
        print("Error:", e)
        try:
            conn.sendall(build_headers(500))
            conn.sendall(b"Internal Server Error")
        except:
            pass
    finally:
        conn.close()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    try:
        while True:
            conn, addr = sock.accept()
            executor.submit(handle_client, conn, addr)
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        try:
            conn.shutdown(socket.SHUT_WR)
            
        except OSError:
            pass
        conn.close()

