from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BlockHost" if FROZEN else RESOURCE_DIR
APP_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SERVER_DIR = (Path.home() / "Documents" / "BlockHost Server") if FROZEN else RESOURCE_DIR / "server"
JAVA_BUNDLE = RESOURCE_DIR / "runtime" / "java25" / "bin" / "java.exe"
PLAYIT_BUNDLE = RESOURCE_DIR / "tools" / "playit.exe"
DEFAULTS = {
    "server_dir": str(DEFAULT_SERVER_DIR),
    "minecraft_version": "latest",
    "server_type": "Vanilla",
    "memory_gb": 4,
    "java_path": str(JAVA_BUNDLE) if JAVA_BUNDLE.is_file() else "java",
    "playit_path": str(PLAYIT_BUNDLE) if PLAYIT_BUNDLE.is_file() else "",
    "auto_restart": False,
    "restart_delay": 10,
}
CONFIG_PATH = APP_DIR / "config.json"


def load_config() -> dict:
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config = {**DEFAULTS, **saved}
    except (OSError, json.JSONDecodeError):
        config = DEFAULTS.copy()
    # Prefer the installer-managed Java and playit binaries when settings still
    # contain the old generic/empty defaults. Preserve explicit user choices.
    if JAVA_BUNDLE.is_file() and config.get("java_path") in (None, "", "java"):
        config["java_path"] = str(JAVA_BUNDLE)
    if PLAYIT_BUNDLE.is_file() and not config.get("playit_path"):
        config["playit_path"] = str(PLAYIT_BUNDLE)
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
