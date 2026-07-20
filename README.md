# Urban Twin

A **neighbourhood digital twin** for **Kensington, Calgary** (Hillhurst–Sunnyside) — not a weather sticker on Google Maps.

Live weather, Bow River levels, air quality, Calgary pathways & traffic incidents, OSM buildings, and **24-hour HistGBR forecasts** (temp + river) share one pipeline: **ingest → PostGIS → Kafka → interactive Cesium map**. Portfolio / learning project for Kafka + Terraform on Azure. See [PRD.md](PRD.md) and [SECURITY.md](SECURITY.md).

---

## Architecture

```
 OpenWeather · Env Canada · OpenAQ · OSM · Open Calgary
        │  poll (~5 min)
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
 │ HistGBR 24h │   │ Kafka → /ws/live │
 │ temp+river  │   └──────────────────┘
 └──────┬──────┘
        ▼
 ┌─────────────────────────────────────┐
 │ PostGIS                             │
 │  buildings · readings · forecasts   │
 │  pathways · amenities · incidents   │
 └──────────────────┬──────────────────┘
                    ▼
           ┌────────────────┐
           │ FastAPI REST   │  /buildings /readings /forecasts /layers/*
           └────────────────┘
                    ▼
           Cesium twin (click · fly · layers)
```

| Component        | Role                                                | Port                            |
| ---------------- | --------------------------------------------------- | ------------------------------- |
| PostGIS          | Spatial DB                                          | `localhost:5433`                |
| Kafka (KRaft)    | Event bus                                           | `localhost:9092`                |
| Ingestion        | weather, river, air, pathways, incidents, amenities | loop                            |
| WebSocket bridge | Kafka → browsers                                    | `:8001` `/ws/live`              |
| FastAPI          | REST + layers                                       | `:8000`                         |
| Forecast worker  | 24h HistGBR temp + river                            | loop                            |
| Frontend         | React + Cesium                                      | `:5173` (local) / `:80` (Azure) |

**“Real-time” here:** the _pipeline_ pushes updates within seconds of ingest. Source APIs update every few minutes — we do not pretend otherwise.

---

## Quick start (local)

```bash
cd "Urban Twin"
cp .env.example .env          # set OPENWEATHER_API_KEY
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
npm run dev                   # Docker + migrate + ingest + forecast + API + WS + Vite
```

Open **http://127.0.0.1:5173**.

| npm script         | What it does            |
| ------------------ | ----------------------- |
| `npm run dev`      | Full stack + frontend   |
| `npm run up`       | Backend only            |
| `npm run down`     | Stop Python/Vite        |
| `npm run down:all` | Stop processes + Docker |
| `npm run validate` | Forecast MAE/RMSE       |
| `npm run train`    | Retrain 24h models      |
| `npm run frontend` | Vite only               |

Logs/PIDs: `.run/`. First run may import OSM buildings and train models.

### Map interactions

- **Click** buildings, pathways, amenities, incidents, sensors, forecasts → detail card
- **Double-click** → fly camera to feature
- **Camera bar:** Home · Street · Top-down · Weather · River
- **Layer names** fly the camera to that system

### Useful API calls

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/buildings?bbox=-114.100,51.048,-114.062,51.062&limit=5"
curl "http://127.0.0.1:8000/readings?limit=8"
curl "http://127.0.0.1:8000/forecasts"
# docs: http://127.0.0.1:8000/docs
```

---

## Forecasting (24h temp + river)

| Model                    | Idea                                       | Version                            |
| ------------------------ | ------------------------------------------ | ---------------------------------- |
| **HistGBR** (default)    | Gradient boosting, lag + calendar features | `gbr-24h-v1`                       |
| Persistence / moving avg | Baselines for comparison                   | `persistence-v1` / `moving-avg-v1` |

Training data (offline): ~2y Open-Meteo hourly temps + multi-year MSC Bow River (`05BH004`).

```bash
.venv/Scripts/python.exe -m urban_twin.forecast.train
.venv/Scripts/python.exe -m urban_twin.forecast.main --once
.venv/Scripts/python.exe -m urban_twin.forecast.main --validate
```

Artifacts: `models/temp_24h.joblib`, `models/river_level_24h.joblib` (gitignored).

---

## Data model (PostGIS)

| Table                                  | Contents                           |
| -------------------------------------- | ---------------------------------- |
| `neighborhood_bounds`                  | AOI polygon                        |
| `buildings`                            | OSM footprints + optional height   |
| `sensor_readings`                      | weather / river / air (+ `source`) |
| `forecasts`                            | 24h predictions + `model_version`  |
| `pathways` / `amenities` / `incidents` | Civic layers                       |

Migrations: Alembic. CRS: **EPSG:4326**.

---

## Project layout

```
urban_twin/     Python package (ingest, API, WS, forecast)
frontend/       Vite + React + Cesium
deploy/         Azure nginx + bootstrap + compose overlay
infra/          Terraform (Azure demo VM)
scripts/        npm up/down helpers
alembic/        schema migrations
docker-compose.yml
```

---

## Configuration

See [.env.example](.env.example). Important knobs:

| Variable                 | Purpose                                            |
| ------------------------ | -------------------------------------------------- |
| `OPENWEATHER_API_KEY`    | Weather ingest (required)                          |
| `CORS_ORIGINS`           | Comma-separated browser origins                    |
| `API_HOST`               | `127.0.0.1` local; `0.0.0.0` behind nginx on Azure |
| `FORECAST_HORIZON_HOURS` | Default `24`                                       |
| `FORECAST_TARGETS`       | `temp,river_level`                                 |

---

## Security (summary)

Full write-up: **[SECURITY.md](SECURITY.md)**.

- Never commit `.env` or `infra/terraform.tfvars`
- Local services bind to **127.0.0.1** by default
- Azure demo is **HTTP, no auth** — demo trust boundary only; destroy when done
- Rate limit via slowapi; parameterized SQL; no OpenWeather keys in httpx access logs

---

## Azure demo deploy (single B2s VM)

**Credits:** treat ~$100 as a short demo budget. Idle B2s burns money — **`terraform destroy` after demos**.

```
Browser → nginx :80 → static Cesium
                 ├─ /api/* → FastAPI :8000
                 └─ /ws/*  → WebSocket :8001
VM also runs: Docker PostGIS + Kafka, ingest + forecast loops
```

### Prerequisites

- Azure CLI + Terraform (≥1.5)
- `az login` with a subscription that has credits
- SSH public key (`~/.ssh/id_ed25519.pub`)
- Repo pushed to GitHub (VM clones it)

### Apply

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Fill: subscription_id, ssh_public_key, allowed_ssh_cidr (your IP/32),
#       budget_contact_emails, openweather_api_key, enable_demo_vm = true

az login
terraform init
terraform plan
terraform apply
```

Outputs include `demo_http_url` and `ssh_command`. First boot runs cloud-init + [deploy/azure-bootstrap.sh](deploy/azure-bootstrap.sh) (~10–20 min: Docker, OSM, model train).

```bash
# Smoke
curl http://<public-ip>/api/health
# Map
open http://<public-ip>/
```

### Tear down (preserve credits)

```bash
cd infra
terraform destroy
```

Details: [infra/README.md](infra/README.md).

---

## Demo for non-engineers (≈30 seconds)

1. Open the map — _“Kensington digital twin, not Google Maps with a temperature sticker.”_
2. Buildings on — _“OSM footprints in a spatial database.”_
3. Bow River — _“Live river level; this area flooded in 2013.”_
4. Click a beacon / café / incident — _“Every layer is inspectable.”_
5. Forecast markers — _“24-hour ML forecast for temp and river.”_
6. If they ask how — Kafka + PostGIS + Terraform.

---

## Roadmap

| Week | Focus                                                     | Status         |
| ---- | --------------------------------------------------------- | -------------- |
| 1    | PostGIS, Alembic, ingest, OSM buildings                   | Done           |
| 2    | Kafka + WebSocket bridge                                  | Done           |
| 3    | FastAPI + forecast baselines                              | Done           |
| 4    | Azure Terraform (demo VM)                                 | Ready to apply |
| 5    | Cesium twin + multi-source layers + interactivity         | Done           |
| 6    | 24h HistGBR + one-command `npm run dev` + Azure bootstrap | Done           |

---

## Why Kafka / Terraform on a small AOI?

Learning vehicle for topics, consumer groups, offsets, and IaC — not a throughput necessity.

---

## License / authorship

Portfolio project by Vyapak Bansal. Data © OpenStreetMap contributors; weather © OpenWeather; hydrometric © Environment and Climate Change Canada.
