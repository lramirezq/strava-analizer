#!/bin/bash
# Strava Training Analyzer - Launcher
DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if already running
if lsof -i :8050 >/dev/null 2>&1; then
    open "http://localhost:8050"
    exit 0
fi

# Start server
cd "$DIR"
source .venv/bin/activate
uvicorn app.server:app --port 8050 --host 0.0.0.0 &
SERVER_PID=$!

# Wait for server to be ready
for i in {1..10}; do
    if curl -s http://localhost:8050 >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Open browser
open "http://localhost:8050"

# Keep running
wait $SERVER_PID
