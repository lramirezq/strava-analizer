"""Training metrics calculations: TSS, CTL, ATL, TSB."""

import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.config import DB_PATH

# Luis's current FTP
FTP = 197
MAX_HR = 195
RESTING_HR = 60  # estimate — can be tuned


def load_activities_df() -> pd.DataFrame:
    """Load all activities from SQLite into a DataFrame."""
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(
        """
        SELECT id, name, type, sport_type, start_date, distance,
               total_elevation_gain, moving_time, elapsed_time,
               average_speed, average_watts, weighted_average_watts,
               average_heartrate, max_heartrate, suffer_score,
               kilojoules, has_power_meter, trainer
        FROM activities
        ORDER BY start_date
        """,
        conn,
    )
    conn.close()
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.tz_localize(None)
    df["date"] = df["start_date"].dt.date
    return df


def estimate_tss(row: pd.Series) -> float:
    """Estimate TSS for an activity.

    Uses power-based TSS if available, otherwise HR-based estimate.
    Formula: TSS = (duration_s * NP * IF) / (FTP * 3600) * 100
    HR-based: hrTSS uses HR reserve method as proxy for intensity.
    """
    duration_s = row.get("moving_time", 0) or 0
    if duration_s == 0:
        return 0.0

    # Power-based TSS (preferred)
    np_watts = row.get("weighted_average_watts")
    if np_watts and np_watts > 0:
        intensity = np_watts / FTP
        return (duration_s * np_watts * intensity) / (FTP * 3600) * 100

    # HR-based TSS estimate (when no power meter)
    avg_hr = row.get("average_heartrate")
    if avg_hr and avg_hr > 0:
        # HR reserve fraction as intensity proxy
        hr_reserve = (avg_hr - RESTING_HR) / (MAX_HR - RESTING_HR)
        hr_reserve = max(0.0, min(1.0, hr_reserve))
        # Scale: intensity factor from HR
        intensity = hr_reserve * 1.1  # slight upward bias since HR lags effort
        return (duration_s / 3600) * intensity * intensity * 100

    # Fallback: use Strava's suffer_score as rough TSS proxy
    if row.get("suffer_score"):
        return float(row["suffer_score"]) * 0.5

    return 0.0


def compute_training_load(df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily TSS, CTL, ATL, TSB from activities."""
    df = df.copy()
    df["tss"] = df.apply(estimate_tss, axis=1)

    # Aggregate to daily TSS
    daily = df.groupby("date").agg({"tss": "sum"}).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])

    # Fill all days (including rest days with 0 TSS)
    if daily.empty:
        return pd.DataFrame(columns=["date", "tss", "ctl", "atl", "tsb"])

    date_range = pd.date_range(start=daily["date"].min(), end=daily["date"].max())
    daily = daily.set_index("date").reindex(date_range, fill_value=0).reset_index()
    daily.columns = ["date", "tss"]

    # Exponential weighted averages
    # CTL: 42-day time constant, ATL: 7-day time constant
    daily["ctl"] = daily["tss"].ewm(span=42, adjust=False).mean()
    daily["atl"] = daily["tss"].ewm(span=7, adjust=False).mean()
    daily["tsb"] = daily["ctl"] - daily["atl"]

    return daily


def get_weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weekly training summary."""
    df = df.copy()
    df["tss"] = df.apply(estimate_tss, axis=1)
    df["week"] = df["start_date"].dt.isocalendar().week
    df["year"] = df["start_date"].dt.year
    df["year_week"] = df["start_date"].dt.to_period("W")

    weekly = df.groupby("year_week").agg(
        activities=("id", "count"),
        total_tss=("tss", "sum"),
        total_hours=("moving_time", lambda x: x.sum() / 3600),
        avg_hr=("average_heartrate", "mean"),
        total_elevation=("total_elevation_gain", "sum"),
        total_distance_km=("distance", lambda x: x.sum() / 1000),
    ).reset_index()

    weekly["year_week_str"] = weekly["year_week"].astype(str)
    return weekly


def project_rest_days(daily: pd.DataFrame, days_ahead: int = 7) -> pd.DataFrame:
    """Project CTL/ATL/TSB forward assuming rest days (TSS=0).

    Uses exponential decay:
    - CTL decays with time constant 42 days: factor = 1 - 2/(42+1)
    - ATL decays with time constant 7 days: factor = 1 - 2/(7+1)
    """
    if daily.empty:
        return pd.DataFrame(columns=["date", "tss", "ctl", "atl", "tsb", "projected"])

    last_row = daily.iloc[-1]
    last_date = last_row["date"]
    ctl = last_row["ctl"]
    atl = last_row["atl"]

    ctl_decay = 1 - 2 / 43  # span=42
    atl_decay = 1 - 2 / 8   # span=7

    projections = []
    for d in range(1, days_ahead + 1):
        ctl = ctl * ctl_decay
        atl = atl * atl_decay
        tsb = ctl - atl
        projections.append({
            "date": last_date + pd.Timedelta(days=d),
            "tss": 0.0,
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
            "projected": True,
        })

    proj_df = pd.DataFrame(projections)

    # Add projected=False to existing data
    daily = daily.copy()
    daily["projected"] = False

    return pd.concat([daily, proj_df], ignore_index=True)
