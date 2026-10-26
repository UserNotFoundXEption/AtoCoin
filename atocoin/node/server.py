from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from ..net import MAX_BODY_BYTES

log = logging.getLogger("atocoin.node.http")


class NodeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, node):
        self.node = node
        super().__init__(address, NodeRequestHandler)


class NodeRequestHandler(BaseHTTPRequestHandler):
    timeout = 10

    def log_message(self, format: str, *args) -> None:
        log.debug("%s: %s", self.address_string(), format % args)


    def do_GET(self):
        self._handle("GET")


    def do_POST(self):
        self._handle("POST")


    def _handle(self, method: str) -> None:
        body = None
        if method == "POST":
            body, error = self._read_json_body()
            if error is not None:
                return self._send(400, {"error": error})
            
        path = urlsplit(self.path).path
        status, payload = self.server.node.handle_request(method, path, body)
        self._send(status, payload)


    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, "Invalid Content-Length header"
        
        if length < 0:
            return None, "Invalid Content-Length header"
        if length > MAX_BODY_BYTES:
            return None, "Body too long"
        
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}, None
        
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "Invalid JSON"
        
        if not isinstance(body, dict):
            return None, "Invalid JSON"
        
        return body, None


    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(node, host: str, port: int) -> NodeHTTPServer:
    return NodeHTTPServer((host, port), node)
