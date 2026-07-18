# 🚴 Strava Training Analyzer

App de análisis de entrenamiento personal que se conecta a Strava para descargar, organizar y analizar tus datos de ciclismo. Hecha para ciclistas que quieren insights más profundos que los que Strava ofrece.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

🇺🇸 [English version](README.md)

## Características

- **📊 Dashboard de Carga** — Gráfico CTL/ATL/TSB con proyección de días de descanso
- **🎯 Indicador de Readiness** — Saber si tu cuerpo está listo para intensidad o necesita descanso (detecta overreach)
- **📈 Detalle de Actividad** — Streams de HR y potencia, tiempo en zonas, proyección de recuperación
- **🔍 Comparación de Actividades** — Encuentra rides similares y compara métricas lado a lado
- **📐 Calculadora de Pacing** — Target de HR/watts/velocidad para cualquier ruta planificada
- **⚙️ Administrador de Zonas** — Configura zonas personalizadas de potencia y FC
- **🔄 Sync con Strava** — Sincronización con un click (incremental)
- **🏔️ Detección de Overreach** — Alerta cuando te pasaste basado en patrones históricos

## Capturas de Pantalla

### Dashboard
Gráfico CTL/ATL/TSB con indicador de readiness y TSS semanal

![Dashboard](docs/screenshots/dashboard.png)

### Detalle de Actividad
Streams de HR, distribución de zonas, proyección de recuperación y rides similares

![Detalle](docs/screenshots/activity-detail.png)

### Todas las Actividades
Lista ordenable y filtrable con estimaciones de recuperación

![Actividades](docs/screenshots/activities.png)

### Calculadora de Pacing
Target de HR/watts/velocidad basado en tu fitness actual

![Pacing](docs/screenshots/pacing.png)

### Administrador de Zonas
Configura zonas de potencia y FC con auto-cálculo desde FTP y FC máxima

![Zonas](docs/screenshots/zones.png)

## Inicio Rápido

### Requisitos

- Python 3.11+
- Una cuenta de Strava con una app API registrada ([crear aquí](https://www.strava.com/settings/api))

### Instalación

```bash
# Clonar el repo
git clone https://github.com/lramirezq/strava-analizer.git
cd strava-analizer

# Crear virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -e ".[dev]"

# Configurar credenciales de Strava
cp .env.example .env
# Editar .env con tu Client ID y Client Secret
```

### Primera Ejecución

```bash
# 1. Autenticarse con Strava (abre el browser)
python -m app.auth

# 2. Descargar todas tus actividades
python -m app.sync

# 3. Iniciar el dashboard
uvicorn app.server:app --port 8050

# Abrir http://localhost:8050
```

### App macOS (standalone)

Puedes construir una app macOS standalone que no requiere Python instalado:

```bash
pip install pyinstaller
pyinstaller strava_analyzer.spec --noconfirm
# Resultado: dist/Strava Analyzer.app (~62MB)
```

## Configuración

### Credenciales de Strava API

1. Ir a [strava.com/settings/api](https://www.strava.com/settings/api)
2. Crear una app (o usar una existente)
3. Setear "Authorization Callback Domain" a `localhost`
4. Copiar Client ID y Client Secret a tu archivo `.env`

### Zonas de Potencia

Navega a `/zones` en el dashboard para configurar tus zonas de potencia y FC. Soporta auto-cálculo desde FTP y FC máxima.

### Métricas

| Métrica | Descripción |
|---|---|
| CTL | Chronic Training Load — fitness (promedio 42 días de TSS) |
| ATL | Acute Training Load — fatiga (promedio 7 días de TSS) |
| TSB | Training Stress Balance — forma (CTL menos ATL) |
| TSS | Training Stress Score — intensidad × duración |

## Estructura del Proyecto

```
strava-analizer/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuración y environment
│   ├── db.py              # Capa de base de datos SQLite
│   ├── metrics.py         # Cálculos de TSS/CTL/ATL/TSB
│   ├── server.py          # Endpoints FastAPI
│   ├── strava_client.py   # Cliente API Strava con OAuth
│   ├── auth.py            # Flujo de autenticación OAuth2
│   ├── sync.py            # Sync de actividades desde Strava
│   └── templates/         # Páginas HTML del dashboard
├── tests/
│   └── test_db.py
├── docs/
│   ├── PRD.md
│   ├── specs/
│   └── adr/
├── main.py                # Entry point para app standalone
├── strava_analyzer.spec   # Spec de PyInstaller
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Endpoints API

| Endpoint | Descripción |
|---|---|
| `GET /` | Dashboard (o setup wizard si no está configurado) |
| `GET /activities` | Lista de todas las actividades con filtros |
| `GET /activity?id=X` | Detalle de actividad con zonas y streams |
| `GET /pacing` | Calculadora de pacing |
| `GET /zones` | Administrador de zonas |
| `GET /api/training-load` | Serie de tiempo CTL/ATL/TSB (JSON) |
| `GET /api/readiness` | Evaluación de readiness actual |
| `GET /api/activity/{id}/zones` | Distribución de zonas HR y potencia |
| `GET /api/activity/{id}/streams` | Series de tiempo HR y potencia |
| `GET /api/pacing-calculator` | Calcular pacing para ruta objetivo |
| `POST /api/sync` | Ejecutar sync con Strava |
| `POST /api/zones/config` | Guardar configuración de zonas |

## Stack Tecnológico

- **Backend:** Python, FastAPI, Pandas, NumPy
- **Frontend:** HTML, Chart.js (sin framework JS)
- **Storage:** SQLite
- **Auth:** Strava OAuth2
- **Packaging:** PyInstaller (app macOS)

## Privacidad

- Todos los datos quedan en tu máquina (base de datos SQLite)
- Tokens almacenados localmente, nunca transmitidos a terceros
- Sin analytics, sin tracking, sin dependencia de cloud
- Las llamadas API solo van a la API oficial de Strava

## Licencia

MIT

## Contribuir

¡Contribuciones bienvenidas! Por favor abre un issue primero para discutir qué te gustaría cambiar.
