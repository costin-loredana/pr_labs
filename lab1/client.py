import socket
import sys
import os
from urllib.parse import urlparse

if len(sys.argv) != 5:
    print("Usage: python client.py <server_host> <server_port> <url_path> <directory>")
    sys.exit(1)

server_host = sys.argv[1]
server_port = int(sys.argv[2])
url_path = sys.argv[3]
save_dir = os.path.abspath(sys.argv[4])

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((server_host, server_port))
    request = f"GET {url_path} HTTP/1.1\r\nHost: {server_host}\r\nConnection: close\r\n\r\n"
    sock.sendall(request.encode('iso-8859-1'))

    response = b""
    while True:
        data = sock.recv(4096)
        if not data:
            break
        response += data

try:
    header_data, body = response.split(b"\r\n\r\n", 1)
except ValueError:
    print("Invalid response from server.")
    sys.exit(1)

headers = header_data.decode('iso-8859-1', errors='replace').splitlines()

status_line = headers[0] if headers else ""
status_code = status_line.split()[1] if len(status_line.split()) > 1 else "000"

if status_code != "200":
    print(f"Server returned status {status_code}")
    print(body.decode('iso-8859-1', errors='replace'))
    sys.exit(0)

content_type = None
for line in headers:
    if line.lower().startswith("content-type:"):
        content_type = line.split(":", 1)[1].strip().lower()
        break

parsed_url = urlparse(url_path)
filename = os.path.basename(parsed_url.path) or "index.html"
save_path = os.path.join(save_dir, filename)

if content_type and "text/html" in content_type:
    print(body.decode('utf-8', errors='replace'))
    with open(save_path, "wb") as f:
        f.write(body)
    print(f"\nHTML saved as: {save_path}")

elif content_type and any(x in content_type for x in ["image/png", "application/pdf"]):
    with open(save_path, "wb") as f:
        f.write(body)
    print(f"File saved to: {save_path} ({content_type})")

else:
    with open(save_path, "wb") as f:
        f.write(body)
    print(f"File saved to: {save_path} ({content_type})")
