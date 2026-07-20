# Supabase setup for Urban Twin
#
# Supabase = hosted Postgres (+ Auth/Realtime/Storage). We use it as the
# spatial database instead of (or in addition to) local Docker PostGIS.
# The FastAPI app still talks SQLAlchemy/asyncpg — same schema via Alembic.

## 1. Create a project

1. Go to https://supabase.com → New project
2. Region: prefer **Canada** (or closest)
3. Save the database password

## 2. Enable PostGIS

SQL editor → run:

```sql
create extension if not exists postgis;
```

## 3. Connection strings

Project Settings → Database:

| Use | Env var | Example |
|---|---|---|
| Transaction pooler (app runtime) | `DATABASE_URL` | `postgresql+asyncpg://postgres.[ref]:[password]@aws-0-….pooler.supabase.com:6543/postgres` |
| Direct / session (Alembic migrations) | `DATABASE_URL_SYNC` | `postgresql+psycopg://postgres.[ref]:[password]@aws-0-….pooler.supabase.com:5432/postgres` |

Notes:
- Prefer **Session mode** port **5432** for Alembic (`upgrade head`).
- Prefer **Transaction** pooler **6543** for the async API if you stay under connection limits.
- Replace `postgresql://` with `postgresql+asyncpg://` (async) or `postgresql+psycopg://` (sync).

## 4. Migrate schema

```bash
# point .env at Supabase, then:
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m urban_twin.scripts.seed_aoi
.venv/Scripts/python.exe -m urban_twin.scripts.import_osm_buildings
```

## 5. Frontend (optional)

For Vercel, you may also set:

```
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

The Cesium map currently uses the FastAPI REST surface; Supabase client is reserved for future realtime/auth. Anon key is safe in the browser **only** with RLS policies — do not expose the service role key.

## 6. Kafka note

Supabase does not replace Kafka. For Vercel + Supabase demos:
- Keep ingest/forecast/API on a small always-on host (Azure VM / Railway / Render), **or**
- Run ingest as a cron hitting Supabase and skip live WebSocket until Realtime is wired.

Local Docker Compose remains the recommended path for Kafka during development.
