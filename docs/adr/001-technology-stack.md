# ADR-001: Technology Stack Selection

## Status: Accepted

## Context

Need a personal training analytics app that connects to Strava, crunches cycling metrics, and presents them visually. Single user, local deployment.

## Decision

- **Backend:** Python + FastAPI (async, fast dev, excellent data science ecosystem)
- **Analysis:** Pandas + NumPy (standard for time-series and numerical analysis)
- **Frontend:** HTML + Chart.js (no framework overhead for a personal dashboard)
- **Storage:** SQLite (zero-config, single file, perfect for single-user local app)
- **Auth:** Strava OAuth2 tokens stored in local file (gitignored)

## Rationale

- Python dominates the data/analytics space — libraries for cycling metrics exist
- FastAPI is lightweight yet production-capable with async support
- SQLite eliminates infrastructure (no Postgres/Docker needed for personal use)
- Chart.js renders performant charts without a JS build step

## Consequences

- No horizontal scaling (acceptable for single-user)
- SQLite concurrent write limitations (irrelevant for single-user)
- Python's GIL not a concern for this workload
