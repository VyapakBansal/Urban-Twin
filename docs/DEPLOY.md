# Deploy path — Supabase → API host → Vercel

Urban Twin splits into three pieces:

| Piece | Where it runs | Why |
|---|---|---|
| **Postgres + PostGIS** | [Supabase](https://supabase.com) | Managed spatial DB |
| **API + ingest + forecast + WS** | Always-on host (Azure VM / Railway / Render) | Not serverless-friendly |
| **Cesium map (Vite SPA)** | [Vercel](https://vercel.com) | Static frontend |

Kafka stays optional for cloud demos: you can run ingest on a schedule writing to Supabase and serve REST from the API host; live WebSocket needs a persistent process.

**Drone simulation** is designed for **local** use (PX4 in WSL2 + MAVSDK bridge). A Vercel-hosted map does not include `/ws/drone` unless you deploy the WebSocket bridge with `wss://…/ws/drone` and optional cloud sim — see [DRONE.md](DRONE.md) and [infra/README.md](../infra/README.md).

---

## Phase A — Supabase (database)

1. Create a project (prefer **Canada** / closest region).
2. SQL editor:

```sql
create extension if not exists postgis;
```

3. Project Settings → Database → copy URIs into local `.env` (never commit):

```env
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[PASSWORD]@aws-0-….pooler.supabase.com:6543/postgres
DATABASE_URL_SYNC=postgresql+psycopg://postgres.[ref]:[PASSWORD]@aws-0-….pooler.supabase.com:5432/postgres
```

Use **session / 5432** for Alembic; **transaction pooler / 6543** for the async API when possible.

4. Migrate + seed (from repo root, venv active):

```bash
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m urban_twin.scripts.seed_aoi
.venv/Scripts/python.exe -m urban_twin.scripts.import_osm_buildings
.venv/Scripts/python.exe -m urban_twin.ingestion.main --once
```

5. Confirm:

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/buildings?bbox=-114.100,51.048,-114.062,51.062&limit=3"
```

(API must be pointed at the same `.env` / restarted after URL change.)

Details: Phase A in this file (above).

---

## Phase B — API host (required for Vercel map)

Vercel cannot run Kafka, long ingest loops, or LightGBM training. Pick one:

- **Azure demo VM** — [infra/README.md](../infra/README.md)
- **Railway / Render** — Docker or native Python process with the same `.env`

Minimum services on that host:

- FastAPI (`urban_twin.api.main`)
- WebSocket bridge (`urban_twin.websocket_bridge.main`) if you want live updates
- Periodic ingest + forecast (cron or long-running workers)

Bind for reverse proxy:

```env
API_HOST=0.0.0.0
WS_BRIDGE_HOST=0.0.0.0
CORS_ORIGINS=http://localhost:5173,https://YOUR-APP.vercel.app
```

Expose HTTPS publicly (or nginx TLS). Note the public base URLs, e.g.:

- `https://api.example.com`
- `wss://api.example.com/ws/live`

---

## Phase C — Vercel (frontend)

1. Import the GitHub repo in Vercel.
2. Settings:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |

3. Environment variables (Production):

| Name | Value |
|---|---|
| `VITE_API_BASE` | `https://api.example.com` |
| `VITE_WS_URL` | `wss://api.example.com/ws/live` |
| `VITE_CESIUM_ION_TOKEN` | optional |

4. Deploy. Open the Vercel URL on phone + desktop.

5. If the map loads but API is red: CORS on the API host must include the Vercel origin; rebuild frontend after changing `VITE_*` (they are bake-time).

Details: [VERCEL.md](VERCEL.md). CLI:

```bash
cd frontend
npx vercel
```

---

## Security checklist (STRIDE / OWASP)

- [ ] No `.env` / service-role keys in git or Vercel public vars
- [ ] Supabase **service role** never in the browser
- [ ] API rate limits on (`API_RATE_LIMIT`)
- [ ] CORS limited to known origins
- [ ] Postgres not world-open (Supabase pooler + password only)
- [ ] Tear down paid Azure VM when not demoing

---

## Suggested order this week

1. Supabase project + PostGIS + migrate + OSM import  
2. Point local `.env` at Supabase; `npm run up` still works with local Kafka  
3. Deploy API to a small host with CORS for Vercel  
4. Deploy `frontend/` to Vercel with `VITE_API_BASE` / `VITE_WS_URL`  
5. Smoke-test phone Safari/Chrome on the Vercel URL  
