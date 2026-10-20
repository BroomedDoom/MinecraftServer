from __future__ import annotations

import queue
import subprocess
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import load_config, save_config
from .client import ManagerClient
from .properties import read_properties, write_properties

BG, PANEL, PANEL2, TEXT, MUTED, GREEN, BLUE, RED = "#0b1020", "#121a2b", "#182338", "#e8edf8", "#91a0b8", "#65d69b", "#80aaff", "#ff7885"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BlockHost — Minecraft Server Manager")
        self.root.geometry("1050x720")
        self.root.minsize(850, 600)
        self.root.configure(bg=BG)
        self.config = load_config()
        self.events: queue.Queue = queue.Queue()
        self.status_text = tk.StringVar(value="Connecting to background manager…")
        self.address_text = tk.StringVar(value="No public address yet")
        self.server_var = tk.StringVar(value="Stopped")
        self.tunnel_var = tk.StringVar(value="Not running")
        self.command_history: list[str] = []
        self.history_index: int | None = None
        self._host_supports_restart = False
        self._restart_pending_config: dict | None = None
        self._make_styles()
        self._build()
        self._load_settings()
        self.manager = ManagerClient(self._on_manager_event)
        self.root.after(100, self._drain_events)
        self.root.after(350, self._focus_command_entry)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _make_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 22))
        style.configure("TEntry", fieldbackground=PANEL2, foreground=TEXT, insertcolor=TEXT, bordercolor="#2a3852", padding=8)
        style.configure("TCombobox", fieldbackground=PANEL2, foreground=TEXT, padding=7)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(14, 9), background=PANEL2, foreground=TEXT, borderwidth=0)
        style.map("TButton", background=[("active", "#263653")])
        style.configure("Green.TButton", background=GREEN, foreground="#07120d")
        style.map("Green.TButton", background=[("active", "#7be4aa")])
        style.configure("Stop.TButton", background="#482632", foreground="#ffb3ba")

    def _build(self) -> None:
        viewport = ttk.Frame(self.root)
        viewport.pack(fill="both", expand=True)
        self.main_canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, borderwidth=0)
        self.main_canvas.pack(side="left", fill="both", expand=True)
        main_scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.main_canvas.yview)
        main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.configure(yscrollcommand=main_scrollbar.set)
        shell = ttk.Frame(self.main_canvas, padding=24)
        self.main_canvas_window = self.main_canvas.create_window((0, 0), window=shell, anchor="nw")
        shell.bind("<Configure>", lambda _event: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda event: self.main_canvas.itemconfigure(self.main_canvas_window, width=event.width))
        self.main_canvas.bind_all("<MouseWheel>", self._scroll_main)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 20))
        ttk.Label(header, text="BlockHost", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="MINECRAFT JAVA  ·  LOCAL HOSTING + PLAYIT", foreground=MUTED).pack(side="left", padx=18, pady=(8, 0))
        ttk.Label(header, textvariable=self.status_text, foreground=GREEN).pack(side="right", pady=(8, 0))

        cards = ttk.Frame(shell)
        cards.pack(fill="x", pady=(0, 16))
        self._card(cards, "MINECRAFT SERVER", self.server_var, "●", GREEN).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._card(cards, "PLAYIT TUNNEL", self.tunnel_var, "↗", BLUE).pack(side="left", fill="x", expand=True, padx=8)
        self._card(cards, "PUBLIC ADDRESS", self.address_text, "⌁", BLUE).pack(side="left", fill="x", expand=True, padx=(8, 0))

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 16))
        ttk.Button(actions, text="⬇  Set up server", style="Green.TButton", command=self._setup).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="▶  Start", style="Green.TButton", command=self._start).pack(side="left", padx=8)
        ttk.Button(actions, text="↻  Restart", command=self._restart).pack(side="left", padx=8)
        ttk.Button(actions, text="■  Stop", style="Stop.TButton", command=lambda: self.manager.send("stop")).pack(side="left", padx=8)
        ttk.Button(actions, text="⚙  Server properties", command=self._open_properties).pack(side="left", padx=8)
        ttk.Label(actions, text="Closing this window keeps the server running", foreground=MUTED).pack(side="left", padx=12)
        ttk.Button(actions, text="Open server folder", command=self._open_folder).pack(side="right")

        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Panel.TFrame", padding=16)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.configure(width=330)
        left.pack_propagate(False)
        ttk.Label(left, text="SERVER SETTINGS", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 12))
        self.entries = {}
        self._field(left, "Server folder", "server_dir", browse="folder")
        self._field(left, "Minecraft version", "minecraft_version")
        self._field(left, "Memory (GB)", "memory_gb")
        self._field(left, "Java executable", "java_path", browse="file")
        self._field(left, "playit executable", "playit_path", browse="file")
        self.restart_var = tk.BooleanVar()
        ttk.Checkbutton(left, text="Restart server after crash", variable=self.restart_var).pack(anchor="w", pady=(8, 4))
        self._field(left, "Restart delay (seconds)", "restart_delay")
        ttk.Button(left, text="Save settings", command=self._save).pack(fill="x", pady=(12, 5))
        ttk.Label(left, text="Setup downloads official Vanilla Minecraft. Server property changes apply after a restart.", style="Muted.TLabel", wraplength=285, justify="left").pack(anchor="w", pady=(7, 0))

        right = ttk.Frame(body, style="Panel.TFrame", padding=14)
        right.pack(side="left", fill="both", expand=True)
        console_head = ttk.Frame(right, style="Panel.TFrame")
        console_head.pack(fill="x", pady=(0, 10))
        ttk.Label(console_head, text="LIVE CONSOLE", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Button(console_head, text="Clear", padding=(8, 4), command=self._clear).pack(side="right")
        self.console = tk.Text(right, bg="#080d18", fg="#c5d1e5", insertbackground=TEXT, relief="flat", wrap="word", font=("Cascadia Mono", 9), padx=12, pady=10, state="disabled")
        self.console.pack(fill="both", expand=True)
        self.console.tag_configure("minecraft", foreground="#cad5e8")
        self.console.tag_configure("playit", foreground="#91b9ff")
        self.console.tag_configure("system", foreground="#7fe0ac")
        self.console.tag_configure("error", foreground="#ff929c")
        command = tk.Frame(right, bg="#080d18", highlightbackground="#2a3852", highlightthickness=1)
        command.pack(fill="x", pady=(10, 0), ipady=5)
        tk.Label(command, text=">", bg="#080d18", fg=GREEN, font=("Cascadia Mono", 12, "bold")).pack(side="left", padx=(12, 8))
        self.command_entry = tk.Entry(
            command, bg="#080d18", fg=TEXT, insertbackground=GREEN, insertwidth=2,
            insertontime=600, insertofftime=350, relief="flat", borderwidth=0,
            highlightthickness=0, font=("Cascadia Mono", 10),
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=5)
        self.command_entry.bind("<Return>", lambda _e: self._send_command())
        self.command_entry.bind("<Up>", self._history_up)
        self.command_entry.bind("<Down>", self._history_down)
        self.root.bind("<Control-l>", lambda _e: self._clear())

    def _card(self, parent, title, variable, symbol, color):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=(16, 13))
        ttk.Label(frame, text=symbol, style="Panel.TLabel", foreground=color, font=("Segoe UI", 17)).pack(side="left", padx=(0, 11))
        stack = ttk.Frame(frame, style="Panel.TFrame")
        stack.pack(side="left", fill="x", expand=True)
        ttk.Label(stack, text=title, style="Muted.TLabel", font=("Segoe UI Semibold", 8)).pack(anchor="w")
        ttk.Label(stack, textvariable=variable, style="Panel.TLabel", font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(3, 0))
        return frame

    def _scroll_main(self, event):
        self.main_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _field(self, parent, label, key, browse=None):
        ttk.Label(parent, text=label, style="Panel.TLabel", foreground=MUTED).pack(anchor="w", pady=(8, 4))
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x")
        var = tk.StringVar()
        self.entries[key] = var
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(row, text="…", padding=(8, 6), command=lambda: self._browse(key, browse)).pack(side="left", padx=(5, 0))

    def _browse(self, key, kind):
        if kind == "folder":
            value = filedialog.askdirectory(initialdir=self.entries[key].get() or str(Path.home()))
        else:
            value = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if value:
            self.entries[key].set(value)

    def _load_settings(self):
        for key, variable in self.entries.items():
            variable.set(str(self.config.get(key, "")))
        self.restart_var.set(bool(self.config.get("auto_restart", False)))

    def _eula_path(self) -> Path:
        return Path(self.entries["server_dir"].get()).expanduser() / "eula.txt"

    def _eula_is_accepted(self) -> bool:
        try:
            return any(line.strip().lower() == "eula=true" for line in self._eula_path().read_text(encoding="utf-8").splitlines())
        except OSError:
            return False

    def _save(self):
        self.config.update({key: variable.get().strip() for key, variable in self.entries.items()})
        try:
            self.config["memory_gb"] = int(self.config["memory_gb"])
            self.config["restart_delay"] = int(self.config["restart_delay"])
            self.config["auto_restart"] = self.restart_var.get()
            if not 1 <= self.config["memory_gb"] <= 64:
                raise ValueError("Memory must be between 1 and 64 GB.")
            if not 1 <= self.config["restart_delay"] <= 300:
                raise ValueError("Restart delay must be between 1 and 300 seconds.")
            save_config(self.config)
            self.status_text.set("Settings saved")
            self.events.put({"type": "log", "message": "Settings saved.", "source": "system"})
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror("Settings", str(exc))
            return False

    def _setup(self):
        if not self._save():
            return
        self.status_text.set("Setting up…")
        self.manager.send("setup", config=self.config)

    def _start(self):
        if not self._save():
            return
        self._run_with_eula("start")

    def _restart(self):
        if not self._save():
            return
        self._run_with_eula("restart")

    def _run_with_eula(self, action: str):
        if self._eula_is_accepted():
            self._send_server_action(action)
            return

        window = tk.Toplevel(self.root)
        window.title("Minecraft EULA")
        window.geometry("480x245")
        window.resizable(False, False)
        window.configure(bg=BG)
        window.transient(self.root)
        window.grab_set()
        content = ttk.Frame(window, padding=22)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Minecraft Server EULA", style="Title.TLabel", font=("Segoe UI Semibold", 17)).pack(anchor="w")
        ttk.Label(content, text="Before the server starts for the first time, review the Minecraft EULA. You can open it here.", wraplength=430, justify="left").pack(anchor="w", pady=(10, 8))
        link = ttk.Label(content, text="Read the Minecraft EULA", foreground=BLUE, cursor="hand2")
        link.pack(anchor="w", pady=(0, 8))
        link.bind("<Button-1>", lambda _event: webbrowser.open("https://www.minecraft.net/en-us/eula"))
        accepted = tk.BooleanVar(value=False)
        ttk.Checkbutton(content, text="I have read and accept the Minecraft EULA", variable=accepted).pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(content)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="right", padx=(8, 0))
        accept_button = ttk.Button(buttons, text="Accept and Start", style="Green.TButton", state="disabled")
        accept_button.pack(side="right")

        def toggle_accept(*_args):
            accept_button.configure(state="normal" if accepted.get() else "disabled")

        def accept_and_continue():
            if not self._write_eula(True):
                return
            window.destroy()
            self._send_server_action(action)

        accepted.trace_add("write", toggle_accept)
        accept_button.configure(command=accept_and_continue)
        window.bind("<Escape>", lambda _event: window.destroy())

    def _send_server_action(self, action: str):
        if action == "restart" and not self._host_supports_restart:
            self._restart_pending_config = self.config.copy()
            self.manager.send("stop")
        else:
            self.manager.send(action, config=self.config)

    def _write_eula(self, accepted: bool) -> bool:
        path = self._eula_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                lines = ["# Review the Minecraft EULA before accepting."]
            eula_line = f"eula={'true' if accepted else 'false'}"
            for index, line in enumerate(lines):
                if line.strip().lower().startswith("eula="):
                    lines[index] = eula_line
                    break
            else:
                lines.append(eula_line)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.events.put({"type": "log", "message": "Minecraft EULA accepted in the first-start prompt.", "source": "system"})
            return True
        except OSError as exc:
            messagebox.showerror("Minecraft EULA", f"Could not save the EULA choice: {exc}")
            return False

    def _open_properties(self):
        folder = Path(self.entries["server_dir"].get()).expanduser()
        path = folder / "server.properties"
        if not path.exists():
            messagebox.showinfo("Server properties", "Choose Set up server first to create server.properties.")
            return
        values, _lines = read_properties(path)
        window = tk.Toplevel(self.root)
        window.title("Server Properties — BlockHost")
        window.geometry("980x700")
        window.minsize(850, 560)
        window.configure(bg=BG)
        window.transient(self.root)

        viewport = ttk.Frame(window)
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, borderwidth=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas, padding=22)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _event: canvas.bind_all("<MouseWheel>", self._scroll_main))
        ttk.Label(content, text="Server Properties", style="Title.TLabel").pack(anchor="w")
        ttk.Label(content, text="Choose switches and values. Changes take effect after the next server restart. Keep the port matched to the Playit tunnel destination.", foreground=MUTED, wraplength=900).pack(anchor="w", pady=(3, 16))
        columns = ttk.Frame(content)
        columns.pack(fill="both", expand=True)
        switches = ttk.LabelFrame(columns, text="Switches", padding=12)
        switches.pack(side="left", fill="both", expand=True, padx=(0, 8))
        values_frame = ttk.LabelFrame(columns, text="Values", padding=12)
        values_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        toggle_labels = {
            "online-mode": "Require authenticated accounts",
            "pvp": "Player versus player combat",
            "allow-flight": "Allow flight",
            "allow-nether": "Allow Nether",
            "enable-command-block": "Enable command blocks",
            "spawn-monsters": "Spawn hostile mobs",
            "spawn-animals": "Spawn animals",
            "spawn-npcs": "Spawn villagers",
            "white-list": "Enable whitelist",
            "enforce-whitelist": "Enforce whitelist on join",
            "hardcore": "Hardcore mode",
            "force-gamemode": "Force default game mode on join",
            "enable-status": "Show server status to the server list",
        }
        toggle_vars = {}
        for key, label in toggle_labels.items():
            var = tk.BooleanVar(value=values.get(key, "false").lower() == "true")
            toggle_vars[key] = var
            ttk.Checkbutton(switches, text=label, variable=var).pack(anchor="w", pady=7)

        property_vars = {}
        fields = [
            ("server-port", "Server port", None),
            ("max-players", "Maximum players", None),
            ("view-distance", "View distance", None),
            ("simulation-distance", "Simulation distance", None),
            ("spawn-protection", "Spawn protection radius", None),
            ("difficulty", "Difficulty", ("peaceful", "easy", "normal", "hard")),
            ("gamemode", "Default game mode", ("survival", "creative", "adventure", "spectator")),
            ("level-name", "World folder name", None),
            ("level-seed", "World seed", None),
            ("motd", "Server list description", None),
        ]
        for key, label, choices in fields:
            ttk.Label(values_frame, text=label, style="Panel.TLabel", foreground=MUTED).pack(anchor="w", pady=(4, 2))
            var = tk.StringVar(value=values.get(key, ""))
            property_vars[key] = var
            if choices:
                ttk.Combobox(values_frame, textvariable=var, values=choices, state="readonly").pack(fill="x", pady=(0, 3))
            else:
                ttk.Entry(values_frame, textvariable=var).pack(fill="x", pady=(0, 3))

        footer = ttk.Frame(content)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(footer, text="Other server.properties settings are preserved.", foreground=MUTED).pack(side="left")

        def save_server_properties():
            updates = {key: "true" if var.get() else "false" for key, var in toggle_vars.items()}
            updates.update({key: var.get().strip() for key, var in property_vars.items()})
            try:
                port = int(updates["server-port"])
                players = int(updates["max-players"])
                view = int(updates["view-distance"])
                simulation = int(updates["simulation-distance"])
                spawn = int(updates["spawn-protection"])
                if not 1 <= port <= 65535:
                    raise ValueError("Server port must be between 1 and 65535.")
                if not 1 <= players <= 10000:
                    raise ValueError("Maximum players must be between 1 and 10000.")
                if not 2 <= view <= 32 or not 2 <= simulation <= 32:
                    raise ValueError("View and simulation distance must be between 2 and 32 chunks.")
                if not 0 <= spawn <= 64:
                    raise ValueError("Spawn protection must be between 0 and 64.")
                if not updates["level-name"]:
                    raise ValueError("World folder name cannot be empty.")
                write_properties(path, updates)
                self.events.put({"type": "log", "message": "Saved server.properties. Restart the server for changes to take effect.", "source": "system"})
                window.destroy()
            except (ValueError, OSError) as exc:
                messagebox.showerror("Server properties", str(exc), parent=window)

        ttk.Button(footer, text="Save changes", style="Green.TButton", command=save_server_properties).pack(side="right")

    def _send_command(self):
        value = self.command_entry.get().strip()
        if value:
            self.manager.send("command", command=value)
            if not self.command_history or self.command_history[-1] != value:
                self.command_history.append(value)
            self.history_index = None
            self.command_entry.delete(0, "end")
            self.command_entry.focus_set()
        return "break"

    def _focus_command_entry(self):
        if self.root.winfo_exists():
            self.command_entry.focus_set()

    def _history_up(self, _event=None):
        if not self.command_history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.command_history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self._show_history_item()
        return "break"

    def _history_down(self, _event=None):
        if self.history_index is None:
            return "break"
        if self.history_index >= len(self.command_history) - 1:
            self.history_index = None
            self.command_entry.delete(0, "end")
        else:
            self.history_index += 1
            self._show_history_item()
        return "break"

    def _show_history_item(self):
        self.command_entry.delete(0, "end")
        self.command_entry.insert(0, self.command_history[self.history_index])

    def _open_folder(self):
        folder = Path(self.entries["server_dir"].get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["explorer", str(folder)])
        except OSError as exc:
            messagebox.showerror("Open folder", str(exc))

    def _clear(self):
        self.console.configure(state="normal"); self.console.delete("1.0", "end"); self.console.configure(state="disabled")

    def _on_manager_event(self, event: dict):
        self.events.put(event)

    def _drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event.get("type")
                if kind == "log":
                    self.console.configure(state="normal")
                    self.console.insert("end", event.get("message", "") + "\n", event.get("source", "system"))
                    self.console.see("end")
                    self.console.configure(state="disabled")
                elif kind == "state":
                    state, message = event.get("state"), event.get("message", "")
                    if state == "address":
                        self.address_text.set(message)
                    else:
                        self.status_text.set(message)
                        if state == "starting":
                            self.server_var.set("Starting")
                        elif state == "recovering":
                            self.server_var.set(message)
                        elif state == "stopping":
                            self.server_var.set("Stopping")
                        elif state == "ready":
                            self.server_var.set("Ready")
                        elif state in ("stopped", "error", "eula"):
                            self.server_var.set("Stopped")
                        if state == "error":
                            self.status_text.set("Needs attention")
                elif kind == "snapshot":
                    self._host_supports_restart = "restart" in event.get("capabilities", [])
                    self.server_var.set(event.get("server", "Stopped"))
                    self.tunnel_var.set(event.get("tunnel", "Not running"))
                    self.address_text.set(event.get("address", "No public address yet"))
                    if self._restart_pending_config and event.get("server") == "Stopped" and event.get("tunnel") == "Not running":
                        pending = self._restart_pending_config
                        self._restart_pending_config = None
                        self.manager.send("start", config=pending)
                elif kind == "connected":
                    self.status_text.set("Background manager connected")
                elif kind == "disconnected":
                    self.status_text.set("Reconnecting to background manager…")
                elif kind == "error":
                    self.status_text.set("Needs attention")
                    self.console.configure(state="normal")
                    self.console.insert("end", event.get("message", "Manager error") + "\n", "error")
                    self.console.see("end")
                    self.console.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _close(self):
        self.manager.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
