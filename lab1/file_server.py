import socket
import os
import mimetypes
import sys
from email.utils import formatdate

if len(sys.argv) != 2:
    print("Usage: python file_server.py <directory_to_serve>")
    sys.exit(1)

serve_dir = os.path.abspath(sys.argv[1])
if not os.path.isdir(serve_dir):
    print("Error: not a valid directory")
    sys.exit(1)

HOST, PORT = '0.0.0.0', 8000
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((HOST, PORT))
sock.listen(1)

print(f"Serving directory: '{serve_dir}'")
print(f"Server running at: http://{HOST}:{PORT}\n")


def build_headers(status_code, content_type=None, content_length=0):
    reason_phrases = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
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
        "<ul>"
    ]

    if request_path not in ("", "/"):
        parent = os.path.dirname(request_path.rstrip("/"))
        if not parent.startswith("/"):
            parent = "/" + parent
        if parent == "":
            parent = "/"
        html.append(f'<li><a href="{parent}">.. (parent directory)</a></li>')

    for entry in entries:
        full_path = os.path.join(path, entry)
        display_name = entry + "/" if os.path.isdir(full_path) else entry
        link = os.path.join(request_path, entry).replace("\\", "/")
        if not link.startswith("/"):
            link = "/" + link
        if os.path.isdir(full_path):
            link = link.rstrip("/") + "/"
        html.append(f'<li><a href="{link}">{display_name}</a></li>')

    html.append("</ul></body></html>")
    return "\n".join(html).encode("utf-8")



while True:
    conn, addr = sock.accept()
    print(f"Connection from {addr}")

    try:
        request = conn.recv(2048).decode('iso-8859-1')
        if not request:
            conn.close()
            continue

        if request.splitlines():
            print(f"Request: {request.splitlines()[0]}")

        try:
            method, path, version = request.splitlines()[0].split()
        except ValueError:
            conn.sendall(build_headers(400))
            conn.sendall(b"Bad Request")
            conn.close()
            continue

        print(f"Requested path: '{path}'")

        if method != 'GET':
            conn.sendall(build_headers(405))
            conn.sendall(b"Method Not Allowed")
            conn.close()
            continue
        #time.sleep(1) ######

        safe_path = os.path.realpath(os.path.join(serve_dir, path.lstrip('/')))
        
        print(f"Looking for: '{safe_path}'")
        print(f"File exists: {os.path.exists(safe_path)}")
        print(f"Is file: {os.path.isfile(safe_path) if os.path.exists(safe_path) else 'N/A'}")
        print("---")

        if not safe_path.startswith(serve_dir):
            conn.sendall(build_headers(403))
            conn.sendall(b"Forbidden")
            conn.close()
            continue

        if os.path.isdir(safe_path):
            index_path = os.path.join(safe_path, "index.html")
            print(f"Directory detected, checking for index: '{index_path}'")

            if os.path.isfile(index_path) and not path.startswith("/downloads"):
                safe_path = index_path
                print(f"Using index file: '{safe_path}'")
            else:
                listing_html = generate_directory_listing(safe_path, path)
                conn.sendall(build_headers(200, "text/html", len(listing_html)) + listing_html)
                conn.close()
                continue

        if not os.path.isfile(safe_path):
            print(f"FILE NOT FOUND: '{safe_path}'")
            conn.sendall(build_headers(404))
            conn.sendall(b"404 Not Found")
            conn.close()
            continue

        mime_type, _ = mimetypes.guess_type(safe_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        print(f"Serving file: '{safe_path}' with MIME type: {mime_type}")
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