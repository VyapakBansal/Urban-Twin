# Urban Twin

**Kensington, Calgary — a neighbourhood digital twin**

Live weather, Bow River levels, air quality, pathways, traffic incidents, OSM buildings, and multi-horizon ML forecasts share one pipeline:

**ingest → PostGIS → Kafka → interactive 3D Cesium map**

| Docs | Purpose |
|---|---|
| [PRD.md](PRD.md) | Product requirements |
| [SECURITY.md](SECURITY.md) | STRIDE / OWASP notes |
| [infra/README.md](infra/README.md) | Azure + Terraform |
| [docs/SUPABASE.md](docs/SUPABASE.md) | Supabase (Postgres) setup |
| [docs/VERCEL.md](docs/VERCEL.md) | Frontend hosting on Vercel |

---

## Features

| Layer | Source |
|---|---|
| 3D buildings | OpenStreetMap → PostGIS |
| Live weather (temp, humidity, wind, precip) | OpenWeather |
| Wind field grid | Open-Meteo |
| Bow River level / flow | Environment Canada (`05BH004`) |
| Air quality (PM2.5) | OpenAQ (optional key) or Open-Meteo fallback |
| Pathways / amenities / incidents | OSM + Open Calgary |
| Forecasts | LightGBM multi-horizon (`temp`, `river_level`, `aqi_pm25`) |

The map is interactive: click features for details, double-click to fly, toggle layers, light/dark theme.

**Real-time note:** the pipeline pushes updates to the browser within seconds of an ingest. Upstream APIs typically refresh on the order of minutes.

---

## Prerequisites

- Docker Desktop (PostGIS + Kafka)
- Python **3.11+**
- Node.js **18+**
- Free [OpenWeather](https://openweathermap.org/api) API key
- Git

---

## Quick start

```bash
git clone https://github.com/VyapakBansal/Urban-Twin.git
cd Urban-Twin

cp .env.example .env
# Set OPENWEATHER_API_KEY=...

python -m venv .venv
# Windows:
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -e ".[dev]"
# macOS / Linux:
# .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"

npm run dev
```

Open **http://127.0.0.1:5173**.

| Command | Description |
|---|---|
| `npm run dev` | Full stack + map |
| `npm run up` | Backend only |
| `npm run down` | Stop app processes |
| `npm run down:all` | Stop apps + Docker |
| `npm run validate` | Forecast metrics |
| `npm run train` | Train LightGBM models (~10–30 min for full 5y run) |
| `npm run frontend` | Vite only |

First run may import OSM buildings and train models. Logs: `.run/logs/`.

### API examples

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/forecasts"
curl "http://127.0.0.1:8000/predict?reading_type=temp&horizon_hours=2"
curl "http://127.0.0.1:8000/predict?reading_type=river_level&at=2026-07-21T18:00:00Z"
curl "http://127.0.0.1:8000/predict/batch?reading_type=aqi_pm25&horizons=1,2,6,24"
curl http://127.0.0.1:8000/layers/wind
# Docs: http://127.0.0.1:8000/docs
```

### Train models

```bash
.venv/Scripts/python.exe -m urban_twin.forecast.train
# Smoke: --days 365 --horizons 1,2,24 --targets temp
```

Default: LightGBM multi-horizon (`lgbm-mh-v1`) on ~5 years of hourly history. Artifacts: `models/<type>_multih.joblib`.

---

## Architecture

```
 OpenWeather · Env Canada · Open-Meteo · OSM · Open Calgary
        │  poll (~5 min)
        ▼
 ┌──────────────────┐
 │ Ingestion        │──► PostGIS
 │                  │──► Kafka: sensor.readings
 └──────────────────┘
        │
        ├──────────────────┐
        ▼                  ▼
 ┌─────────────┐   ┌──────────────────┐
 │ Forecast    │   │ WebSocket bridge │
 │ LightGBM MH │   │ → /ws/live       │
 └─────────────┘   └──────────────────┘
        │
        ▼
 FastAPI (:8000)  +  Cesium twin (:5173)
```

| Process | Port / topic |
|---|---|
| PostGIS | `localhost:5433` |
| Kafka (KRaft) | `localhost:9092` |
| FastAPI | `localhost:8000` |
| WebSocket bridge | `localhost:8001` `/ws/live` |
| Vite | `localhost:5173` |

Kafka and Terraform are included so the project exercises event streaming and infrastructure-as-code on a real system; this neighbourhood’s volume alone would not require either.

---

## Project layout

```
urban_twin/     Python: ingest, API, WebSocket, forecast
frontend/       React + Cesium
deploy/         Azure nginx + VM bootstrap
infra/          Terraform (Azure demo VM)
docs/           Supabase + Vercel guides
scripts/        npm up / down helpers
alembic/        DB migrations
docker-compose.yml
```

---

## Configuration

Copy [.env.example](.env.example) → `.env`. Do not commit `.env`.

| Variable | Meaning |
|---|---|
| `OPENWEATHER_API_KEY` | Required for weather ingest |
| `OPENAQ_API_KEY` | Optional; air falls back to Open-Meteo if unset/unavailable |
| `AOI_*` / `STATION_*` | Kensington bbox + station |
| `FORECAST_HORIZONS` | e.g. `1,2,3,6,12,24,48` |
| `FORECAST_TRAIN_DAYS` | Default `1826` (~5 years) |
| `CORS_ORIGINS` | Allowed browser origins |
| `DATABASE_URL` | Local Docker or Supabase |

---

## Security

See [SECURITY.md](SECURITY.md).

- Secrets only in `.env` / gitignored `terraform.tfvars`
- Local services bind to `127.0.0.1` by default
- Parameterized SQL, Pydantic validation, REST rate limits (slowapi)

---

## Azure (optional)

One **Standard_B2s** Ubuntu VM runs Docker + the app stack behind **nginx :80**.

1. [Azure Portal](https://portal.azure.com) → select subscription → note Subscription ID  
2. Optional: Cost Management → Budget with alert emails  
3. Locally:

```bash
az login
az account set --subscription "<subscription-id>"
cd infra
cp terraform.tfvars.example terraform.tfvars
# Fill subscription_id, ssh_public_key, allowed_ssh_cidr, openweather_api_key, enable_demo_vm = true
terraform init && terraform plan && terraform apply
terraform output demo_http_url
# Tear down when finished:
terraform destroy
```

Details: [infra/README.md](infra/README.md).

---

## Roadmap

| Area | Status |
|---|---|
| PostGIS + multi-source ingest + Kafka + WebSocket | Done |
| Cesium twin (layers, inspect, light/dark) | Done |
| LightGBM multi-horizon + `/predict` API | Done |
| Azure Terraform bootstrap | Ready |
| Supabase + Vercel guides | Ready |
| Choosable AOI | Planned |
| Amenity ranking from live signals | Planned |
| Image → place prediction | Planned |
| Optional NVIDIA Earth-2 weather prior (GPU) | Planned |

---

## License / data

Author: Vyapak Bansal.  
Data © OpenStreetMap contributors; weather © OpenWeather; hydrometric © Environment and Climate Change Canada; atmosphere grids © Open-Meteo.
