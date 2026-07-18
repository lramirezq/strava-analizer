# Feature Spec: Training Dashboard

## Problem

Need a web dashboard to visualize training load, weekly TSS, fitness/fatigue/form (CTL/ATL/TSB), and compare activities to identify anomalies like the 709 relative effort ride.

## Actors

- **User (Luis):** Views dashboard in browser, selects date ranges, compares rides

## Rules

1. Dashboard served locally on port 8050 via FastAPI
2. TSS calculated from HR when no power meter: hrTSS = (duration × avgHR × IF_hr) / (FTP_hr × 3600) × 100
3. CTL = 42-day exponential weighted avg of daily TSS
4. ATL = 7-day exponential weighted avg of daily TSS
5. TSB = CTL - ATL (positive = fresh, negative = fatigued)
6. Weekly summary shows total TSS, hours, activity count, avg HR
7. Activity comparison shows side-by-side metrics with deltas

## Acceptance Criteria

- AC1: WHEN user visits localhost:8050 THEN dashboard renders with charts
- AC2: WHEN dashboard loads THEN CTL/ATL/TSB chart shows full history
- AC3: WHEN dashboard loads THEN weekly TSS bar chart is visible
- AC4: WHEN user views activity list THEN top efforts are highlighted
- AC5: WHEN page loads THEN all data comes from local SQLite (no external calls)

## Status: Implemented
