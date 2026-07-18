# CONTEXT — Strava Training Analyzer

## Project

Personal training analytics platform that connects to Strava API to download, organize, and analyze cycling and weight training data.

## Owner

Luis Ramirez (LRQ Strava app)

## Domain Terms

| Term | Definition |
|---|---|
| FTP | Functional Threshold Power — max sustained power for 1 hour. Current: 197W |
| TSS | Training Stress Score — intensity × duration normalized to FTP |
| CTL | Chronic Training Load — fitness (42-day rolling avg of TSS) |
| ATL | Acute Training Load — fatigue (7-day rolling avg of TSS) |
| TSB | Training Stress Balance — form (CTL - ATL). Negative = fatigued |
| IF | Intensity Factor — normalized power / FTP |
| NP | Normalized Power — weighted average power accounting for variability |
| VI | Variability Index — NP / avg power. Higher = more surges |
| Relative Effort | Strava's proprietary HR-based effort metric (similar to TRIMP) |
| HR Zones | 5-zone model based on max HR or LTHR |
| Power Zones | Based on FTP (Active Recovery, Endurance, Tempo, Threshold, VO2max, Anaerobic, Neuromuscular) |
| Brevet | Long-distance organized cycling event (200-1200km) |
| Decoupling | HR drift relative to power — indicates aerobic fitness or fatigue |

## Key Metrics

- **Primary sport:** Road cycling
- **Secondary:** Weight training (tracked in Strava but without set/rep detail)
- **Current FTP:** 194W (Strava config)
- **HR Zones:** 5-zone model
- **Target event:** Brevet 300km / 2500m elevation
- **Key concern:** A ride produced Relative Effort of 709 on a route previously done with much less effort — need to understand why and prevent it on the brevet

## Architecture

- **Backend:** Python (FastAPI)
- **Analysis:** Pandas + NumPy
- **Frontend:** HTML + Chart.js (lightweight dashboard)
- **Storage:** SQLite (local)
- **Auth:** Strava OAuth2 (token stored locally)
- **Deployment:** Local machine (dev/personal use)

## Strava API

- App name: LRQ
- OAuth2 flow: authorization code grant
- Scopes needed: read, read_all, activity:read_all
- Rate limits: 100 requests/15min, 1000 requests/day
