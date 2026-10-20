"""Reconnectable GUI client for the persistent local server manager."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time

from .config import APP_DIR, FROZEN
from .host import HOST, PORT, TOKEN_PATH, _token


class ManagerClient:
    def __init__(self, on_event):
        self.on_event = on_event
        self._socket: socket.socket | None = None
        self._write_lock = threading.Lock()
        self._connected = threading.Event()
        self._closed = threading.Event()
        self._spawned = False
        threading.Thread(target=self._connection_loop, daemon=True).start()

    @property
    def connected(self):
        return self._connected.is_set()

    def _connection_loop(self):
        while not self._closed.is_set():
            try:
                sock = socket.create_connection((HOST, PORT), timeout=0.5)
            except OSError:
                if not self._spawned:
                    self._spawn_host()
                self._closed.wait(0.5)
                continue
            sock.settimeout(None)
            self._socket = sock
            self._connected.set()
            self._send_raw({"token": _token()})
            self.on_event({"type": "connected"})
            try:
                stream = sock.makefile("rb")
                for line in stream:
                    if self._closed.is_set():
                        break
                    try:
                        self.on_event(json.loads(line.decode("utf-8")))
                    except (ValueError, UnicodeDecodeError):
                        continue
            except OSError:
                pass
            self._connected.clear()
            self._socket = None
            try:
                sock.close()
            except OSError:
                pass
            if not self._closed.is_set():
                self.on_event({"type": "disconnected"})
                self._closed.wait(1)

    def _spawn_host(self):
        self._spawned = True
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            command = [sys.executable, "--host"] if FROZEN else [sys.executable, "-m", "mcmanager.host"]
            subprocess.Popen(command, cwd=APP_DIR,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
        except OSError as exc:
            self.on_event({"type": "error", "message": f"Could not start the background manager: {exc}"})

    def _send_raw(self, payload: dict):
        with self._write_lock:
            sock = self._socket
            if not sock or not self._connected.is_set():
                self.on_event({"type": "error", "message": "Background manager is reconnecting. Try again in a moment."})
                return False
            try:
                sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                return True
            except OSError:
                self._connected.clear()
                return False

    def send(self, action: str, **values):
        return self._send_raw({"action": action, **values})

    def close(self):
        self._closed.set()
        self._connected.clear()
        sock = self._socket
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
