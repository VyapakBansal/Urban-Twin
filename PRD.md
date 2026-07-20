# Urban Twin — Product Requirements Document

**Author:** Vyapak
**Status:** Draft v1
**Timeline:** 4 weeks
**Purpose:** Portfolio project demonstrating full-stack + real-time backend engineering capability, complementing hardware/SLAM work (ARGOS, event camera calibration)

---

## 1. Summary

Urban Twin is a real-time geospatial platform that ingests live environmental sensor data for a single neighborhood, stores it in a spatial database, forecasts near-term conditions with a trained model, and streams updates to a 3D web map as they arrive. The project prioritizes backend and data engineering depth over feature breadth — one real data source, done correctly end-to-end, rather than many data sources done shallowly.

This version deliberately includes Kafka and Terraform even though the data volume alone doesn't require them. That's a conscious tradeoff: the project doubles as a learning vehicle for event streaming and infrastructure-as-code, both of which show up constantly in backend job postings. The cost of that choice is honesty and scope discipline — see Section 6 for where this is and isn't justified by the system's actual needs, and Section 12 for the timeline impact.

**What this project is not:** a smart-city SaaS pitch or a multi-tenant platform. It's a single-neighborhood system built with production-grade tooling as a deliberate learning exercise, not because the data volume demands it.

---

## 2. Goals

- Demonstrate genuine real-time backend architecture: ingestion → processing → push to client, with sub-minute latency
- Demonstrate spatial data engineering: PostGIS schema design, geospatial queries, coordinate reference system handling
- Demonstrate applied ML: a real, validated forecasting model, not a stub
- Produce a deployed, demoable artifact with a live link, not just source code
- Produce documentation good enough that a reviewer can understand every architectural decision in under 5 minutes

### Non-goals
- Multiple simultaneous data sources (v1 ships with one)
- Multi-broker Kafka cluster or production-grade HA setup (single broker is enough to learn the concepts; a cluster is a separate, later exercise)
- Multi-user auth, billing, or SaaS features
- City-wide coverage (single neighborhood only)
- Mobile app or native client
- Multi-environment Terraform setup (dev/staging/prod) — one environment is enough to learn IaC fundamentals; don't let environment-matrix complexity eat into core project time

---

## 3. Target data source

**Primary:** weather (temperature, precipitation, wind, humidity) via OpenWeather or NOAA API.

Rationale: no approval/waitlist, generous free tier, reliable uptime, genuinely updates on a short interval, and has enough signal for a legitimate forecasting model. Traffic and air-quality APIs were considered and rejected for v1 — most require registration approval, city-specific access, or have unreliable coverage for the target neighborhood, which risks the whole real-time claim on infrastructure outside your control.

**Stretch (only after core is solid):** add one additional feed (e.g. air quality via OpenAQ) using the same ingestion pattern, to show the architecture generalizes.

---

## 4. System architecture

```
┌─────────────────┐
│  External API    │ (OpenWeather/NOAA)
└────────┬─────────┘
         │ polled on interval (see 4.1)
         ▼
┌─────────────────────────┐
│  Ingestion Service        │  (Python, async)
│  - fetch, validate, normalize │
│  - write to PostGIS        │
│  - publish to Kafka topic   │
│    sensor.readings           │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Kafka (single broker)    │
│  topics:                   │
│  - sensor.readings           │
│  - forecasts.generated       │
└──────┬──────────┬─────────┘
       │           │
       ▼           ▼
┌─────────────┐ ┌──────────────────┐
│ Forecast     │ │ WebSocket Bridge   │
│ Worker        │ │ (Kafka consumer →   │
│ (consumer)    │ │  broadcasts to      │
│ writes to     │ │  connected clients) │
│ forecasts.    │ └──────────┬────────┘
│ generated     │            │
│ topic + DB    │            ▼
└──────┬───────┘   ┌──────────────────────┐
       │             │  Connected Clients      │
       ▼             │  (browser WebSocket)     │
┌─────────────────────────┐  └──────────────────────┘
│  PostGIS                  │
│  - static layer (buildings)│
│  - dynamic layer (readings)│
│  - forecast outputs        │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────┐
│  API Layer (FastAPI)      │
│  - REST: historical/static queries │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Frontend (React + CesiumGL)│
│  - 3D building layer         │
│  - live sensor overlay       │
│  - forecast overlay           │
└─────────────────────────┘
```

**Infrastructure (provisioned via Terraform):**
- VPC, subnets, security groups
- Compute for ingestion, Kafka broker, forecast worker, WebSocket bridge, and API (EC2 or ECS/Fargate — EC2 is more instructive for learning IaC fundamentals since you provision more of the stack yourself)
- Managed Postgres with PostGIS (RDS, or Supabase if credits are tight — see Section 6a)
- S3 for model artifacts and static assets
- All of this defined as Terraform modules, applied via `terraform apply`, state stored remotely (S3 backend + DynamoDB lock table) once you're past the initial local-state stage

### 4.1 What "real-time" means here (be precise, this matters for credibility)

True push-based real-time end-to-end, defined as:

- Ingestion polls the external API as frequently as its rate limit allows (typically every 1–10 minutes for weather APIs — state the actual number once you pick a provider, don't round up)
- The moment a new reading is fetched, the ingestion service both writes it to PostGIS and publishes it to the `sensor.readings` Kafka topic
- The WebSocket bridge consumes from that topic and pushes the update to all connected clients within seconds of the message landing in Kafka
- The frontend updates the map without a page refresh or poll

Note this pipeline could be built with Postgres `LISTEN/NOTIFY` alone at this data volume — Kafka is not required by throughput here. It's included because you specifically want the hands-on experience (topics, consumer groups, offsets, at-least-once delivery semantics) as a foundation for larger systems later. Say that plainly in the README rather than implying the data volume demanded it — a reviewer who knows the space will ask "why Kafka for one sensor feed," and "I wanted to learn it properly on a real system, not just a tutorial" is a better answer than pretending it was a scaling necessity.

This is an honest, real-time system on the ingestion→client side, even though the *source* data itself only updates every few minutes. Be upfront about this distinction in the README: "real-time" describes the pipeline's responsiveness, not artificial data freshness the source API doesn't provide. Overclaiming here is the fastest way to lose credibility in a technical interview.

---

## 5. Data model (PostGIS)

### Static layer
- `buildings`: id, geometry (polygon), height, source (OSM), imported_at
- `neighborhood_bounds`: id, geometry (polygon) — defines the AOI for all queries

### Dynamic layer
- `sensor_readings`: id, station_id, geometry (point), reading_type (temp/precip/wind/humidity), value, unit, recorded_at, ingested_at
- Index: GiST spatial index on geometry, btree index on recorded_at, composite index on (station_id, recorded_at) for time-series queries

### Forecast layer
- `forecasts`: id, station_id, geometry (point), reading_type, predicted_value, target_time, model_version, generated_at
- Store `model_version` so you can compare predictions across model iterations later — small thing, signals you're thinking about ML ops, not just training a model once

### Migrations
Use Alembic from day one. Don't hand-edit schema. This is a small effort investment that's an easy thing to point to as evidence of engineering maturity.

---

## 6. Explicit architectural decisions (and why)

Document these in the README — they preempt the obvious questions a reviewer would ask.

| Decision | Reasoning |
|---|---|
| Kafka included despite low data volume | Deliberate learning choice, not a throughput requirement — this data volume doesn't need it. Included to get real hands-on experience with topics, partitions, consumer groups, and delivery semantics on a working system rather than a tutorial. Stated honestly in the README rather than implied as a scaling necessity. |
| Single Kafka broker, not a cluster | A cluster adds replication, leader election, and failure-mode complexity that's a separate learning project on its own. One broker is enough to learn the producer/consumer/topic model correctly; cluster HA is a good "next thing to learn" note for future work, not this project. |
| Terraform included despite single-environment deployment | Same rationale as Kafka — IaC fundamentals (providers, state, modules, plan/apply) are the goal, not solving a multi-environment problem this project doesn't have. Kept to one environment so the IaC itself stays learnable rather than turning into its own multi-week side project. |
| No microservices split | Ingestion, forecast worker, WebSocket bridge, and API are separate deployable units (this is partly what Kafka enables) but share one repo/codebase for development simplicity. This is a reasonable middle ground between a monolith and a fully split microservices system. |
| FastAPI over Express/Django | Native async support fits the WebSocket + polling ingestion pattern; auto-generated OpenAPI docs are a nice secondary benefit for the writeup. |
| Single neighborhood scope | Keeps the static data import tractable and keeps the demo legible — a full city of buildings is a rendering-performance project, not a backend project, and would pull time away from the stated goal. |

### 6a. Cloud infrastructure and cost management

- **Database:** default to Supabase (managed Postgres + PostGIS, generous free tier, no credit card needed to start) unless AWS Educate credits come through — RDS is more consistent with the "learn AWS via Terraform" goal, but Supabase de-risks the project if credits don't materialize or expire mid-project. Terraform can provision either; the Terraform learning objective doesn't depend on which one you pick.
- **Compute for Kafka + services:** this is where actual cost risk lives. A broker plus 3-4 small services running continuously for a month will draw down credits faster than the DB will. Budget for this explicitly: check your actual AWS Educate balance before committing to EC2, and set a billing alarm via Terraform (a CloudWatch billing alarm module) on day one so a misconfigured resource doesn't quietly burn through a month of credits in a weekend.
- **Fallback if credits don't come through or run out:** run Kafka and the services locally via Docker Compose during development, and only pay for cloud compute during the final deployed-demo phase (Week 4). You still write the same Terraform either way — you're just choosing when to point `terraform apply` at a real cloud account.
- **Verify eligibility first:** AWS Educate's current offering has shifted over the past couple of years and different sources describe different credit amounts, so confirm what you're actually eligible for at the AWS Educate signup page with your school email before this becomes a planning assumption. If it falls through, the GitHub Student Developer Pack is worth checking as a secondary source of cloud credits.

---

## 7. Forecasting model

- **Task:** predict the target reading type (e.g. temperature) 1 hour ahead, per station
- **Approach:** start with a simple, correctly-validated baseline (e.g. seasonal naive or ARIMA) before reaching for anything more complex — a well-validated simple model is more credible than an unvalidated complex one
- **If time allows:** compare against XGBoost on engineered lag/time features, or Prophet
- **Validation:** proper train/test split respecting time order (no shuffling), report MAE/RMSE, and be ready to explain the number honestly rather than cherry-picking a good window
- **Serving:** forecast worker runs on a schedule (e.g. every 15 min), writes to the `forecasts` table, API serves latest forecast per station

---

## 8. API surface

**REST (FastAPI, auto-documented via OpenAPI):**
- `GET /buildings?bbox=...` — static building geometries for the AOI
- `GET /readings?station_id=&reading_type=&from=&to=` — historical sensor data
- `GET /forecasts?station_id=&reading_type=` — latest forecast

**WebSocket:**
- `/ws/live` — client subscribes, receives a message on every new reading write for the AOI

**Non-functional:**
- Rate limiting on REST endpoints (slowapi or similar)
- Input validation via Pydantic models throughout
- Structured error responses, not raw stack traces

---

## 9. Frontend scope (kept deliberately minimal — 30% of project time)

- CesiumJS scene with imported OSM building footprints for the target neighborhood
- Live sensor markers, colored/sized by current reading value, updating via WebSocket without refresh
- Forecast overlay (toggle-able) showing predicted values
- One layer toggle panel — buildings on/off, live data on/off, forecast on/off
- No auth, no user accounts, no multi-neighborhood switching in v1

---

## 10. Testing

- Pytest coverage on: ingestion validation logic, API endpoint responses, forecast worker output shape
- At least one integration test that runs the ingestion → DB → API path end-to-end against a test database
- This is a good-faith minimum, not full coverage — the point is showing you write tests at all, which most portfolio projects skip entirely

---

## 11. Deployment

- Backend + worker + Kafka broker: AWS (or wherever your credits land), provisioned entirely through Terraform — no manual console clicking, that defeats the point of including it
- Database: Supabase or RDS (see 6a)
- Frontend: static hosting (Vercel/Netlify) — no reason to route this through Terraform/AWS, keep it simple
- Must stay up after the project is "done" — a dead demo link is worse than no link. If cloud costs make that impractical past the demo period, keep the Terraform config and a recorded demo, and note in the README that it can be redeployed with `terraform apply` on request — that's a legitimate and honest thing to say
- Environment variables and cloud credentials via Terraform variables / a secrets manager, never committed

---

## 12. Timeline (6 weeks, ~70% backend / 30% frontend)

Honest note on scope: adding Kafka and Terraform to the original 4-week plan without adjusting the timeline would just mean cutting corners on both — either shipping Kafka/Terraform in name only (a broker you never really configure, a Terraform script you write once and never touch again) or blowing the deadline. Two extra weeks buys you enough room to actually learn these tools rather than cargo-cult them in. If a month is a hard ceiling, the honest trade is to drop one of Kafka or Terraform, not to keep both and rush.

**Week 1 — Data + spatial foundation**
- PostGIS schema + Alembic migrations (Supabase or local Postgres to start, no cloud dependency yet)
- Import OSM buildings for target neighborhood
- Ingestion service: fetch → validate → write, tested against real API
- Confirm actual API rate limits and update Section 4.1 with real numbers
- Confirm AWS Educate / GitHub Student Pack credit eligibility this week, before any infra decisions depend on it

**Week 2 — Kafka fundamentals + local pipeline**
- Run Kafka locally (Docker Compose) — get comfortable with topics, producers, consumers, consumer groups before touching cloud infra
- Wire ingestion service to publish to `sensor.readings`
- Build the WebSocket bridge as a Kafka consumer, confirm push-to-client works end to end, locally
- This week is explicitly about the Kafka learning curve — budget for reading docs and hitting confusing errors, don't expect it to go as smoothly as a library you already know

**Week 3 — API + forecasting**
- FastAPI REST endpoints
- Forecast worker as a second Kafka consumer, baseline model properly validated
- Second model if time allows, compared against baseline
- Wire forecast into API and into the `forecasts.generated` topic

**Week 4 — Terraform + cloud infrastructure**
- Write Terraform modules incrementally: start with just the database (RDS or confirm Supabase path), apply, verify, then add compute for one service at a time rather than writing the whole stack blind
- Set the CloudWatch billing alarm before provisioning anything that costs money
- Get one service (start with ingestion) running in the cloud end-to-end before adding the rest — this catches config mistakes early instead of debugging five services at once
- This week is where the actual infra-as-code learning happens; don't rush it to protect Week 5-6

**Week 5 — Full cloud deployment + frontend**
- Finish provisioning remaining services (Kafka broker, forecast worker, WebSocket bridge, API) via Terraform
- CesiumJS scene, live overlay, forecast overlay
- Confirm the full pipeline works against the cloud deployment, not just locally

**Week 6 — Stabilization + writeup**
- Let the deployed system run for several days, watch for anything that falls over unattended (this is where Kafka consumer lag, dropped connections, or a forgotten billing cap tends to surface)
- README: architecture diagram, decisions table (Section 6 and 6a), setup instructions, demo link, honest description of what "real-time" means here and why Kafka/Terraform are included
- Record a short demo clip as a fallback in case the live link or cloud budget runs out after the fact

---

## 13. Success criteria

- A stranger can open the live link and see the map update on its own within the polling interval, with no page refresh
- The README's architecture section can be read and understood in under 5 minutes
- Every claim in the resume bullet point traces to something actually running, not planned
- You can explain and defend every entry in the Section 6 decisions table in an interview without hedging
