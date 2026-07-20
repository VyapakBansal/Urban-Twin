# Urban Twin — Product Requirements Document

**Author:** Vyapak Bansal  
**Status:** Active  
**Scope:** Kensington (Hillhurst–Sunnyside), Calgary

---

## 1. Summary

Urban Twin is a neighbourhood digital twin: live environmental and civic feeds for one AOI are ingested into PostGIS, published through Kafka, forecasted with LightGBM, and shown on an interactive 3D Cesium map.

Kafka and Terraform are part of the stack so the project exercises event streaming and infrastructure-as-code on a real system. Neighbourhood-scale volume alone would not require either; that tradeoff is documented in Section 6.

This is a single-neighbourhood system, not a multi-tenant smart-city platform.

---

## 2. Goals

- End-to-end real-time pipeline: ingest → store → stream → map, with sub-minute client update latency after ingest
- Spatial data engineering: PostGIS schema, geospatial queries, CRS handling
- Applied forecasting: validated multi-horizon models with reported metrics
- Deployable demo (local Docker Compose; optional Azure VM via Terraform)
- Documentation that explains architecture and decisions clearly

### Non-goals

- Multi-broker Kafka HA / cluster
- Multi-user auth, billing, or SaaS features
- City-wide coverage
- Native mobile client
- Multi-environment Terraform (dev/staging/prod)

---

## 3. Data sources

| Feed | Provider |
|---|---|
| Weather (temp, humidity, wind, precip) | OpenWeather |
| Wind field grid | Open-Meteo |
| Bow River level / flow | Environment Canada (`05BH004`) |
| Air quality (PM2.5) | OpenAQ when available; Open-Meteo fallback |
| Buildings, pathways, amenities | OpenStreetMap |
| Traffic incidents | Open Calgary |

---

## 4. System architecture

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

**Optional cloud (Terraform):** Azure resource group, budget alert, and a short-lived Standard_B2s VM running Docker + nginx. See [infra/README.md](infra/README.md).

### 4.1 What “real-time” means

- Ingestion polls upstream APIs on a configured interval (default ~5 minutes)
- Each new reading is written to PostGIS and published to `sensor.readings`
- The WebSocket bridge consumes that topic and pushes updates to connected clients within seconds
- The map updates without a full page refresh

“Real-time” refers to pipeline responsiveness after ingest. Upstream sources typically refresh on the order of minutes.

---

## 5. Data model (PostGIS)

### Static

- `buildings` — polygon geometry, height, OSM source, imported_at
- `neighborhood_bounds` — AOI polygon
- Pathways, amenities, incidents as dedicated tables/layers

### Dynamic

- `sensor_readings` — station_id, point geometry, reading_type, value, unit, recorded_at, ingested_at, source
- Indexes: GiST on geometry; btree on recorded_at; composite (station_id, recorded_at)

### Forecasts

- `forecasts` — station_id, reading_type, predicted_value, target_time, model_version, generated_at

### Migrations

Schema changes go through Alembic only.

---

## 6. Architectural decisions

| Decision | Reasoning |
|---|---|
| Kafka despite low volume | Exercises topics, consumer groups, offsets, and at-least-once delivery on a working system |
| Single Kafka broker | Enough for the producer/consumer model; cluster HA is out of scope |
| Terraform for one demo environment | Exercises providers, state, plan/apply without a multi-env matrix |
| Separate processes, one repo | Ingest, forecast, WebSocket bridge, and API are separate processes; shared codebase for simplicity |
| FastAPI | Async fits WebSocket + polling; OpenAPI docs for the REST surface |
| Single neighbourhood AOI | Keeps OSM import and demo legible |

### 6a. Hosting options

- **Local:** Docker Compose for PostGIS + Kafka; Python processes + Vite on the host
- **Database:** local PostGIS or Supabase (see [docs/DEPLOY.md](docs/DEPLOY.md))
- **Frontend host:** Vercel optional (see [docs/VERCEL.md](docs/VERCEL.md)); API stays on an always-on host
- **Azure demo VM:** short-lived B2s via Terraform; destroy when finished

---

## 7. Forecasting

- **Targets:** `temp`, `river_level`, `aqi_pm25`
- **Model:** LightGBM multi-horizon (`lgbm-mh-v1`)
- **Horizons:** configurable (default includes 1, 2, 3, 6, 12, 24, 48 hours)
- **Validation:** time-ordered train/test split; MAE/RMSE reported by the train/validate tooling
- **Serving:** forecast worker + REST `/predict`, `/predict/batch`, `/forecasts`

---

## 8. API surface

**REST (FastAPI / OpenAPI):**

- Buildings, pathways, amenities, incidents, layer counts
- Readings history and latest
- Forecasts and `/predict` endpoints
- Wind grid layer

**WebSocket:**

- `/ws/live` — push on new AOI readings

**Non-functional:**

- Rate limiting on REST (slowapi)
- Pydantic validation
- Structured error responses

---

## 9. Frontend

- Cesium 3D scene with OSM buildings for the AOI
- Live overlays: weather, river, air, wind field, humidity, precip, forecasts
- Civic layers: pathways, amenities, incidents
- Click to inspect, double-click to fly, camera toolbar
- Layer toggles
- Light and dark theme (UI + basemap)

---

## 10. Testing

- Pytest coverage for ingestion validation, API responses, and forecast output shape
- At least one integration path for ingest → DB → API against a test database

---

## 11. Deployment

| Piece | Approach |
|---|---|
| Local full stack | `npm run dev` (see README) |
| Azure demo | `infra/` Terraform + `deploy/` bootstrap |
| Frontend CDN | Optional Vercel |
| Secrets | `.env` / gitignored `terraform.tfvars` only |

---

## 12. Success criteria

- Opening the map shows live layers updating after ingest without a manual refresh
- Architecture and setup are understandable from the README in a few minutes
- Claims about the pipeline match what actually runs locally (and optionally on Azure)
