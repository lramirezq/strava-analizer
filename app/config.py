"""Application configuration — loaded from environment variables."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Determine base directory
# In packaged mode: uses ~/.strava-analyzer for data
# In development: uses the project directory
if os.environ.get("STRAVA_ANALYZER_DATA"):
    BASE_DIR = Path(os.environ["STRAVA_ANALYZER_DATA"])
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present (from data dir or project dir)
load_dotenv(BASE_DIR / ".env")

# Strava OAuth2 — MUST be set in .env or environment
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")

# Paths
DB_PATH = BASE_DIR / "strava.db"
TOKENS_PATH = BASE_DIR / "tokens.json"

# Strava API
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# OAuth redirect (localhost is whitelisted by Strava)
OAUTH_REDIRECT_URI = "http://localhost:8000/callback"
OAUTH_SCOPES = "read,activity:read_all"

# Rate limit thresholds
RATE_LIMIT_WARNING_THRESHOLD = 10


def validate_config() -> None:
    """Fail fast if required config is missing."""
    missing = []
    if not STRAVA_CLIENT_ID:
        missing.append("STRAVA_CLIENT_ID")
    if not STRAVA_CLIENT_SECRET:
        missing.append("STRAVA_CLIENT_SECRET")
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Set them in a .env file or export them in your shell.")
        sys.exit(1)
