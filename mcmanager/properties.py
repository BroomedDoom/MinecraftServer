from __future__ import annotations

from pathlib import Path


DEFAULT_PROPERTIES = {
    "online-mode": "true",
    "pvp": "true",
    "allow-flight": "false",
    "allow-nether": "true",
    "enable-command-block": "false",
    "spawn-monsters": "true",
    "spawn-animals": "true",
    "spawn-npcs": "true",
    "white-list": "false",
    "enforce-whitelist": "false",
    "hardcore": "false",
    "server-port": "25565",
    "max-players": "20",
    "view-distance": "10",
    "simulation-distance": "10",
    "difficulty": "easy",
    "gamemode": "survival",
    "level-name": "world",
    "level-seed": "",
    "motd": "Minecraft Server",
    "spawn-protection": "16",
}


def read_properties(path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    values = DEFAULT_PROPERTIES.copy()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values, lines


def write_properties(path: Path, updates: dict[str, str]) -> None:
    _values, lines = read_properties(path)
    remaining = dict(updates)
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "!")) and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
