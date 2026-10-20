"""Minecraft + playit desktop manager entry point."""
import sys

from mcmanager.ui import main

if __name__ == "__main__":
    if "--host" in sys.argv:
        from mcmanager.host import main as run_host
        run_host()
    else:
        main()
