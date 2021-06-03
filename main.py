import socket
import threading
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler
from io import BytesIO

HOST = '127.0.0.1'
PORT = 8888
BUFF = 8192


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, raw_http_request):
        self.rfile = BytesIO(raw_http_request.encode('utf-8'))
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

        data = self.headers['Host'].split(':')
        self.host = data[0]
        self.port = 80 if len(data) == 1 else int(data[1])


def build_tunnel(server_sock: socket.socket, client_sock: socket.socket):
    message = b"HTTP/1.1 200 Connection established\r\n" \
              b"ProxyServer-agent: Egor\r\n\r\n"
    client_sock.sendall(message)

    client_sock.setblocking(False)
    server_sock.setblocking(False)

    while True:
        try:
            data = client_sock.recv(BUFF)
            if data is None:
                break
            server_sock.sendall(data)
        except socket.error:
            pass

        try:
            data = server_sock.recv(BUFF)
            if data is None:
                break
            client_sock.sendall(data)
        except socket.error:
            pass

    client_sock.close()
    server_sock.close()


def handle_conn(client_sock: socket.socket):
    raw_request = client_sock.recv(BUFF)
    request = HTTPRequest(raw_request.decode())
    print(f"Connecting to {request.host}:{request.port}")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_sock.connect((request.host, request.port))
    except socket.error:
        print(f'Could not connect to {request.host}:{request.port}')
        client_sock.close()
        server_sock.close()
        return

    if 'CONNECT' != request.command:
        server_sock.sendall(raw_request)

        raw_response = server_sock.recv(BUFF)
        raw_headers = raw_response.split(b'\r\n\r\n', 1)[0].split(b'\r\n', 1)[1]
        headers = BytesParser().parsebytes(raw_headers)

        if 'Content-Length' in headers:
            while len(raw_response) < int(headers['Content-Length']):
                raw_response += server_sock.recv(BUFF)
        elif 'Transfer-Encoding' in headers \
                and headers['Transfer-Encoding'] == 'chunked':
            while not raw_response.endswith(b'0\r\n\r\n'):
                raw_response += server_sock.recv(BUFF)

        client_sock.sendall(raw_response)

        server_sock.close()
        client_sock.close()
    else:
        build_tunnel(server_sock, client_sock)


def run_proxy():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()

    while True:
        client_sock, addr = sock.accept()
        print(f'Socket accepted connection from {addr[0]}:{addr[1]}')
        threading.Thread(
            target=handle_conn,
            args=(client_sock,)
        ).start()


if __name__ == '__main__':
    run_proxy()
