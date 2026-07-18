"""OAuth2 authentication flow for Strava.

Run directly:
    python -m app.auth
"""

import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import (
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    STRAVA_AUTH_URL,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_TOKEN_URL,
    TOKENS_PATH,
    validate_config,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

_auth_code: str | None = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth2 redirect callback from Strava."""

    def do_GET(self) -> None:
        """Process the callback with authorization code."""
        global _auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h1>Authorization denied.</h1><p>Close this window.</p>"
            )
            logger.error("User denied authorization.")
            return

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h1>Authorized!</h1><p>Close this window and return to terminal.</p>"
            )
            logger.info("Authorization code received.")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error: no code received.</h1>")

    def log_message(self, format, *args) -> None:
        """Suppress default HTTP server logs."""


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if response.status_code != 200:
        logger.error(f"Token exchange failed: HTTP {response.status_code}")
        raise RuntimeError("Failed to exchange authorization code.")
    return response.json()


def run_auth_flow() -> None:
    """Run the full OAuth2 authorization flow."""
    global _auth_code
    validate_config()

    auth_url = (
        f"{STRAVA_AUTH_URL}"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&response_type=code"
        f"&approval_prompt=auto"
        f"&scope={OAUTH_SCOPES}"
    )

    print("\n🚴 Strava Authentication")
    print("=" * 40)
    print("\nOpening browser for authorization...\n")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")

    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8000), OAuthCallbackHandler)
    logger.info("Waiting for callback on http://localhost:8000 ...")
    server.handle_request()
    server.server_close()

    if not _auth_code:
        logger.error("No authorization code received. Aborting.")
        return

    logger.info("Exchanging code for tokens...")
    tokens = exchange_code_for_tokens(_auth_code)

    token_data = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
        "athlete_id": tokens.get("athlete", {}).get("id"),
    }
    with open(TOKENS_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

    athlete_name = tokens.get("athlete", {}).get("firstname", "Unknown")
    print(f"\n✅ Authenticated as: {athlete_name}")
    print(f"   Tokens saved to: {TOKENS_PATH}")
    print("\n   Now run: python -m app.sync")


if __name__ == "__main__":
    run_auth_flow()
