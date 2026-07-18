"""Strava API client with OAuth2 token management."""

import json
import logging
import time

import httpx

from app.config import (
    RATE_LIMIT_WARNING_THRESHOLD,
    STRAVA_API_BASE,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_TOKEN_URL,
    TOKENS_PATH,
)

logger = logging.getLogger(__name__)


class StravaAuthError(Exception):
    """Raised when authentication fails and re-auth is needed."""


def load_tokens() -> dict:
    """Load tokens from disk. Raises if not found."""
    if not TOKENS_PATH.exists():
        raise StravaAuthError(
            "No tokens found. Run 'python -m app.auth' to authenticate."
        )
    with open(TOKENS_PATH) as f:
        return json.load(f)


def save_tokens(tokens: dict) -> None:
    """Persist tokens to disk."""
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def is_token_expired(tokens: dict) -> bool:
    """Check if access token is expired (with 60s buffer)."""
    return time.time() >= (tokens.get("expires_at", 0) - 60)


def refresh_access_token(tokens: dict) -> dict:
    """Refresh the access token using the refresh token."""
    logger.info("Access token expired, refreshing...")
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise StravaAuthError(
            "Token refresh failed. Run 'python -m app.auth' to re-authenticate."
        )
    new_tokens = response.json()
    tokens["access_token"] = new_tokens["access_token"]
    tokens["refresh_token"] = new_tokens["refresh_token"]
    tokens["expires_at"] = new_tokens["expires_at"]
    save_tokens(tokens)
    logger.info("Token refreshed successfully.")
    return tokens


def get_valid_token() -> str:
    """Return a valid access token, refreshing if necessary."""
    tokens = load_tokens()
    if is_token_expired(tokens):
        tokens = refresh_access_token(tokens)
    return tokens["access_token"]


def _check_rate_limit(headers: httpx.Headers) -> None:
    """Log warning if rate limit is getting low."""
    usage = headers.get("X-RateLimit-Usage")
    if usage:
        parts = usage.split(",")
        if len(parts) == 2:
            used_15min = int(parts[0])
            used_daily = int(parts[1])
            remaining_short = 100 - used_15min
            remaining_daily = 1000 - used_daily
            if remaining_short <= RATE_LIMIT_WARNING_THRESHOLD:
                logger.warning(
                    f"Rate limit: {remaining_short} requests left (15min)"
                )
            if remaining_daily <= RATE_LIMIT_WARNING_THRESHOLD * 5:
                logger.warning(
                    f"Rate limit: {remaining_daily} requests left (daily)"
                )


def fetch_activities(
    after: int | None = None, page: int = 1, per_page: int = 200
) -> list[dict]:
    """Fetch a page of activities from Strava API."""
    token = get_valid_token()
    params: dict = {"page": page, "per_page": per_page}
    if after:
        params["after"] = after

    response = httpx.get(
        f"{STRAVA_API_BASE}/athlete/activities",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )

    _check_rate_limit(response.headers)

    if response.status_code == 401:
        raise StravaAuthError(
            "Access denied. Run 'python -m app.auth' to re-authenticate."
        )
    if response.status_code == 429:
        logger.error("Rate limited by Strava. Try again later.")
        raise RuntimeError("Strava API rate limit exceeded.")
    if response.status_code != 200:
        logger.error(f"Strava API error: HTTP {response.status_code}")
        raise RuntimeError(f"Strava API returned HTTP {response.status_code}")

    return response.json()


def fetch_activity_zones(activity_id: int) -> list[dict]:
    """Fetch zone distribution for a single activity from Strava API."""
    token = get_valid_token()
    response = httpx.get(
        f"{STRAVA_API_BASE}/activities/{activity_id}/zones",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    _check_rate_limit(response.headers)

    if response.status_code == 401:
        raise StravaAuthError("Access denied. Run 'python -m app.auth' to re-authenticate.")
    if response.status_code == 429:
        raise RuntimeError("Strava API rate limit exceeded.")
    if response.status_code != 200:
        logger.warning(f"Zones not available for activity {activity_id}: HTTP {response.status_code}")
        return []

    return response.json()


def fetch_activity_streams(activity_id: int, keys: str = "time,heartrate,watts,distance") -> dict:
    """Fetch second-by-second streams for an activity.

    Returns dict with stream type as key and data list as value.
    """
    token = get_valid_token()
    response = httpx.get(
        f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
        headers={"Authorization": f"Bearer {token}"},
        params={"keys": keys, "key_type": "time"},
        timeout=60,
    )

    _check_rate_limit(response.headers)

    if response.status_code == 401:
        raise StravaAuthError("Access denied. Run 'python -m app.auth' to re-authenticate.")
    if response.status_code == 429:
        raise RuntimeError("Strava API rate limit exceeded.")
    if response.status_code != 200:
        logger.warning(f"Streams not available for activity {activity_id}: HTTP {response.status_code}")
        return {}

    result = {}
    for stream in response.json():
        result[stream["type"]] = stream["data"]
    return result
