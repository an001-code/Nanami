"""本地静态 HTTP server：为 QWebEngineView 服务 Live2D 资源（模型需 HTTP 访问）。"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D401
        pass


class StaticServer:
    def __init__(self, directory: str | Path, port: int = 0) -> None:
        self.directory = str(Path(directory))
        handler = functools.partial(_QuietHandler, directory=self.directory)
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
        self.port: int = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
