"""FastAPI web dashboard for training analytics."""

import math

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.db import init_db
from app.metrics import compute_training_load, get_weekly_summary, load_activities_df, project_rest_days

app = FastAPI(title="Strava Training Analyzer")


def _safe_round(value) -> int | None:
    """Round a value safely, returning None for NaN/None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(value)


def _safe_int(value) -> int | None:
    """Convert to int safely, returning None for NaN/None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(value)


@app.on_event("startup")
def startup():
    init_db()


@app.post("/api/sync")
def api_sync():
    """Trigger a re-sync of activities from Strava."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "app.sync"],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
        timeout=120,
    )
    if result.returncode != 0:
        return JSONResponse(
            {"status": "error", "message": "Sync failed. Check server logs."},
            status_code=500,
        )
    # Extract summary from output
    output = result.stdout.strip().split("\n")
    summary = [line.strip() for line in output if "✅" in line or "New" in line or "Total" in line]
    return JSONResponse({"status": "ok", "message": "\n".join(summary) or "Sync complete"})


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the main dashboard page, or setup if not configured."""
    from app.config import STRAVA_CLIENT_ID, TOKENS_PATH

    # If no credentials configured, redirect to setup
    if not STRAVA_CLIENT_ID:
        with open("app/templates/setup.html") as f:
            return f.read()

    # If no tokens yet, show setup with auth prompt
    if not TOKENS_PATH.exists():
        with open("app/templates/setup.html") as f:
            return f.read()

    with open("app/templates/dashboard.html") as f:
        return f.read()


@app.get("/setup", response_class=HTMLResponse)
def setup_page():
    """Serve the setup page."""
    with open("app/templates/setup.html") as f:
        return f.read()


@app.post("/api/setup")
async def api_setup(request: Request):
    """Save Strava credentials to .env file."""
    from app.config import BASE_DIR, OAUTH_REDIRECT_URI, OAUTH_SCOPES, STRAVA_AUTH_URL

    data = await request.json()
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()

    if not client_id or not client_secret:
        return JSONResponse({"message": "Client ID y Secret son requeridos."}, status_code=400)

    # Save to .env
    env_path = BASE_DIR / ".env"
    with open(env_path, "w") as f:
        f.write(f"STRAVA_CLIENT_ID={client_id}\n")
        f.write(f"STRAVA_CLIENT_SECRET={client_secret}\n")

    # Build auth URL for the user
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri=http://localhost:8050/oauth/callback"
        f"&response_type=code"
        f"&approval_prompt=auto"
        f"&scope=read,activity:read_all"
    )

    return JSONResponse({"status": "ok", "auth_url": auth_url})


@app.get("/oauth/callback")
def oauth_callback(code: str = "", error: str = ""):
    """Handle OAuth callback from Strava after setup."""
    import os

    import httpx
    from app.config import BASE_DIR, TOKENS_PATH

    if error:
        return HTMLResponse(f"<h1>Error: {error}</h1><p><a href='/setup'>Volver al setup</a></p>")

    if not code:
        return HTMLResponse("<h1>No authorization code received</h1><p><a href='/setup'>Volver</a></p>")

    # Read credentials from .env
    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")

    # If env vars not loaded yet, read from file
    if not client_id:
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            for line in open(env_path):
                if line.startswith("STRAVA_CLIENT_ID="):
                    client_id = line.split("=", 1)[1].strip()
                elif line.startswith("STRAVA_CLIENT_SECRET="):
                    client_secret = line.split("=", 1)[1].strip()

    # Exchange code for tokens
    response = httpx.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )

    if response.status_code != 200:
        return HTMLResponse(f"<h1>Token exchange failed</h1><p><a href='/setup'>Reintentar</a></p>")

    import json
    tokens = response.json()
    token_data = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
        "athlete_id": tokens.get("athlete", {}).get("id"),
    }
    with open(TOKENS_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

    athlete_name = tokens.get("athlete", {}).get("firstname", "")

    # Redirect to dashboard with success
    return HTMLResponse(f"""
        <html><body style="background:#0f1117;color:#e1e4e8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
        <div style="text-align:center">
            <h1>✅ Conectado como {athlete_name}!</h1>
            <p style="color:#8b949e;margin:16px 0">Redirigiendo al dashboard...</p>
            <script>setTimeout(()=>window.location='/', 2000)</script>
        </div></body></html>
    """)


@app.get("/api/readiness")
def api_readiness():
    """Return training readiness assessment based on current TSB and recent overreach."""
    from datetime import date, timedelta

    df = load_activities_df()
    daily = compute_training_load(df)

    # Project to today
    last_date = daily["date"].iloc[-1].date()
    today = date.today()
    days_to_project = (today - last_date).days

    ctl = daily["ctl"].iloc[-1]
    atl = daily["atl"].iloc[-1]

    # Decay to today
    for _ in range(days_to_project):
        ctl = ctl * (1 - 2 / 43)
        atl = atl * (1 - 2 / 8)

    tsb = ctl - atl

    # Check for recent overreach: any activity with suffer_score > 500
    # in the last 21 days that spiked ACWR > 1.5
    overreach_window = today - timedelta(days=21)
    recent_extreme = df[
        (df["start_date"].dt.date >= overreach_window)
        & (df["suffer_score"].notna())
        & (df["suffer_score"] > 500)
    ]

    overreach_active = False
    overreach_days_ago = None
    overreach_recovery_days = 0

    if not recent_extreme.empty:
        last_extreme = recent_extreme.sort_values("start_date", ascending=False).iloc[0]
        overreach_days_ago = (today - last_extreme["start_date"].date()).days
        effort = last_extreme["suffer_score"]

        # Recovery time estimate based on effort magnitude
        if effort >= 800:
            overreach_recovery_days = 18
        elif effort >= 600:
            overreach_recovery_days = 14
        elif effort >= 500:
            overreach_recovery_days = 10

        if overreach_days_ago < overreach_recovery_days:
            overreach_active = True

    # Determine readiness level
    if overreach_active:
        days_remaining = overreach_recovery_days - overreach_days_ago
        if days_remaining > 7:
            level = "overreach"
            emoji = "🔴🔴🔴"
            title = "OVERREACH activo — descansa"
            message = (
                f"Esfuerzo extremo hace {overreach_days_ago} días "
                f"(effort {int(last_extreme['suffer_score'])}). "
                f"Recuperación estimada: {overreach_recovery_days} días. "
                f"Faltan ~{days_remaining} días."
            )
            recommendation = "DESCANSO TOTAL o Z1 máx 30min. Hidratación, sueño, electrolitos."
            color = "#f85149"
        elif days_remaining > 3:
            level = "recovering"
            emoji = "🟡"
            title = "En recuperación — solo Z1-Z2 suave"
            message = (
                f"Overreach hace {overreach_days_ago} días "
                f"(effort {int(last_extreme['suffer_score'])}). "
                f"Recuperación en progreso. ~{days_remaining} días para Z4."
            )
            recommendation = "Solo Z1-Z2, máximo 1 hora. Nada de intensidad."
            color = "#d29922"
        else:
            level = "almost_ready"
            emoji = "🟡🟢"
            title = "Casi recuperado — Z2 con precaución"
            message = (
                f"Overreach hace {overreach_days_ago} días. "
                f"Si no hay mareos ni fatiga inusual, puedes probar Z2-Z3 corto."
            )
            recommendation = "Z2 libre. Z3 solo si te sientes bien. Aún no Z4."
            color = "#d29922"
    elif tsb >= 15:
        level = "peak"
        emoji = "🟢🟢🟢"
        title = "Listo para esfuerzo máximo"
        message = "Tu cuerpo está descansado y con buena base. Día ideal para un fondo largo, intervalos duros, o test de FTP."
        recommendation = "Puedes hacer Z4-Z5, intervalos, o fondo largo"
        color = "#3fb950"
    elif tsb >= 5:
        level = "fresh"
        emoji = "🟢🟢"
        title = "Fresco — entrena normal"
        message = "Buena forma. Puedes entrenar con intensidad moderada-alta sin riesgo."
        recommendation = "Z2-Z4 sin problema. Intervalos cortos OK."
        color = "#3fb950"
    elif tsb >= 0:
        level = "neutral"
        emoji = "🟢"
        title = "Normal — entrena con moderación"
        message = "Equilibrio entre fitness y fatiga. Entrenamiento normal pero sin excederte."
        recommendation = "Z2-Z3 recomendado. Z4 solo si te sientes bien."
        color = "#58a6ff"
    elif tsb >= -10:
        level = "tired"
        emoji = "🟡"
        title = "Fatigado — solo entreno suave"
        message = "Acumulación de fatiga. Tu cuerpo necesita recuperar. Solo actividad ligera."
        recommendation = "Solo Z1-Z2. Máximo 1 hora. Mejor caminar o descansar."
        color = "#d29922"
    elif tsb >= -30:
        level = "very_tired"
        emoji = "🔴"
        title = "Muy fatigado — descanso activo"
        message = "Fatiga importante. Entrenar fuerte ahora aumenta riesgo de lesión y sobreentrenamiento."
        recommendation = "Solo Z1 (recuperación activa) o descanso total. Hidratación y sueño."
        color = "#f85149"
    else:
        level = "danger"
        emoji = "🔴🔴🔴"
        title = "OVERREACH — descansa ya"
        message = "Fatiga extrema. Posibles síntomas: mareos, HR errática, falta de motivación, problemas de sueño."
        recommendation = "DESCANSO TOTAL. Si hay mareos o malestar, consulta médico."
        color = "#f85149"

    return JSONResponse({
        "level": level,
        "emoji": emoji,
        "title": title,
        "message": message,
        "recommendation": recommendation,
        "color": color,
        "tsb": round(tsb, 1),
        "ctl": round(ctl, 1),
        "atl": round(atl, 1),
        "projected": days_to_project > 0,
        "last_sync_date": last_date.isoformat(),
        "overreach_active": overreach_active,
        "overreach_days_ago": overreach_days_ago,
    })


@app.get("/api/training-load")
def api_training_load():
    """Return CTL/ATL/TSB time series with rest-day projection to today + 3 days."""
    from datetime import date

    df = load_activities_df()
    daily = compute_training_load(df)

    # Calculate how many days to project (from last data point to today + 3)
    last_date = daily["date"].iloc[-1].date()
    today = date.today()
    days_to_project = (today - last_date).days + 3
    if days_to_project < 1:
        days_to_project = 3

    # Project forward assuming rest
    projected = project_rest_days(daily, days_ahead=days_to_project)

    return JSONResponse(
        {
            "dates": projected["date"].dt.strftime("%Y-%m-%d").tolist(),
            "ctl": projected["ctl"].round(1).tolist(),
            "atl": projected["atl"].round(1).tolist(),
            "tsb": projected["tsb"].round(1).tolist(),
            "tss": projected["tss"].round(1).tolist(),
            "projected": projected["projected"].tolist(),
        }
    )


@app.get("/api/weekly-summary")
def api_weekly_summary():
    """Return weekly training summary."""
    df = load_activities_df()
    weekly = get_weekly_summary(df)
    return JSONResponse(
        {
            "weeks": weekly["year_week_str"].tolist(),
            "tss": weekly["total_tss"].round(1).tolist(),
            "hours": weekly["total_hours"].round(1).tolist(),
            "activities": weekly["activities"].tolist(),
            "elevation": weekly["total_elevation"].round(0).tolist(),
            "distance": weekly["total_distance_km"].round(1).tolist(),
        }
    )


@app.get("/api/activities")
def api_activities(limit: int = 50, activity_type: str | None = None):
    """Return recent activities with metrics."""
    df = load_activities_df()
    if activity_type:
        df = df[df["type"] == activity_type]
    df = df.sort_values("start_date", ascending=False).head(limit)

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "type": row["type"],
                "date": row["start_date"].strftime("%Y-%m-%d"),
                "distance_km": round((row["distance"] or 0) / 1000, 1),
                "elevation": round(row["total_elevation_gain"] or 0),
                "moving_time_h": round((row["moving_time"] or 0) / 3600, 1),
                "avg_watts": _safe_round(row["average_watts"]),
                "avg_hr": _safe_round(row["average_heartrate"]),
                "suffer_score": _safe_int(row["suffer_score"]),
            }
        )
    return JSONResponse(records)


@app.get("/api/compare/{id1}/{id2}")
def api_compare(id1: int, id2: int):
    """Compare two activities side by side."""
    df = load_activities_df()
    a1 = df[df["id"] == id1]
    a2 = df[df["id"] == id2]

    if a1.empty or a2.empty:
        return JSONResponse({"error": "Activity not found"}, status_code=404)

    def activity_dict(row):
        return {
            "id": int(row["id"]),
            "name": row["name"],
            "date": row["start_date"].strftime("%Y-%m-%d"),
            "distance_km": round((row["distance"] or 0) / 1000, 1),
            "elevation": round(row["total_elevation_gain"] or 0),
            "moving_time_h": round((row["moving_time"] or 0) / 3600, 2),
            "avg_speed_kph": round((row["average_speed"] or 0) * 3.6, 1),
            "avg_watts": _safe_round(row["average_watts"]),
            "avg_hr": _safe_round(row["average_heartrate"]),
            "max_hr": _safe_int(row["max_heartrate"]),
            "suffer_score": _safe_int(row["suffer_score"]),
            "kilojoules": _safe_round(row["kilojoules"]),
        }

    r1 = a1.iloc[0]
    r2 = a2.iloc[0]
    return JSONResponse({"activity_1": activity_dict(r1), "activity_2": activity_dict(r2)})


@app.get("/activity", response_class=HTMLResponse)
def activity_page():
    """Serve the activity detail page."""
    with open("app/templates/activity.html") as f:
        return f.read()


@app.get("/activities", response_class=HTMLResponse)
def activities_page():
    """Serve the activities list page."""
    with open("app/templates/activities.html") as f:
        return f.read()


@app.get("/api/activities/all")
def api_all_activities():
    """Return all activities with metrics for the list view."""
    df = load_activities_df()
    df = df.sort_values("start_date", ascending=False)

    records = []
    for _, row in df.iterrows():
        distance = row["distance"] or 0
        moving_time = row["moving_time"] or 0
        records.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "type": row["type"],
                "date": row["start_date"].strftime("%Y-%m-%d"),
                "distance_km": round(distance / 1000, 1),
                "elevation": _safe_round(row["total_elevation_gain"]),
                "moving_time_h": round(moving_time / 3600, 2),
                "avg_speed_kph": round((row["average_speed"] or 0) * 3.6, 1),
                "avg_hr": _safe_round(row["average_heartrate"]),
                "avg_watts": _safe_round(row["average_watts"]),
                "suffer_score": _safe_int(row["suffer_score"]),
            }
        )
    return JSONResponse(records)


@app.get("/api/activity/{activity_id}")
def api_activity_detail(activity_id: int):
    """Return full detail for a single activity."""
    df = load_activities_df()
    activity = df[df["id"] == activity_id]
    if activity.empty:
        return JSONResponse({"error": "Activity not found"}, status_code=404)

    row = activity.iloc[0]
    return JSONResponse(
        {
            "id": int(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "sport_type": row.get("sport_type") if not _is_nan(row.get("sport_type")) else None,
            "date": row["start_date"].strftime("%Y-%m-%d"),
            "distance_km": round((row["distance"] or 0) / 1000, 1),
            "elevation": _safe_round(row["total_elevation_gain"]),
            "moving_time_h": round((row["moving_time"] or 0) / 3600, 2),
            "elapsed_time_h": round((row["elapsed_time"] or 0) / 3600, 2),
            "avg_speed_kph": round((row["average_speed"] or 0) * 3.6, 1),
            "avg_watts": _safe_round(row["average_watts"]),
            "max_watts": _safe_int(row.get("max_watts")),
            "weighted_avg_watts": _safe_round(row.get("weighted_average_watts")),
            "avg_hr": _safe_round(row["average_heartrate"]),
            "max_hr": _safe_int(row["max_heartrate"]),
            "suffer_score": _safe_int(row["suffer_score"]),
            "kilojoules": _safe_round(row["kilojoules"]),
            "has_power_meter": bool(row.get("has_power_meter")),
            "trainer": bool(row.get("trainer")),
        }
    )


@app.get("/api/activities/similar/{activity_id}")
def api_similar_activities(activity_id: int):
    """Find activities similar in type, distance, and elevation."""
    df = load_activities_df()
    activity = df[df["id"] == activity_id]
    if activity.empty:
        return JSONResponse({"error": "Activity not found"}, status_code=404)

    row = activity.iloc[0]
    act_type = row["type"]
    act_dist = row["distance"] or 0
    act_elev = row["total_elevation_gain"] or 0

    # Filter same type, distance within 30%, elevation within 40%
    similar = df[
        (df["type"] == act_type)
        & (df["distance"].between(act_dist * 0.7, act_dist * 1.3))
        & (df["total_elevation_gain"].between(act_elev * 0.6, act_elev * 1.4))
    ].sort_values("start_date", ascending=False).head(15)

    records = []
    for _, r in similar.iterrows():
        records.append(
            {
                "id": int(r["id"]),
                "name": r["name"],
                "date": r["start_date"].strftime("%Y-%m-%d"),
                "distance_km": round((r["distance"] or 0) / 1000, 1),
                "elevation": _safe_round(r["total_elevation_gain"]),
                "moving_time_h": round((r["moving_time"] or 0) / 3600, 1),
                "avg_hr": _safe_round(r["average_heartrate"]),
                "avg_watts": _safe_round(r["average_watts"]),
                "suffer_score": _safe_int(r["suffer_score"]),
            }
        )
    return JSONResponse(records)


def _is_nan(value) -> bool:
    """Check if value is NaN."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


@app.get("/api/activity/{activity_id}/zones")
def api_activity_zones(activity_id: int):
    """Get HR/Power zones for an activity. Fetches from Strava if not cached."""
    from app.db import get_activity_zones, has_zones, save_activity_zones
    from app.strava_client import fetch_activity_zones

    # Check cache first
    zones = get_activity_zones(activity_id)
    if zones:
        return JSONResponse(_format_zones(zones))

    # Fetch from Strava
    raw_zones = fetch_activity_zones(activity_id)
    if not raw_zones:
        return JSONResponse({"heartrate": [], "power": []})

    # Save to DB
    save_activity_zones(activity_id, raw_zones)

    # Return formatted
    zones = get_activity_zones(activity_id)
    return JSONResponse(_format_zones(zones))


@app.get("/api/activity/{activity_id}/streams")
def api_activity_streams(activity_id: int):
    """Get HR and power streams (time series) for charting."""
    from app.strava_client import fetch_activity_streams

    streams = fetch_activity_streams(activity_id)
    if not streams:
        return JSONResponse({"time": [], "heartrate": [], "watts": [], "distance": []})

    # Downsample to ~500 points for smooth charts without overloading browser
    time_data = streams.get("time", [])
    hr_data = streams.get("heartrate", [])
    watts_data = streams.get("watts", [])
    distance_data = streams.get("distance", [])

    total_points = len(time_data)
    if total_points > 500:
        step = total_points // 500
        time_data = time_data[::step]
        hr_data = hr_data[::step] if hr_data else []
        watts_data = watts_data[::step] if watts_data else []
        distance_data = distance_data[::step] if distance_data else []

    # Convert time to minutes, distance to km
    time_min = [round(t / 60, 1) for t in time_data]
    distance_km = [round(d / 1000, 1) for d in distance_data] if distance_data else []

    return JSONResponse({
        "time_min": time_min,
        "heartrate": hr_data,
        "watts": watts_data,
        "distance_km": distance_km,
    })


def _format_zones(zones: dict) -> dict:
    """Format zones for frontend display."""
    import json
    from app.config import BASE_DIR

    # Load custom zones config
    config_path = BASE_DIR / "zones_config.json"
    hr_labels = ["Z1 Recovery", "Z2 Endurance", "Z3 Tempo", "Z4 Threshold", "Z5 VO2max"]
    power_zones_custom = [
        {"min": 0, "max": 133, "label": "Z1 Recuperación Activa"},
        {"min": 134, "max": 170, "label": "Z2 Endurance"},
        {"min": 171, "max": 182, "label": "Z3 Tempo"},
        {"min": 183, "max": 191, "label": "Z3 Sweet Spot"},
        {"min": 192, "max": 230, "label": "Z4 Umbral - FTP"},
        {"min": 231, "max": 290, "label": "Z5 VO2 MAX"},
        {"min": 291, "max": 363, "label": "Z6 Capacidad Anaeróbica"},
        {"min": 364, "max": 484, "label": "Z7 Anaerobic Power"},
        {"min": 485, "max": 950, "label": "Z8 Neuromuscular"},
    ]

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        if "power_zones" in config:
            power_zones_custom = [
                {"min": z["min"], "max": z["max"], "label": z["name"]}
                for z in config["power_zones"]
            ]
        if "hr_zones" in config:
            hr_labels = [z["name"] for z in config["hr_zones"]]

    result = {}
    for zone_type, buckets in zones.items():
        formatted = []

        if zone_type == "power":
            # Remap Strava's generic power buckets into our custom zones
            # Strava buckets have a min/max range. We distribute time proportionally
            # across custom zones that overlap with each bucket.
            custom_time = [0.0] * len(power_zones_custom)

            for b in buckets:
                b_min = b["min"] if b["min"] is not None else 0
                b_max = b["max"] if b["max"] is not None else 950
                b_range = max(b_max - b_min, 1)

                for i, cz in enumerate(power_zones_custom):
                    # Calculate overlap between strava bucket and custom zone
                    overlap_min = max(b_min, cz["min"])
                    overlap_max = min(b_max, cz["max"])
                    if overlap_min < overlap_max:
                        overlap_fraction = (overlap_max - overlap_min) / b_range
                        custom_time[i] += b["time_seconds"] * overlap_fraction

            for i, cz in enumerate(power_zones_custom):
                secs = custom_time[i]
                mins = secs / 60
                formatted.append({
                    "zone": i + 1,
                    "label": cz["label"],
                    "min_val": cz["min"],
                    "max_val": cz["max"],
                    "time_seconds": round(secs),
                    "time_minutes": round(mins, 1),
                    "time_display": f"{int(mins // 60)}h{int(mins % 60):02d}m" if mins >= 60 else f"{int(mins)}m",
                })
        else:
            # HR zones - use as-is from Strava
            for b in buckets:
                mins = b["time_seconds"] / 60
                label = hr_labels[b["zone"] - 1] if b["zone"] <= 5 else f"Z{b['zone']}"
                formatted.append({
                    "zone": b["zone"],
                    "label": label,
                    "min_val": b["min"],
                    "max_val": b["max"],
                    "time_seconds": b["time_seconds"],
                    "time_minutes": round(mins, 1),
                    "time_display": f"{int(mins // 60)}h{int(mins % 60):02d}m" if mins >= 60 else f"{int(mins)}m",
                })

        result[zone_type] = formatted
    return result


@app.get("/pacing", response_class=HTMLResponse)
def pacing_page():
    """Serve the pacing calculator page."""
    with open("app/templates/pacing.html") as f:
        return f.read()


@app.get("/zones", response_class=HTMLResponse)
def zones_config_page():
    """Serve the zones configuration page."""
    with open("app/templates/zones_config.html") as f:
        return f.read()


@app.get("/api/zones/config")
def api_get_zones_config():
    """Get current zones configuration."""
    import json
    from app.config import BASE_DIR

    config_path = BASE_DIR / "zones_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"error": "No config found"}, status_code=404)


@app.post("/api/zones/config")
async def api_save_zones_config(request: Request):
    """Save zones configuration."""
    import json
    from app.config import BASE_DIR

    request_data = await request.json()
    config_path = BASE_DIR / "zones_config.json"
    with open(config_path, "w") as f:
        json.dump(request_data, f, indent=2, ensure_ascii=False)

    # Clear cached power zones so they get recalculated with new config
    from app.db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM activity_zones WHERE zone_type = 'power'")
    conn.commit()
    conn.close()

    return JSONResponse({"status": "ok"})


@app.get("/api/pacing-calculator")
def api_pacing_calculator(distance_km: float = 100, elevation_m: float = 1000):
    """Calculate recommended pacing for a target ride."""
    from datetime import date

    df = load_activities_df()
    daily = compute_training_load(df)

    # Get current CTL (projected to today)
    last_date = daily["date"].iloc[-1].date()
    today = date.today()
    days_to_project = (today - last_date).days
    ctl = daily["ctl"].iloc[-1]
    for _ in range(days_to_project):
        ctl = ctl * (1 - 2 / 43)

    ftp = 197
    max_hr = 195
    resting_hr = 60

    # Target zones based on distance
    # HR pct is % of HR reserve (max-resting) — lower for longer rides
    if distance_km >= 250:
        target_if = 0.58
        target_hr_pct = 0.55  # ~135 bpm — firm Z2
    elif distance_km >= 150:
        target_if = 0.62
        target_hr_pct = 0.60  # ~141 bpm — Z2 high
    elif distance_km >= 100:
        target_if = 0.65
        target_hr_pct = 0.63  # ~145 bpm — Z2-Z3 border
    elif distance_km >= 60:
        target_if = 0.70
        target_hr_pct = 0.67  # ~150 bpm — Z3 low
    else:
        target_if = 0.75
        target_hr_pct = 0.72  # ~157 bpm — Z3-Z4

    target_hr = resting_hr + (max_hr - resting_hr) * target_hr_pct
    target_watts = ftp * target_if

    # Estimate speed/time
    elev_factor = 1 - (elevation_m / distance_km / 1000) * 0.3
    base_speed = 19.0 * elev_factor
    estimated_time_h = distance_km / base_speed

    # Estimate effort
    hr_reserve = (target_hr - resting_hr) / (max_hr - resting_hr)
    intensity = hr_reserve * 1.1
    estimated_effort = estimated_time_h * intensity * intensity * 100

    # Recovery
    if estimated_effort >= 700:
        recovery_days = "14-18"
        recovery_level = "overreach"
    elif estimated_effort >= 500:
        recovery_days = "10-14"
        recovery_level = "extreme"
    elif estimated_effort >= 300:
        recovery_days = "4-7"
        recovery_level = "hard"
    elif estimated_effort >= 150:
        recovery_days = "2-3"
        recovery_level = "moderate"
    else:
        recovery_days = "1"
        recovery_level = "easy"

    # Zone distribution
    if distance_km >= 150:
        zones_rec = {"Z1": "5%", "Z2": "70-75%", "Z3": "15-20%", "Z4": "< 5%"}
    elif distance_km >= 80:
        zones_rec = {"Z1": "5%", "Z2": "60-65%", "Z3": "25-30%", "Z4": "5-10%"}
    else:
        zones_rec = {"Z1": "5%", "Z2": "50-55%", "Z3": "30-35%", "Z4": "10-15%"}

    # Nutrition
    carbs_per_hour = 60 if distance_km < 150 else 80
    total_carbs = int(carbs_per_hour * estimated_time_h)
    water_liters = round(estimated_time_h * 0.6, 1)
    stop_interval = 60 if distance_km >= 150 else 80

    return JSONResponse({
        "input": {
            "distance_km": distance_km,
            "elevation_m": elevation_m,
            "ctl": round(ctl, 1),
            "ftp": ftp,
        },
        "pacing": {
            "target_hr": round(target_hr),
            "target_hr_range": f"{round(target_hr - 3)}-{round(target_hr + 3)}",
            "target_watts": round(target_watts),
            "target_if": target_if,
            "estimated_speed_kph": round(base_speed, 1),
            "estimated_time_h": round(estimated_time_h, 1),
            "estimated_effort": round(estimated_effort),
        },
        "recovery": {
            "estimated_days": recovery_days,
            "level": recovery_level,
        },
        "zones": zones_rec,
        "nutrition": {
            "carbs_per_hour_g": carbs_per_hour,
            "total_carbs_g": total_carbs,
            "water_liters": water_liters,
            "stop_every_km": stop_interval,
        },
    })
