#!/usr/bin/env bash
# Urban Twin — first-boot / re-run bootstrap on the Azure demo VM.
# Idempotent enough to re-run safely after cloud-init.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/urban-twin}"
GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/VyapakBansal/Urban-Twin.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"
RUN_DIR="$APP_DIR/.run"
LOG_DIR="$RUN_DIR/logs"
PID_DIR="$RUN_DIR/pids"
export DEBIAN_FRONTEND=noninteractive

log() { echo "[bootstrap $(date -u +%H:%M:%S)] $*"; }

mkdir -p "$LOG_DIR" "$PID_DIR"

# --- packages ---
if ! command -v docker >/dev/null 2>&1; then
  log "installing docker"
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git nginx python3 python3-venv python3-pip
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi

# Node 20 for frontend build
if ! command -v node >/dev/null 2>&1; then
  log "installing node 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# --- clone / update repo ---
if [[ ! -d "$APP_DIR/.git" ]]; then
  log "cloning $GIT_REPO_URL → $APP_DIR"
  rm -rf "$APP_DIR"
  git clone --branch "$GIT_BRANCH" --depth 1 "$GIT_REPO_URL" "$APP_DIR"
else
  log "updating repo"
  git -C "$APP_DIR" fetch origin "$GIT_BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$GIT_BRANCH"
fi

cd "$APP_DIR"

# --- .env (cloud-init writes secrets; keep if present) ---
if [[ ! -f "$APP_DIR/.env" ]]; then
  if [[ -f /etc/urban-twin.env ]]; then
    cp /etc/urban-twin.env "$APP_DIR/.env"
  else
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    log "WARN: no /etc/urban-twin.env — fill OPENWEATHER_API_KEY"
  fi
fi

# Ensure CORS includes this host's public IP if detectable
PUBLIC_IP="$(curl -sf --max-time 5 https://api.ipify.org || true)"
if [[ -n "$PUBLIC_IP" ]]; then
  if ! grep -q "CORS_ORIGINS=.*${PUBLIC_IP}" "$APP_DIR/.env" 2>/dev/null; then
    # append / replace CORS line
    if grep -q '^CORS_ORIGINS=' "$APP_DIR/.env"; then
      sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://${PUBLIC_IP}|" "$APP_DIR/.env"
    else
      echo "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://${PUBLIC_IP}" >> "$APP_DIR/.env"
    fi
  fi
fi

# --- python venv ---
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  log "creating venv + installing package"
  python3 -m venv "$APP_DIR/.venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
pip install -U pip
pip install -e ".[dev]"

PY="$APP_DIR/.venv/bin/python"

# --- docker data plane ---
log "starting PostGIS + Kafka"
docker compose -f "$APP_DIR/deploy/docker-compose.azure.yml" up -d

log "waiting for postgres"
for i in $(seq 1 60); do
  if docker compose -f "$APP_DIR/deploy/docker-compose.azure.yml" exec -T db \
    pg_isready -U urban -d urban_twin >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

log "waiting for kafka"
for i in $(seq 1 60); do
  if docker compose -f "$APP_DIR/deploy/docker-compose.azure.yml" exec -T kafka \
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# --- schema + seed ---
log "migrations + AOI"
cd "$APP_DIR"
"$PY" -m alembic upgrade head
"$PY" -m urban_twin.scripts.seed_aoi || true

BUILDING_COUNT="$("$PY" - <<'PY' 2>/dev/null || echo 0
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
  log "importing OSM buildings"
  "$PY" -m urban_twin.scripts.import_osm_buildings || log "WARN: OSM import failed"
fi

if [[ ! -f "$APP_DIR/models/temp_24h.joblib" || ! -f "$APP_DIR/models/river_level_24h.joblib" ]]; then
  log "training 24h forecast models"
  "$PY" -m urban_twin.forecast.train || log "WARN: training failed"
fi

start_bg() {
  local name="$1"
  shift
  local pidfile="$PID_DIR/$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    log "$name already running"
    return 0
  fi
  log "starting $name"
  nohup "$@" >"$LOG_DIR/$name.log" 2>&1 &
  echo $! >"$pidfile"
}

# stop old processes if re-running
for name in api ws ingest forecast; do
  if [[ -f "$PID_DIR/$name.pid" ]]; then
    kill "$(cat "$PID_DIR/$name.pid")" 2>/dev/null || true
    rm -f "$PID_DIR/$name.pid"
  fi
done

start_bg api "$PY" -m urban_twin.api.main
start_bg ws "$PY" -m urban_twin.websocket_bridge.main
start_bg ingest "$PY" -m urban_twin.ingestion.main
start_bg forecast "$PY" -m urban_twin.forecast.main --model gbr

sleep 3
log "one-shot ingest + forecast"
"$PY" -m urban_twin.ingestion.main --once || log "WARN: ingest errors"
"$PY" -m urban_twin.forecast.main --once || log "WARN: forecast errors"

# --- frontend build ---
log "building frontend"
cd "$APP_DIR/frontend"
npm install
npm run build

# --- nginx ---
log "configuring nginx"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/nginx.conf
systemctl enable nginx
systemctl restart nginx

log "bootstrap complete"
if [[ -n "${PUBLIC_IP:-}" ]]; then
  echo "Map:  http://${PUBLIC_IP}/"
  echo "API:  http://${PUBLIC_IP}/api/health"
fi
