# Urban Twin

**Kensington, Calgary — a neighbourhood digital twin**

Portfolio project by **Vyapak Bansal**. Built to learn Kafka and infrastructure-as-code end-to-end, not to fake “Google Maps with a weather sticker.”

Live weather, Bow River levels, air quality, pathways, traffic incidents, OSM buildings, and **24-hour ML forecasts** (temperature + river level) share one pipeline:

**ingest → PostGIS → Kafka → interactive 3D Cesium map**

| Docs | Purpose |
|---|---|
| [PRD.md](PRD.md) | Product requirements |
| [SECURITY.md](SECURITY.md) | STRIDE / OWASP notes |
| [infra/README.md](infra/README.md) | Azure + Terraform (demo VM) |

---

## What you are looking at

| Layer | Source | Why it matters here |
|---|---|---|
| 3D buildings | OpenStreetMap → PostGIS | Spatial foundation of the twin |
| Live weather | OpenWeather | Near-real-time sensor loop |
| Bow River level / flow | Environment Canada (station `05BH004`) | Flood-relevant for Kensington (2013) |
| Air quality | OpenAQ (optional API key) | Second environmental signal |
| Pathways / amenities / incidents | OSM + Open Calgary | Civic “city systems” on the same map |
| +24h forecasts | HistGradientBoosting (`gbr-24h-v1`) | Trained offline; validated MAE/RMSE |

**Honest “real-time”:** the *pipeline* pushes updates to the browser within seconds of an ingest. Upstream APIs only refresh every few minutes — the project does not pretend otherwise.

**Why Kafka / Terraform on a small AOI?** Deliberate learning vehicle (topics, consumer groups, offsets, IaC). Prefer that answer in interviews over claiming scale this neighbourhood does not need.

---

## Prerequisites (reviewer machine)

- Docker Desktop (PostGIS + Kafka)
- Python **3.11+**
- Node.js **18+** (frontend)
- Free [OpenWeather](https://openweathermap.org/api) API key
- Git
- Windows: Git Bash or PowerShell works. If Git Bash rewrites Docker paths, use `MSYS_NO_PATHCONV=1`.

---

## Run it locally (recommended path)

```bash
git clone https://github.com/VyapakBansal/Urban-Twin.git
cd Urban-Twin

cp .env.example .env
# Edit .env → set OPENWEATHER_API_KEY=...

python -m venv .venv
# Windows:
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -e ".[dev]"
# macOS / Linux:
# .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"

npm run dev
```

Then open **http://127.0.0.1:5173**.

`npm run dev` starts Docker (PostGIS + Kafka), runs migrations, refreshes ingest + forecasts, and brings up the API, WebSocket bridge, background workers, and Vite.

| Command | What it does |
|---|---|
| `npm run dev` | Full stack + map |
| `npm run up` | Backend only (no Vite) |
| `npm run down` | Stop app processes |
| `npm run down:all` | Stop apps + Docker |
| `npm run validate` | Print forecast MAE/RMSE |
| `npm run train` | Retrain 24h models |
| `npm run frontend` | Vite only (stack already up) |

First run can take a few minutes (OSM building import + model train if artifacts are missing). Logs: `.run/logs/`.

### What to try on the map

1. Leave **Buildings** on — OSM footprints in 3D.
2. Toggle **Bow River** — live hydrometric level.
3. Toggle pathways / amenities / incidents — civic layers.
4. **Click** any feature → detail card; **double-click** → fly camera.
5. Use the camera bar: Home · Street · Top-down · Weather · River.
6. Click a layer name in the panel to fly to that system.
7. Note **+24h** forecast markers (temp + river).

### API smoke checks

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/forecasts"
# Interactive docs: http://127.0.0.1:8000/docs
```

### Forecast training / validation

```bash
.venv/Scripts/python.exe -m urban_twin.forecast.train
.venv/Scripts/python.exe -m urban_twin.forecast.main --validate
```

Training data: ~2 years Open-Meteo hourly temperature + multi-year MSC Bow River levels. Models land in `models/` (gitignored).

---

## Architecture (one picture)

```
 OpenWeather · Env Canada · OpenAQ · OSM · Open Calgary
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
 │ HistGBR 24h │   │ → /ws/live       │
 └─────────────┘   └──────────────────┘
        │
        ▼
 FastAPI (:8000)  +  Cesium twin (:5173)
```

| Process | Port / topic |
|---|---|
| PostGIS | `localhost:5433` |
| Kafka (KRaft) | `localhost:9092` · `sensor.readings` · `forecasts.generated` |
| FastAPI | `localhost:8000` |
| WebSocket bridge | `localhost:8001` `/ws/live` |
| Vite (local) | `localhost:5173` |

---

## Repo layout

```
urban_twin/          Python: ingest, API, WebSocket, forecast
frontend/            React + Cesium map
deploy/              Azure nginx + VM bootstrap
infra/               Terraform (Azure demo VM)
scripts/             npm up / down helpers
alembic/             DB migrations
docker-compose.yml   Local PostGIS + Kafka
```

---

## Configuration

Copy [.env.example](.env.example) → `.env`. Never commit `.env`.

| Variable | Meaning |
|---|---|
| `OPENWEATHER_API_KEY` | Required for weather ingest |
| `AOI_*` / `STATION_*` | Kensington bbox + station point |
| `FORECAST_HORIZON_HOURS` | Default `24` |
| `FORECAST_TARGETS` | `temp,river_level` |
| `CORS_ORIGINS` | Browser origins allowed by the API |
| `INGEST_SOURCES` | Which layers to poll |

---

## Security (short)

See [SECURITY.md](SECURITY.md).

- Secrets only in `.env` / gitignored `terraform.tfvars`
- Local services bind to `127.0.0.1` by default
- Azure demo is **HTTP, no auth** — short-lived demo boundary; destroy after
- SQLAlchemy / Pydantic validation; REST rate-limited (slowapi)

---

## Azure demo (optional — you run this)

Goal: one cheap **Standard_B2s** Ubuntu VM in **Canada Central** running the same stack behind **nginx :80** (map + proxied `/api` and `/ws`). Uses student credits carefully; **destroy when done**.

### A) Azure Portal (one-time setup)

1. Sign in at [portal.azure.com](https://portal.azure.com) with the subscription you want (e.g. **Azure for Students**).
2. Confirm the active subscription under **Subscriptions**.
3. Create a **Budget** (or rely on Terraform’s budget resource if you set `budget_contact_emails`):
   - Cost Management → Budgets → amount e.g. **$40/month**
   - Alert emails at 50% / 90%
4. Note your **Subscription ID** (Overview → Subscription ID).
5. Optional: Resource groups created by Terraform will be named like `rg-urbantwin-demo` — you do not need to create the VM by hand.

### B) Local machine before Terraform

```bash
# Tools (already fine if scoop/winget installed them)
az login
az account set --subscription "Azure for Students"   # or paste subscription id
az account show --query id -o tsv                    # copy this → subscription_id

# Public IP for SSH lockdown
curl https://api.ipify.org
# SSH public key
# Windows: type %USERPROFILE%\.ssh\id_ed25519.pub
```

### C) Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` (gitignored):

| Field | Value |
|---|---|
| `subscription_id` | From `az account show` |
| `enable_demo_vm` | `true` |
| `ssh_public_key` | Contents of `id_ed25519.pub` |
| `allowed_ssh_cidr` | `"YOUR.PUBLIC.IP/32"` |
| `openweather_api_key` | Same as local `.env` |
| `budget_contact_emails` | `["you@email.com"]` (optional but recommended) |
| `git_repo_url` | `https://github.com/VyapakBansal/Urban-Twin.git` |

```bash
terraform init
terraform plan     # review: RG + VNet + NSG + public IP + B2s VM
terraform apply    # type yes — starts spending credits
```

After apply:

```bash
terraform output demo_http_url
terraform output ssh_command
# Wait 10–20 min for cloud-init bootstrap, then:
curl "$(terraform output -raw demo_api_health_url)"
# Map: open the demo_http_url in a browser
# Debug: ssh … then  sudo tail -f /var/log/urban-twin-bootstrap.log
```

**Tear down (important):**

```bash
cd infra
terraform destroy
```

Or in Portal: delete resource group `rg-urbantwin-demo`.

Full detail: [infra/README.md](infra/README.md).

---

## 30-second demo script

1. Open the map — *“Neighbourhood digital twin of Kensington, not a weather widget.”*
2. Buildings — *“OSM footprints in PostGIS.”*
3. Bow River — *“Live river level; this area flooded in 2013.”*
4. Click a café / incident / forecast — *“Inspectable layers on one pipeline.”*
5. If they ask how — ingest → DB → Kafka → WebSocket / REST → Cesium; Terraform for Azure.

---

## Status & roadmap

| Area | Status |
|---|---|
| PostGIS + Alembic + multi-source ingest | Done |
| Kafka + WebSocket live bridge | Done |
| FastAPI + Cesium interactive twin | Done |
| 24h HistGBR temp + river forecasts | Done |
| One-command `npm run dev` | Done |
| Azure Terraform (B2s + nginx bootstrap) | Ready — apply when demoing |

### Future plans

| Idea | Intent |
|---|---|
| **Choosable AOI** | Switch neighbourhood bbox (not only Kensington) from config/UI; re-seed buildings + stations |
| **Event / amenity sorting** | Rank cafés and civic points using live + historical signals (busy-ness, incidents nearby, air/weather context) instead of a flat list |
| **Image → place prediction** | Upload a street/neighbourhood photo; model predicts *where* in the city it belongs and flies the twin camera there |

---

## License / data

Portfolio project by Vyapak Bansal.  
Data © OpenStreetMap contributors; weather © OpenWeather; hydrometric © Environment and Climate Change Canada.
