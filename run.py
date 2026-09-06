#!/usr/bin/env python3
"""Source entrypoint and PyInstaller entrypoint."""
import argparse
import signal
import sys
import threading
import webbrowser
from pathlib import Path

from myai.engine import Engine
from myai.hardware import detect_hardware
from myai.server import App, make_server


def main():
    parser = argparse.ArgumentParser(description="MyAi portable offline chat")
    parser.add_argument("--root", type=Path, help="Portable workspace folder (default: beside app)")
    parser.add_argument("--port", type=int, default=0, help="UI port; default chooses a free port")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    frozen = getattr(sys, "frozen", False)
    root = (args.root or (Path(sys.executable).parent if frozen else Path(__file__).parent)).resolve()
    assets = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "web"
    # Detect once at startup; Engine still detects lazily when embedded directly.
    app = App(root, assets, Engine(root, hardware=detect_hardware()))
    server = make_server(app, args.port)
    url = f"http://127.0.0.1:{server.server_port}/#token={app.token}"
    print(f"MyAi 0.2.0 | workspace: {root}\nOpen this private session URL:\n{url}\nKeep this terminal open. Press Ctrl+C to stop before ejecting the drive.", flush=True)

    def stop(*_):
        app.cancel.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        app.media.close()
        app.engine.stop()
        # Allow the request thread to persist an interrupted response before exit.
        with app.busy:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
