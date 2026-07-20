# Urban Twin

Real-time geospatial weather twin for **Kensington, Calgary** (Hillhurst–Sunnyside).

Live environmental readings are ingested from OpenWeather, stored in PostGIS, published through Kafka, forecasted with a validated baseline model, and pushed to clients over WebSocket. A Cesium 3D frontend and cloud Terraform deploy come later (Weeks 4–5).

This is a **portfolio / learning project**: Kafka and Terraform are included deliberately to practice event streaming and IaC — not because one neighbourhood of weather data requires them. See [PRD.md](PRD.md) and [SECURITY.md](SECURITY.md).

---

## Architecture (Weeks 1–3)

```
 OpenWeather API
        │  poll (e.g. every 5 min)
        ▼
 ┌──────────────────┐
 │ Ingestion        │  fetch → validate → PostGIS
 │ (Python async)   │                 └─► Kafka: sensor.readings
 └──────────────────┘
        │
        ├──────────────────┐
        ▼                  ▼
 ┌─────────────┐   ┌──────────────────┐
 │ Forecast    │   │ WebSocket bridge │
 │ worker      │   │ Kafka → /ws/live │
 │ → forecasts │   └──────────────────┘
 │ + Kafka     │
 │ forecasts.  │
 │ generated   │
 └──────┬──────┘
        ▼
 ┌─────────────────────────────────────┐
 │ PostGIS                             │
 │  neighborhood_bounds · buildings    │
 │  sensor_readings · forecasts        │
 └──────────────────┬──────────────────┘
                    ▼
           ┌────────────────┐
           │ FastAPI REST   │  /buildings /readings /forecasts
           │ (port 8000)    │
           └────────────────┘
```

| Component | Role | Port / topic |
|---|---|---|
| PostGIS | Spatial DB | `localhost:5433` |
| Kafka (KRaft, single broker) | Event bus | `localhost:9092` |
| Ingestion | OpenWeather → DB + `sensor.readings` | CLI |
| WebSocket bridge | Kafka → browsers | `localhost:8001` `/ws/live` |
| FastAPI | Historical / static queries | `localhost:8000` |
| Forecast worker | Baseline 1h-ahead temp → DB + `forecasts.generated` | CLI |

**What “real-time” means here:** the *pipeline* pushes updates to clients within seconds of a new ingest. The *source* API only updates every few minutes. We do not pretend otherwise.

---

## Prerequisites

- Docker Desktop + Docker Compose
- Python 3.11+ (3.14 works in this repo)
- Free [OpenWeather](https://openweathermap.org/api) API key
- Git

Windows works fine. Prefer Git Bash or PowerShell. If Git Bash rewrites Docker paths like `/opt/...`, prefix with `MSYS_NO_PATHCONV=1`.

---

## Quick start

```bash
# 1. Clone & enter
cd "Urban Twin"   # or your clone path

# 2. Env
cp .env.example .env
# Edit .env → set OPENWEATHER_API_KEY=...

# 3. Infra
docker compose up -d

# 4. Python
python -m venv .venv
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 5. Schema + AOI
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m urban_twin.scripts.seed_aoi

# 6. OSM buildings (Overpass; may take ~1 min)
.venv/Scripts/python.exe -m urban_twin.scripts.import_osm_buildings

# 7. Tests
.venv/Scripts/python.exe -m pytest -q
```

### Run the live pipeline (several terminals)

```bash
# Terminal A — WebSocket bridge
.venv/Scripts/python.exe -m urban_twin.websocket_bridge.main

# Terminal B — listen for live events
.venv/Scripts/python.exe -m urban_twin.scripts.ws_listen

# Terminal C — REST API
.venv/Scripts/python.exe -m urban_twin.api.main

# Terminal D — ingest once (writes DB + Kafka)
.venv/Scripts/python.exe -m urban_twin.ingestion.main --once

# Terminal D — forecast once (writes DB + Kafka)
.venv/Scripts/python.exe -m urban_twin.forecast.main --once
```

### Useful API calls

```bash
# Health
curl http://127.0.0.1:8000/health

# Buildings in AOI bbox
curl "http://127.0.0.1:8000/buildings?bbox=-114.100,51.048,-114.062,51.062&limit=5"

# Recent readings
curl "http://127.0.0.1:8000/readings?station_id=calgary-kensington-1&limit=8"

# Latest forecasts
curl "http://127.0.0.1:8000/forecasts?station_id=calgary-kensington-1"

# Interactive OpenAPI docs
# open http://127.0.0.1:8000/docs
```

### Forecast validation (honest walk-forward)

```bash
.venv/Scripts/python.exe -m urban_twin.forecast.main --validate
```

Needs enough stored readings (persistence ≥4 points). MAE/RMSE are reported without shuffling — time order is respected.

---

## Data model (PostGIS)

| Table | Contents |
|---|---|
| `neighborhood_bounds` | AOI polygon (Kensington) |
| `buildings` | OSM footprints (~3.8k for this AOI) + optional height |
| `sensor_readings` | temp / humidity / wind / precip points |
| `forecasts` | 1h-ahead predictions + `model_version` |

Migrations: **Alembic** (`alembic/versions/`). Never hand-edit production schema.

CRS: **EPSG:4326** (WGS84) for all geometries.

---

## Forecasting (Week 3)

| Model | Idea | Version string |
|---|---|---|
| **Persistence** (default) | Next hour ≈ last observed value | `persistence-v1` |
| **Moving average** | Mean of last N values | `moving-avg-v1` |

Why start here: a simple, time-respecting baseline with reported MAE/RMSE is more credible than an unvalidated complex model. Compare with `--model moving_avg` when you have more history.

Horizon: **1 hour** (`FORECAST_HORIZON_HOURS`). Reading type default: **temp**.

---

## Project layout

```
urban_twin/
  config.py              # pydantic-settings from .env
  db/                    # SQLAlchemy models + sessions
  ingestion/             # OpenWeather → validate → PostGIS → Kafka
  messaging/             # ReadingEvent + Kafka producer
  websocket_bridge/      # Kafka consumer → /ws/live
  api/                   # FastAPI REST
  forecast/              # baselines + worker
  scripts/               # seed AOI, OSM import, ws_listen
alembic/                 # migrations
infra/                   # Terraform (Week 4)
tests/
docker-compose.yml       # PostGIS + Kafka
PRD.md
SECURITY.md              # STRIDE + OWASP notes
```

---

## Security (summary)

Full write-up: **[SECURITY.md](SECURITY.md)** (STRIDE + OWASP Top 10 mapped to this stack).

Non-negotiables:

- **Never commit `.env`** — only `.env.example`
- **Never commit API keys** — rotate if leaked in logs/chat
- Local services bind to **127.0.0.1** by default
- REST rate-limited via **slowapi** (`API_RATE_LIMIT`)
- SQL via SQLAlchemy / parameterized queries; inputs via Pydantic
- httpx OpenWeather logging set to WARNING so `appid` is not printed in URLs

This is a **localhost trust boundary**. Before any public deploy (Week 4+ on Azure), re-run STRIDE with VNet / TLS / Key Vault in mind.

---

## Configuration

See `.env.example`. Important knobs:

| Variable | Purpose |
|---|---|
| `OPENWEATHER_API_KEY` | Weather ingest (required) |
| `AOI_*` / `STATION_*` | Kensington bbox + station point |
| `DATABASE_URL` | Async SQLAlchemy (port **5433**) |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `INGESTION_POLL_INTERVAL_SEC` | Default 300 |
| `FORECAST_INTERVAL_SEC` | Default 900 |
| `API_RATE_LIMIT` | Default `60/minute` |

---

## Cloud plan (Azure — spend carefully)

**Credits:** ~$100 Azure. Treat them as a **final demo budget**, not a daily playground.

| Rule | Why |
|---|---|
| Local Docker until Weeks 1–3 are boringly reliable | Free iteration |
| No `terraform apply` / portal VMs until the local pipeline is green | Avoid burning credits on debug loops |
| Prefer **Azure Database for PostgreSQL Flexible Server** *or* keep Supabase free tier for DB | DB is the easy cost win |
| Prefer **Container Apps** or a **single small VM** over many always-on SKUs | Kafka + 4 services idle = silent spend |
| Set a **budget alert** on day one of any cloud use | Hard stop before $100 is gone |
| Tear down (`terraform destroy` / delete RG) after demos | Credits don’t pause on forgotten resources |

**Azure mapping (Week 4 — only when ready):**

| Local today | Azure later |
|---|---|
| Docker PostGIS | Azure Database for PostgreSQL + PostGIS, or Supabase (free) |
| Docker Kafka | Single VM / Container Apps running Compose, or Event Hubs Kafka endpoint (costlier — decide later) |
| Ingestion / forecast / API / WS | Container Apps or one B1s-class VM |
| Frontend (Week 5) | Static Web Apps or Azure Blob static website (cheap) |
| Secrets | Key Vault (never commit keys) |
| IaC | Terraform `azurerm` provider (not AWS) |

**Until then:** keep developing against `docker compose` on your laptop. Azure stays in `infra/` as code you write and `plan`, not blindly `apply`.

---

## Roadmap

| Week | Focus | Status |
|---|---|---|
| 1 | PostGIS, Alembic, ingest, OSM buildings | Done |
| 2 | Kafka + WebSocket bridge | Done |
| 3 | FastAPI + forecast worker | Done |
| 4 | Terraform on **Azure** (only after local is solid) | Next |
| 5 | React + CesiumJS frontend + cloud wiring | Planned |
| 6 | Stabilize, demo clip, README polish | Planned |

---

## Why Kafka / Terraform on a small AOI?

Documented honestly in the PRD: learning vehicle for topics, consumer groups, offsets, and IaC fundamentals — not a throughput necessity. Prefer that answer in interviews over claiming scale requirements this neighbourhood does not have.

---

## License / authorship

Portfolio project by Vyapak. Data © OpenStreetMap contributors; weather © OpenWeather (terms of their free tier).
