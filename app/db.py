"""SQLite database initialization and access."""

import sqlite3
from datetime import datetime, timezone

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    sport_type TEXT,
    start_date TEXT NOT NULL,
    distance REAL,
    total_elevation_gain REAL,
    moving_time INTEGER,
    elapsed_time INTEGER,
    average_speed REAL,
    max_speed REAL,
    average_watts REAL,
    max_watts REAL,
    weighted_average_watts REAL,
    average_heartrate REAL,
    max_heartrate REAL,
    suffer_score INTEGER,
    kilojoules REAL,
    has_power_meter INTEGER,
    trainer INTEGER,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_zones (
    activity_id INTEGER NOT NULL,
    zone_type TEXT NOT NULL,
    zone_index INTEGER NOT NULL,
    zone_min REAL,
    zone_max REAL,
    time_seconds REAL NOT NULL,
    PRIMARY KEY (activity_id, zone_type, zone_index),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);
"""


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.close()


def get_latest_activity_timestamp() -> str | None:
    """Return the start_date of the most recent stored activity, or None."""
    conn = get_connection()
    cursor = conn.execute("SELECT MAX(start_date) FROM activities")
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return None


def upsert_activity(activity: dict) -> None:
    """Insert or update an activity record."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO activities (
            id, name, type, sport_type, start_date, distance,
            total_elevation_gain, moving_time, elapsed_time,
            average_speed, max_speed, average_watts, max_watts,
            weighted_average_watts, average_heartrate, max_heartrate,
            suffer_score, kilojoules, has_power_meter, trainer, synced_at
        ) VALUES (
            :id, :name, :type, :sport_type, :start_date, :distance,
            :total_elevation_gain, :moving_time, :elapsed_time,
            :average_speed, :max_speed, :average_watts, :max_watts,
            :weighted_average_watts, :average_heartrate, :max_heartrate,
            :suffer_score, :kilojoules, :has_power_meter, :trainer, :synced_at
        )
        """,
        {
            "id": activity["id"],
            "name": activity["name"],
            "type": activity["type"],
            "sport_type": activity.get("sport_type"),
            "start_date": activity.get("start_date_local", activity.get("start_date")),
            "distance": activity.get("distance"),
            "total_elevation_gain": activity.get("total_elevation_gain"),
            "moving_time": activity.get("moving_time"),
            "elapsed_time": activity.get("elapsed_time"),
            "average_speed": activity.get("average_speed"),
            "max_speed": activity.get("max_speed"),
            "average_watts": activity.get("average_watts"),
            "max_watts": activity.get("max_watts"),
            "weighted_average_watts": activity.get("weighted_average_watts"),
            "average_heartrate": activity.get("average_heartrate"),
            "max_heartrate": activity.get("max_heartrate"),
            "suffer_score": activity.get("suffer_score"),
            "kilojoules": activity.get("kilojoules"),
            "has_power_meter": int(activity.get("device_watts", False)),
            "trainer": int(activity.get("trainer", False)),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    conn.commit()
    conn.close()


def get_activity_count() -> int:
    """Return total number of stored activities."""
    conn = get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM activities")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def save_activity_zones(activity_id: int, zones_data: list[dict]) -> None:
    """Save zone distribution for an activity."""
    conn = get_connection()
    for zone_entry in zones_data:
        zone_type = zone_entry["type"]
        for i, bucket in enumerate(zone_entry.get("distribution_buckets", [])):
            conn.execute(
                """
                INSERT OR REPLACE INTO activity_zones
                (activity_id, zone_type, zone_index, zone_min, zone_max, time_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    zone_type,
                    i,
                    bucket.get("min"),
                    bucket.get("max") if bucket.get("max", -1) != -1 else None,
                    bucket.get("time", 0),
                ),
            )
    conn.commit()
    conn.close()


def get_activity_zones(activity_id: int) -> list[dict] | None:
    """Get zones for an activity. Returns None if not yet fetched."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT zone_type, zone_index, zone_min, zone_max, time_seconds "
        "FROM activity_zones WHERE activity_id = ? ORDER BY zone_type, zone_index",
        (activity_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    result = {}
    for row in rows:
        ztype = row[0]
        if ztype not in result:
            result[ztype] = []
        result[ztype].append({
            "zone": row[1] + 1,
            "min": row[2],
            "max": row[3],
            "time_seconds": row[4],
        })
    return result


def has_zones(activity_id: int) -> bool:
    """Check if zones have been fetched for this activity."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM activity_zones WHERE activity_id = ?", (activity_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0
