"""Tests for database operations."""

import sqlite3
from unittest.mock import patch

import pytest

from app.db import get_activity_count, get_latest_activity_timestamp, init_db, upsert_activity


def _make_activity(activity_id: int = 1, **overrides) -> dict:
    """Create a minimal activity dict for testing."""
    base = {
        "id": activity_id,
        "name": "Morning Ride",
        "type": "Ride",
        "sport_type": "MountainBikeRide",
        "start_date_local": "2026-07-15T07:30:00Z",
        "distance": 45000.0,
        "total_elevation_gain": 800.0,
        "moving_time": 5400,
        "elapsed_time": 6000,
        "average_speed": 8.3,
        "max_speed": 15.2,
        "average_watts": 180.0,
        "max_watts": 450,
        "weighted_average_watts": 195.0,
        "average_heartrate": 145.0,
        "max_heartrate": 178,
        "suffer_score": 120,
        "kilojoules": 972.0,
        "device_watts": True,
        "trainer": False,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary database for each test."""
    test_db = tmp_path / "test.db"
    with patch("app.db.DB_PATH", test_db):
        init_db()
        yield test_db


def test_init_db_creates_table(temp_db):
    """Activities table should exist after init."""
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='activities'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_upsert_inserts_new_activity(temp_db):
    """Upserting a new activity should insert it."""
    with patch("app.db.DB_PATH", temp_db):
        upsert_activity(_make_activity(activity_id=123))
        assert get_activity_count() == 1


def test_upsert_updates_on_duplicate(temp_db):
    """Upserting same ID should update, not duplicate."""
    with patch("app.db.DB_PATH", temp_db):
        upsert_activity(_make_activity(activity_id=123, name="Ride v1"))
        upsert_activity(_make_activity(activity_id=123, name="Ride v2"))
        assert get_activity_count() == 1


def test_latest_timestamp_empty(temp_db):
    """Should return None when no activities exist."""
    with patch("app.db.DB_PATH", temp_db):
        assert get_latest_activity_timestamp() is None


def test_latest_timestamp_returns_max(temp_db):
    """Should return the most recent start_date."""
    with patch("app.db.DB_PATH", temp_db):
        upsert_activity(_make_activity(activity_id=1, start_date_local="2026-07-10T08:00:00Z"))
        upsert_activity(_make_activity(activity_id=2, start_date_local="2026-07-15T08:00:00Z"))
        assert get_latest_activity_timestamp() == "2026-07-15T08:00:00Z"


def test_nullable_watts_fields(temp_db):
    """Activities without power data should store NULL."""
    with patch("app.db.DB_PATH", temp_db):
        activity = _make_activity(activity_id=99)
        activity["average_watts"] = None
        activity["max_watts"] = None
        activity["weighted_average_watts"] = None
        activity["device_watts"] = False
        upsert_activity(activity)
        assert get_activity_count() == 1
