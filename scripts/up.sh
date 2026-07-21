#!/usr/bin/env bash
# Start Urban Twin stack: Docker → migrate → train (if needed) → ingest/forecast → API/WS/loops
# Usage:
#   ./scripts/up.sh
#   ./scripts/up.sh --with-frontend
#   npm run up
#   npm run dev   # up + Vite

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.run"
LOG_DIR="$RUN_DIR/logs"
PID_DIR="$RUN_DIR/pids"
WITH_FRONTEND=0
SKIP_TRAIN=0
SKIP_OSM=0

for arg in "$@"; do
  case "$arg" in
    --with-frontend|-f) WITH_FRONTEND=1 ;;
    --skip-train) SKIP_TRAIN=1 ;;
    --skip-osm) SKIP_OSM=1 ;;
    --help|-h)
      cat <<'EOF'
Urban Twin — start everything

Usage: ./scripts/up.sh [options]

  --with-frontend, -f   Also start Vite (localhost:5173)
  --skip-train          Do not train GBR models if missing
  --skip-osm            Do not import OSM buildings if DB empty
  --help                Show this help

Then open: http://127.0.0.1:5173  (with frontend) or API docs :8000/docs
Stop with:  ./scripts/down.sh   or   npm run down
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$LOG_DIR" "$PID_DIR"

if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  PY="$ROOT/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  echo "No .venv found. Create one:" >&2
  echo "  python -m venv .venv && .venv/Scripts/python.exe -m pip install -e \".[dev]\"" >&2
  exit 1
fi

already_running() {
  local name="$1"
  local pidfile="$PID_DIR/$name.pid"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    rm -f "$pidfile"
  fi
  return 1
}

start_bg() {
  local name="$1"
  shift
  if already_running "$name"; then
    echo "  · $name already running (pid $(cat "$PID_DIR/$name.pid"))"
    return 0
  fi
  echo "  · starting $name"
  nohup "$@" >"$LOG_DIR/$name.log" 2>&1 &
  echo $! >"$PID_DIR/$name.pid"
}

wait_http() {
  local url="$1"
  local label="$2"
  local tries="${3:-40}"
  local i=0
  while (( i < tries )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "  · $label ready"
      return 0
    fi
    sleep 1
    ((i++)) || true
  done
  echo "WARN: $label not ready after ${tries}s — check $LOG_DIR" >&2
  return 1
}

echo "==> Urban Twin up"
echo "    root: $ROOT"
echo "    python: $PY"

# --- env ---
if [[ ! -f "$ROOT/.env" ]]; then
  if [[ -f "$ROOT/.env.example" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "Created .env from .env.example — set OPENWEATHER_API_KEY before live weather works."
  else
    echo "Missing .env" >&2
    exit 1
  fi
fi

# --- docker ---
echo "==> Docker (PostGIS + Kafka)"
export MSYS_NO_PATHCONV=1
docker compose up -d

echo "==> Waiting for Postgres on :5433"
for i in $(seq 1 60); do
  if docker compose exec -T db pg_isready -U urban -d urban_twin >/dev/null 2>&1; then
    echo "  · db ready"
    break
  fi
  if (( i == 60 )); then
    echo "Postgres did not become ready" >&2
    exit 1
  fi
  sleep 1
done

echo "==> Waiting for Kafka on :9092"
for i in $(seq 1 60); do
  if docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
    echo "  · kafka ready"
    break
  fi
  if (( i == 60 )); then
    echo "Kafka did not become ready" >&2
    exit 1
  fi
  sleep 2
done

echo "==> Ensuring Kafka topics"
for topic in sensor.readings forecasts.generated drone.telemetry drone.control; do
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic "$topic" --partitions 1 --replication-factor 1 >/dev/null
done

# --- schema / seed ---
echo "==> Migrations + AOI seed"
"$PY" -m alembic upgrade head
"$PY" -m urban_twin.scripts.seed_aoi >/dev/null 2>&1 || true

# --- OSM buildings if empty ---
if [[ "$SKIP_OSM" -eq 0 ]]; then
  BUILDING_COUNT="$(
    "$PY" - <<'PY' 2>/dev/null || echo 0
import asyncio
from sqlalchemy import text
from urban_twin.db.session import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as s:
        n = (await s.execute(text("SELECT COUNT(*) FROM buildings"))).scalar()
        print(int(n or 0))

asyncio.run(main())
PY
  )"
  BUILDING_COUNT="$(echo "${BUILDING_COUNT:-0}" | tr -cd '0-9')"
  BUILDING_COUNT="${BUILDING_COUNT:-0}"
  if [[ "$BUILDING_COUNT" -lt 100 ]]; then
    echo "==> Importing OSM buildings (first run — ~1 min)"
    "$PY" -m urban_twin.scripts.import_osm_buildings || echo "WARN: OSM import failed (Overpass?); continue anyway"
  else
    echo "==> Buildings already loaded ($BUILDING_COUNT)"
  fi
fi

# --- train models if missing ---
if [[ "$SKIP_TRAIN" -eq 0 ]]; then
  if [[ ! -f "$ROOT/models/temp_24h.joblib" || ! -f "$ROOT/models/river_level_24h.joblib" ]]; then
    echo "==> Training 24h forecast models (first run — a few minutes)"
    "$PY" -m urban_twin.forecast.train || echo "WARN: training failed; forecasts may use persistence"
  else
    echo "==> Forecast models present"
  fi
fi

# --- long-running services ---
echo "==> Starting services"
start_bg api "$PY" -m urban_twin.api.main
start_bg ws "$PY" -m urban_twin.websocket_bridge.main
start_bg ingest "$PY" -m urban_twin.ingestion.main
start_bg forecast "$PY" -m urban_twin.forecast.main --model gbr

wait_http "http://127.0.0.1:8000/health" "API :8000" 45 || true

# --- one-shot refresh so the map has data immediately ---
echo "==> Refresh ingest + 24h forecasts"
"$PY" -m urban_twin.ingestion.main --once || echo "WARN: ingest --once had errors"
"$PY" -m urban_twin.forecast.main --once || echo "WARN: forecast --once had errors"

# --- frontend ---
if [[ "$WITH_FRONTEND" -eq 1 ]]; then
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    echo "==> npm install (frontend)"
    (cd "$ROOT/frontend" && npm install)
  fi
  # cd into frontend so Windows npm never sees a Git-Bash /c/... path
  # (MSYS can turn --prefix /c/Projects/... into C:\c\Projects\...).
  if already_running vite; then
    echo "  · vite already running (pid $(cat "$PID_DIR/vite.pid"))"
  else
    echo "  · starting vite"
    (
      cd "$ROOT/frontend"
      nohup npm run dev -- --host 127.0.0.1 --port 5173 >"$LOG_DIR/vite.log" 2>&1 &
      echo $! >"$PID_DIR/vite.pid"
    )
  fi
  wait_http "http://127.0.0.1:5173" "Vite :5173" 60 || true
fi

cat <<EOF

Urban Twin is up.

  API docs     http://127.0.0.1:8000/docs
  WebSocket    ws://127.0.0.1:8001/ws/live
  Map (Vite)   http://127.0.0.1:5173
  Logs         $LOG_DIR
  PIDs         $PID_DIR

  Stop:  npm run down   or   ./scripts/down.sh
EOF

if [[ "$WITH_FRONTEND" -eq 0 ]]; then
  echo "  Tip:  npm run dev   starts stack + frontend together"
fi
