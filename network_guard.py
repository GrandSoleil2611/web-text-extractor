"""Per-crawl egress proxy: resolve once, connect to that validated public IP.

This protects redirects and browser subresources as well as the initial URL.
No request content is logged. The outer worker enforces the total deadline.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import ipaddress
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit

from settings import PUBLIC_DEPLOYMENT

proxy_url = ContextVar("crawl_proxy_url", default=None)


def connect_public(host, port):
    if port not in (80, 443):
        raise ValueError("Public mode supports ports 80 and 443 only")
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global
                            or ipaddress.ip_address(a[4][0]).is_multicast for a in addresses):
        raise ValueError("Non-public destination blocked")
    for family, kind, proto, _, address in addresses:
        conn = socket.socket(family, kind, proto)
        conn.settimeout(15)
        try:
            conn.connect(address)  # numeric address: no second DNS lookup
            return conn
        except OSError:
            conn.close()
    raise OSError("Destination unavailable")


class _Proxy(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self):
        self.slots = threading.BoundedSemaphore(24)
        super().__init__(("127.0.0.1", 0), _Handler)

    def handle_error(self, request, client_address):
        pass  # Never log visitor URLs, headers, or content.


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        if not self.server.slots.acquire(blocking=False):
            return
        try:
            self.connection.settimeout(15)
            line = self.rfile.readline(8193)
            if len(line) > 8192:
                return
            method, target, version = line.decode("latin1").strip().split(" ", 2)
            headers = []
            size = 0
            while True:
                line = self.rfile.readline(8193)
                size += len(line)
                if size > 32768 or not line:
                    return
                if line == b"\r\n":
                    break
                if line.split(b":", 1)[0].lower() not in (b"connection", b"proxy-connection", b"proxy-authorization"):
                    headers.append(line)
            parsed = urlsplit("//" + target if method == "CONNECT" else target)
            if not parsed.hostname or parsed.username or parsed.password:
                return
            if method != "CONNECT" and parsed.scheme != "http":
                return
            port = parsed.port or (443 if method == "CONNECT" else 80)
            with connect_public(parsed.hostname, port) as upstream:
                if method == "CONNECT":
                    self.connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                else:
                    path = parsed.path or "/"
                    if parsed.query:
                        path += "?" + parsed.query
                    upstream.sendall(f"{method} {path} {version}\r\n".encode("latin1")
                                     + b"".join(headers) + b"Connection: close\r\n\r\n")
                deadline = time.monotonic() + 80
                total = 0
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 15)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        total += len(data)
                        if total > 32 * 1024 * 1024:
                            return
                        (upstream if source is self.connection else self.connection).sendall(data)
        except (OSError, ValueError):
            try:
                self.connection.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
        finally:
            self.server.slots.release()

    # Unbuffered headers leave HTTP request bodies available to the relay.
    rbufsize = 0


@contextmanager
def public_network():
    if not PUBLIC_DEPLOYMENT or proxy_url.get():
        yield
        return
    with _Proxy() as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        token = proxy_url.set(f"http://127.0.0.1:{server.server_address[1]}")
        try:
            yield
        finally:
            proxy_url.reset(token)
            server.shutdown()
            thread.join(timeout=2)


def guarded_network(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with public_network():
            return function(*args, **kwargs)
    return wrapped
