from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Callable

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ADDRESS_RE = re.compile(r"(?:https?://)?([a-zA-Z0-9.-]+\.joinmc\.link(?::\d+)?|[a-zA-Z0-9.-]+\.playit\.gg(?::\d+)?)", re.I)


class ServerManager:
    """Owns independent Minecraft and playit child processes."""

    def __init__(self, log: Callable[[str, str], None], state: Callable[[str, str], None]):
        self.log, self.state = log, state
        self.config: dict = {}
        self.server_proc: subprocess.Popen | None = None
        self.playit_proc: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._starting = False
        self._stopping = False
        self._recovering = False
        self._recovery_timer: threading.Timer | None = None
        self._restart_config: dict | None = None
        self._server_done = threading.Event()
        self._server_done.set()
        self.address = ""

    def setup(self, config: dict) -> None:
        self.config = config.copy()
        threading.Thread(target=self._setup_worker, daemon=True).start()

    def _setup_worker(self) -> None:
        try:
            directory = Path(self.config["server_dir"]).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            jar = directory / "server.jar"
            if jar.exists():
                self.log("Server jar already exists; keeping it.", "system")
            else:
                version = self.config["minecraft_version"].strip()
                self.log("Fetching official Minecraft version manifest…", "system")
                manifest = self._get_json(MANIFEST_URL)
                if version.lower() == "latest":
                    version = manifest["latest"]["release"]
                    self.log(f"Using latest release: Minecraft {version}", "system")
                entry = next((item for item in manifest["versions"] if item["id"] == version), None)
                if not entry:
                    raise ValueError(f"Minecraft version {version!r} was not found in Mojang's manifest.")
                details = self._get_json(entry["url"])
                url = details["downloads"]["server"]["url"]
                temp = directory / "server.jar.part"
                self.log("Downloading official Minecraft server…", "system")
                urllib.request.urlretrieve(url, temp)
                temp.replace(jar)
            eula = directory / "eula.txt"
            if not eula.exists():
                eula.write_text("# Review the Minecraft EULA before accepting.\neula=false\n", encoding="utf-8")
            props = directory / "server.properties"
            if not props.exists():
                props.write_text("server-port=25565\nserver-ip=\nmax-players=20\nmotd=Minecraft Server Manager\nonline-mode=true\n", encoding="utf-8")
            self.log(f"Setup complete: {directory}", "system")
            self.state("ready", "Setup complete. Review eula.txt, then accept the EULA to start.")
        except Exception as exc:
            self.log(f"Setup failed: {exc}", "error")
            self.state("error", str(exc))

    @staticmethod
    def _get_json(url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "MinecraftServerManager/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def start(self, config: dict) -> None:
        self.config = config.copy()
        with self._lock:
            if self._starting or (self.server_proc and self.server_proc.poll() is None):
                self.log("Minecraft is already running or starting.", "system")
                return
            self._stopping = False
            self._starting = True
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self) -> None:
        directory = Path(self.config["server_dir"]).expanduser()
        jar = directory / "server.jar"
        if not jar.exists():
            with self._lock:
                self._starting = False
            self.log("Run Setup first to download the server jar.", "error")
            self.state("error", "Server jar not found")
            return
        if not (directory / "eula.txt").exists() or "eula=true" not in (directory / "eula.txt").read_text(encoding="utf-8").lower():
            with self._lock:
                self._starting = False
            self.log("Minecraft EULA not accepted. Review eula.txt and set eula=true to continue.", "error")
            self.state("eula", "Accept the Minecraft EULA in eula.txt to start.")
            return
        try:
            java = self.config.get("java_path", "java") or "java"
            memory = max(1, min(64, int(self.config.get("memory_gb", 4))))
            command = [java, f"-Xms{min(memory, 2)}G", f"-Xmx{memory}G", "-jar", "server.jar", "nogui"]
            self.log("Starting Minecraft…", "system")
            with self._lock:
                if self._stopping:
                    self._starting = False
                    return
                self._server_done.clear()
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                self.server_proc = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                                    creationflags=flags)
                self._starting = False
            self.state("starting", "Minecraft is starting")
            proc = self.server_proc
            threading.Thread(target=self._read_process, args=(proc, "minecraft"), daemon=True).start()
            self._start_playit()
            code = proc.wait()
            self.log(f"Minecraft exited (code {code}).", "system")
            with self._lock:
                if self.server_proc is proc:
                    self.server_proc = None
            self.state("stopped", "Minecraft stopped")
            self._maybe_recover()
            self._server_done.set()
        except FileNotFoundError:
            with self._lock:
                self._starting = False
                self._server_done.set()
            self.log("Java was not found. Install a compatible Java runtime or set its full path in Settings.", "error")
            self.state("error", "Java not found")
        except Exception as exc:
            with self._lock:
                self._starting = False
                self._server_done.set()
            self.log(f"Could not start Minecraft: {exc}", "error")
            self.state("error", str(exc))

    def _start_playit(self) -> None:
        with self._lock:
            if self._stopping:
                return
            if self.playit_proc and self.playit_proc.poll() is None:
                return
            path = self.config.get("playit_path", "").strip()
            if not path:
                self.log("playit agent not configured. Select the existing playit executable in Settings.", "system")
                return
            executable = Path(path).expanduser()
            if not executable.is_file():
                self.log(f"playit executable not found: {executable}", "error")
                return
            try:
                playit_cwd = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BlockHost" / "playit"
                playit_cwd.mkdir(parents=True, exist_ok=True)
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                self.playit_proc = subprocess.Popen([str(executable)], cwd=playit_cwd, stdout=subprocess.PIPE,
                                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                                    encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
                self.log("Started the existing playit agent as a separate process.", "system")
                threading.Thread(target=self._read_process, args=(self.playit_proc, "playit"), daemon=True).start()
            except Exception as exc:
                self.log(f"Could not start playit: {exc}", "error")

    def _read_process(self, proc: subprocess.Popen, name: str) -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            self.log(line, name)
            match = ADDRESS_RE.search(line)
            if match:
                self.address = match.group(1)
                self.state("address", self.address)

    def send_command(self, command: str) -> None:
        proc = self.server_proc
        if not proc or proc.poll() is not None or not proc.stdin:
            self.log("Minecraft is not running.", "error")
            return
        try:
            proc.stdin.write(command.strip() + "\n")
            proc.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            self.log(f"Could not send command: {exc}", "error")

    def stop(self) -> None:
        with self._lock:
            self._stopping = True
            self._restart_config = None
            if self._recovery_timer:
                self._recovery_timer.cancel()
                self._recovery_timer = None
            self._recovering = False
        self.state("stopping", "Stopping Minecraft and playit…")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def restart(self, config: dict) -> None:
        with self._lock:
            self.config = config.copy()
            if self._recovery_timer:
                self._recovery_timer.cancel()
                self._recovery_timer = None
            self._recovering = False
            if self._starting:
                self.log("Wait for Minecraft to finish starting before restarting it.", "system")
                return
            if not self.server_proc:
                self.log("Minecraft is stopped; starting it now.", "system")
                start_now = True
            else:
                self._stopping = True
                self._restart_config = config.copy()
                start_now = False
        if start_now:
            self.start(config)
            return
        self.state("stopping", "Restarting Minecraft and playit…")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _stop_worker(self) -> None:
        with self._lock:
            server, playit = self.server_proc, self.playit_proc
        if server and server.poll() is None:
            try:
                if server.stdin:
                    server.stdin.write("stop\n"); server.stdin.flush()
                server.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired):
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
        if playit and playit.poll() is None:
            playit.terminate()
            try:
                playit.wait(timeout=5)
            except subprocess.TimeoutExpired:
                playit.kill()
                playit.wait(timeout=3)
        with self._lock:
            restart_config = self._restart_config
        if restart_config:
            self._server_done.wait(timeout=30)
        self.playit_proc = None
        self.state("stopped", "Minecraft and playit stopped")
        with self._lock:
            restart_config = self._restart_config
            self._restart_config = None
            self._stopping = restart_config is None
        if restart_config:
            self.log("Restarting Minecraft…", "system")
            timer = threading.Timer(0.75, lambda: self.start(restart_config))
            timer.daemon = True
            timer.start()

    def _maybe_recover(self) -> None:
        with self._lock:
            if self._stopping or not self.config.get("auto_restart") or self._recovering:
                self._recovering = False
                return
            self._recovering = True
        delay = max(1, min(300, int(self.config.get("restart_delay", 10))))
        self.log(f"Crash recovery: restarting in {delay} seconds…", "system")
        self.state("recovering", f"Restarting in {delay} seconds")
        timer = threading.Timer(delay, self._restart_after_crash_delay)
        timer.daemon = True
        with self._lock:
            self._recovery_timer = timer
        timer.start()

    def _restart_after_crash_delay(self) -> None:
        with self._lock:
            self._recovery_timer = None
            self._recovering = False
            if self._stopping:
                return
            config = self.config.copy()
        self.start(config)
