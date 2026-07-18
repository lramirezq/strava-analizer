"""Strava Analyzer — standalone entry point for packaged app."""

import os
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

    # Set BASE_DIR to user data directory
    os.environ["STRAVA_ANALYZER_DATA"] = str(data_dir)

    # Load .env from data dir if exists
    env_file = data_dir / ".env"
    if env_file.exists():
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


def open_browser():
    """Open browser after a short delay to let server start."""
    time.sleep(3)
    webbrowser.open("http://localhost:8050")


def main():
    """Start the Strava Analyzer app."""
    setup_environment()

    # Ensure templates are findable
    if getattr(sys, "_MEIPASS", None):
        os.chdir(sys._MEIPASS)

    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start uvicorn server
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8050, log_level="warning")


if __name__ == "__main__":
    main()
