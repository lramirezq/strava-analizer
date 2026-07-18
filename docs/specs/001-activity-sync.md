# Feature Spec: Strava Activity Sync

## Problem

Need to download all historical activities from Strava and store them locally in SQLite for offline analysis. This is the foundation — no dashboard or analysis works without data.

## Actors

- **User (Luis):** Triggers sync, provides OAuth authorization once

## Rules

1. OAuth2 flow: authorization_code grant → exchange for access_token + refresh_token
2. Tokens stored locally in `tokens.json` (gitignored)
3. Access tokens expire in 6 hours — auto-refresh using refresh_token before API calls
4. Activities fetched paginated (200 per page max, Strava API limit)
5. Initial sync: download ALL activities. Subsequent syncs: only new (after latest stored timestamp)
6. Store activity summary fields: id, name, type, distance, elevation, moving_time, elapsed_time, start_date, average_watts, max_watts, weighted_average_watts, average_heartrate, max_heartrate, suffer_score (relative effort), kilojoules, has_power_meter
7. Respect rate limits: 100 req/15min, 1000/day. Log remaining quota from response headers.
8. On API error: log details with correlation ID, fail gracefully (don't crash mid-sync)

## Acceptance Criteria

- AC1: WHEN user runs `python -m app.auth` THEN browser opens Strava authorization page AND after approval, tokens are saved to `tokens.json`
- AC2: WHEN tokens exist and are expired THEN the app auto-refreshes before making API calls
- AC3: WHEN user runs `python -m app.sync` THEN all activities are downloaded and stored in SQLite
- AC4: WHEN sync runs again THEN only activities newer than the latest stored are fetched
- AC5: WHEN Strava returns an error THEN the error is logged with context but no secrets/tokens are leaked in logs
- AC6: WHEN rate limit is approaching THEN remaining quota is logged as a warning

## Edge Cases

- Token refresh fails (user revoked access) → log error, prompt re-auth
- Network timeout during sync → retry current page up to 3 times, then stop with partial data saved
- Activity has no power data (indoor ride, weight training) → nullable fields stored as NULL
- Strava returns 429 (rate limited) → wait and retry with backoff

## Data Model

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,  -- Strava activity ID
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    sport_type TEXT,
    start_date TEXT NOT NULL,  -- ISO 8601
    distance REAL,  -- meters
    total_elevation_gain REAL,  -- meters
    moving_time INTEGER,  -- seconds
    elapsed_time INTEGER,  -- seconds
    average_speed REAL,  -- m/s
    max_speed REAL,  -- m/s
    average_watts REAL,
    max_watts REAL,
    weighted_average_watts REAL,  -- NP
    average_heartrate REAL,
    max_heartrate REAL,
    suffer_score INTEGER,  -- Relative Effort
    kilojoules REAL,
    has_power_meter INTEGER,  -- boolean
    trainer INTEGER,  -- boolean (indoor)
    synced_at TEXT NOT NULL  -- when we downloaded it
);
```

## Status: Implemented
