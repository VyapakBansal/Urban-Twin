#!/usr/bin/env bash
# Stop Urban Twin long-running processes started by scripts/up.sh
# Usage: ./scripts/down.sh [--docker]

set -euo pipefail

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
