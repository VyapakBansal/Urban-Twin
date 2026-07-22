#!/usr/bin/env bash
# Stop Urban Twin long-running processes started by scripts/up.sh
# Usage: ./scripts/down.sh [--docker]

set -euo pipefail

export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/.run/pids"
STOP_DOCKER=0

for arg in "$@"; do
  case "$arg" in
    --docker) STOP_DOCKER=1 ;;
    --help|-h)
      echo "Usage: ./scripts/down.sh [--docker]"
      echo "  --docker   also docker compose down (keeps DB volume)"
      exit 0
      ;;
  esac
done

echo "==> Urban Twin down"

stop_px4_sim() {
  if ! command -v wsl >/dev/null 2>&1; then
    return 0
  fi
  local wsl_root
  local root="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  local p="${root//\\//}"
  if [[ "$p" =~ ^/[a-zA-Z]/ ]]; then
    local drive="${p:1:1}"
    local rest="${p:2}"
    wsl_root="/mnt/$(echo "$drive" | tr '[:upper:]' '[:lower:]')$rest"
  elif [[ "$p" =~ ^[A-Za-z]: ]]; then
    wsl_root="/mnt/$(echo "${p:0:1}" | tr '[:upper:]' '[:lower:]')${p:2}"
  elif command -v wslpath >/dev/null 2>&1; then
    wsl_root="$(wslpath -a "$root")"
  else
    wsl_root="$(wsl wslpath -a "$root" 2>/dev/null || true)"
  fi
  if [[ -n "${wsl_root:-}" ]]; then
    echo "  · stopping PX4 SITL (WSL2)"
    MSYS_NO_PATHCONV=1 wsl bash -lc "cd '$wsl_root' && bash scripts/px4-sitl.sh --stop" 2>/dev/null || true
  fi
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //IM mavsdk_server.exe >/dev/null 2>&1 || true
  fi
}

if [[ -f "$PID_DIR/px4-sitl.pid" ]] || command -v wsl >/dev/null 2>&1; then
  stop_px4_sim
fi

if [[ -d "$PID_DIR" ]]; then
  for pidfile in "$PID_DIR"/*.pid; do
    [[ -f "$pidfile" ]] || continue
    name="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  · stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      # Vite / nested shells may leave children — best-effort
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
    else
      echo "  · $name not running"
    fi
    rm -f "$pidfile"
  done
else
  echo "  · no pid dir (nothing to stop)"
fi

# Extra: free common ports if orphans remain (Windows / Git Bash)
for port in 8000 8001 5173; do
  if command -v netstat >/dev/null 2>&1; then
    :
  fi
done

if [[ "$STOP_DOCKER" -eq 1 ]]; then
  echo "==> docker compose down"
  export MSYS_NO_PATHCONV=1
  (cd "$ROOT" && docker compose down)
else
  echo "  (Docker left running — pass --docker to stop PostGIS/Kafka)"
fi

echo "Done."
