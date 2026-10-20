"""Background process that keeps server control and console streams alive."""
from __future__ import annotations

import json
import secrets
import socketserver
import threading
import time
from collections import deque
from pathlib import Path

from .config import APP_DIR, load_config
from .server import ServerManager

HOST = "127.0.0.1"
PORT = 38721
TOKEN_PATH = APP_DIR / ".host-token"


def _token() -> str:
    try:
        return TOKEN_PATH.read_text(encoding="ascii").strip()
    except OSError:
        value = secrets.token_urlsafe(32)
        TOKEN_PATH.write_text(value, encoding="ascii")
        return value


class HostService:
    def __init__(self):
        self.lock = threading.RLock()
        self.clients = set()
        self.history = deque(maxlen=800)
        self.server_state = "stopped"
        self.tunnel_state = "Not running"
        self.address = "No public address yet"
        self.manager = ServerManager(self.log, self.state)
        self.manager.config = load_config()

    def log(self, message: str, source: str):
        event = {"type": "log", "message": message, "source": source}
        with self.lock:
            self.history.append(event)
        self.broadcast(event)

    def state(self, state: str, message: str):
        if state == "address":
            self.address = message
        elif state == "starting":
            self.server_state = "Starting"
        elif state == "recovering":
            self.server_state = message
        elif state == "ready":
            self.server_state = "Ready"
        elif state in ("stopped", "error", "eula"):
            self.server_state = "Stopped"
        elif state == "stopping":
            self.server_state = "Stopping"
        self.broadcast({"type": "state", "state": state, "message": message})

    def snapshot(self) -> dict:
        server = self.manager.server_proc
        playit = self.manager.playit_proc
        if server and server.poll() is None:
            self.server_state = "Running"
        elif not self.manager._recovering and self.server_state in ("Running", "Starting", "Stopping"):
            self.server_state = "Stopped"
        if playit and playit.poll() is None:
            self.tunnel_state = "Agent running"
        else:
            self.tunnel_state = "Not running"
        return {"type": "snapshot", "server": self.server_state, "tunnel": self.tunnel_state,
                "address": self.address, "capabilities": ["restart"]}

    def add_client(self, client):
        with self.lock:
            self.clients.add(client)
            backlog = list(self.history)
            snapshot = self.snapshot()
        for event in backlog:
            client.send_event(event)
        client.send_event(snapshot)

    def remove_client(self, client):
        with self.lock:
            self.clients.discard(client)

    def broadcast(self, event: dict):
        with self.lock:
            clients = tuple(self.clients)
        for client in clients:
            client.send_event(event)


class ClientHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self._write_lock = threading.Lock()
        self._subscribed = False

    def send_event(self, event: dict):
        try:
            payload = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            with self._write_lock:
                self.wfile.write(payload)
                self.wfile.flush()
        except (OSError, ValueError):
            self.server.service.remove_client(self)

    def handle(self):
        first = self.rfile.readline(4096)
        try:
            hello = json.loads(first.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if hello.get("token") != self.server.token:
            return
        self._subscribed = True
        self.server.service.add_client(self)
        for raw in self.rfile:
            try:
                request = json.loads(raw.decode("utf-8"))
                action = request.get("action")
                service = self.server.service
                if action == "setup":
                    config = request.get("config") or load_config()
                    service.manager.setup(config)
                elif action == "start":
                    service.manager.start(request.get("config") or load_config())
                elif action == "stop":
                    service.manager.stop()
                elif action == "restart":
                    service.manager.restart(request.get("config") or load_config())
                elif action == "command":
                    service.manager.send_command(request.get("command", ""))
            except (ValueError, TypeError, OSError) as exc:
                self.server.service.log(f"Manager command failed: {exc}", "error")

    def finish(self):
        if self._subscribed:
            self.server.service.remove_client(self)
        super().finish()


class LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, service: HostService, token: str):
        self.service, self.token = service, token
        super().__init__((HOST, PORT), ClientHandler)


def main():
    service = HostService()
    server = LocalServer(service, _token())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while True:
            service.broadcast(service.snapshot())
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
