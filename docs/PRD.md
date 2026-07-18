# PRD — Strava Training Analyzer

## Problem

A cyclist needs to understand his training load, detect when efforts are disproportionate to the route difficulty, and prepare for a 300km brevet without excessive post-ride fatigue. Current tools (Strava web) don't provide enough analysis depth or historical comparison.

## User

Single user (Luis Ramirez). Personal tool. No multi-user concerns.

## Goals

1. **Download and store** all historical Strava activities locally
2. **Calculate training metrics** (TSS, CTL, ATL, TSB, IF, NP, VI) from raw power/HR data
3. **Visualize evolution** over time — identify best months, performance drops, fitness peaks
4. **Compare similar activities** — same route, different conditions, explain effort differences
5. **Alert on overtraining signals** — TSB too negative, HR decoupling trends, excessive relative effort
6. **Project brevet readiness** — estimate effort for 300km/2500m based on current fitness

## Core Use Cases

### UC1: Sync Activities
Download all activities from Strava (initial bulk + incremental). Store raw data locally in SQLite.

### UC2: Weekly/Monthly Dashboard
Show TSS per week, CTL/ATL/TSB chart, time in HR/power zones distribution.

### UC3: Activity Comparison
Select two activities (same or similar route) and compare: avg power, NP, HR, decoupling, effort, weather conditions, pacing.

### UC4: Anomaly Detection
Flag activities where relative effort is significantly higher than expected given the route profile (distance + elevation vs historical performance on similar routes).

### UC5: Brevet Projection
Given target route (300km, 2500m), estimate: required time, expected TSS, recommended pacing strategy (IF target), predicted recovery time.

## Non-Goals (v1)

- No mobile app
- No social features
- No weight training rep/set tracking (Strava doesn't have it anyway)
- No real-time tracking
- No multi-user support

## Success Criteria

- All historical activities downloaded and queryable
- Dashboard loads in < 2 seconds
- Can identify WHY the 709 relative effort ride was anomalous
- Can produce a pacing plan for the 300km brevet

## Constraints

- Strava API rate limits: 100 req/15min, 1000/day
- Local deployment only
- Single user, no auth beyond Strava OAuth

## Status: APPROVED
