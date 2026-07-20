"""Strava Analyzer — standalone entry point for packaged app."""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def get_data_dir() -> Path:
    """Get the user data directory for storing config, DB, tokens."""
    data_dir = Path.home() / ".strava-analyzer"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def setup_environment():
    """Set up environment for the packaged app."""
    data_dir = get_data_dir()
    os.environ["STRAVA_ANALYZER_DATA"] = str(data_dir)

    # Load .env from data dir if exists
    env_file = data_dir / ".env"
    if env_file.exists():
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


def kill_port(port: int):
    """Kill any process using the given port."""
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True, text=True,
    )
    pids = result.stdout.strip()
    if pids:
        for pid in pids.split("\n"):
            pid = pid.strip()
            if pid:
                subprocess.run(["kill", "-9", pid], capture_output=True)
        time.sleep(1)


def open_browser_when_ready():
    """Wait for server to be ready, then open browser."""
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen("http://localhost:8050/", timeout=1)
            webbrowser.open("http://localhost:8050")
            return
        except Exception:
            time.sleep(1)
    # Fallback: open anyway
    webbrowser.open("http://localhost:8050")


def run_server():
    """Run the uvicorn server (blocking)."""
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8050, log_level="warning")


def main():
    """Start the Strava Analyzer app."""
    setup_environment()
    kill_port(8050)

    # Ensure templates are findable
    if getattr(sys, "_MEIPASS", None):
        os.chdir(sys._MEIPASS)

    # Open browser in background thread (waits for server)
    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    # Run server in main thread (this blocks, which is fine — it keeps the process alive)
    run_server()


if __name__ == "__main__":
    main()
