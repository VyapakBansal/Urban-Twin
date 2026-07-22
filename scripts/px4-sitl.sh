#!/usr/bin/env bash
# Start PX4 SITL + Gazebo (run inside WSL2/Linux).
#
# Usage:
#   ./scripts/px4-sitl.sh              # foreground
#   ./scripts/px4-sitl.sh --background # detach (used by scripts/drone.sh)
#   ./scripts/px4-sitl.sh --stop       # stop background sim

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
PX4_SITL_TARGET="${PX4_SITL_TARGET:-gz_x500}"
PX4_HOME_LAT="${PX4_HOME_LAT:-51.053}"
PX4_HOME_LON="${PX4_HOME_LON:--114.081}"
PX4_HOME_ALT="${PX4_HOME_ALT:-1045.0}"
LOG_DIR="${URBAN_TWIN_LOG_DIR:-$ROOT/.run/logs}"
PID_DIR="${URBAN_TWIN_PID_DIR:-$ROOT/.run/pids}"
# make/px4 runs from PX4_DIR — anchor repo-relative paths before that cd
if [[ "$LOG_DIR" != /* ]]; then
  LOG_DIR="$ROOT/$LOG_DIR"
fi
if [[ "$PID_DIR" != /* ]]; then
  PID_DIR="$ROOT/$PID_DIR"
fi
PID_FILE="$PID_DIR/px4-sitl.pid"
BACKGROUND=0
STOP=0

for arg in "$@"; do
  case "$arg" in
    --background|-b) BACKGROUND=1 ;;
    --stop) STOP=1 ;;
    --help|-h)
      cat <<'EOF'
PX4 SITL + Gazebo for Urban Twin

Usage:
  ./scripts/px4-sitl.sh [--background]
  ./scripts/px4-sitl.sh --stop

Environment:
  PX4_DIR           Default: ~/PX4-Autopilot
  PX4_SITL_TARGET   Default: gz_x500
  PX4_HOME_LAT/LON/ALT   Kensington origin (must match DRONE_HOME_* in .env)
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"
RELAY_PID_FILE="$PID_DIR/mavlink-relay.pid"

start_mavlink_relay() {
  if [[ "${URBAN_TWIN_MAVLINK_RELAY:-1}" == "0" ]]; then
    return 0
  fi
  if ! grep -qi microsoft /proc/version 2>/dev/null; then
    return 0
  fi
  if [[ -f "$RELAY_PID_FILE" ]]; then
    local relay_pid
    relay_pid="$(cat "$RELAY_PID_FILE")"
    if kill -0 "$relay_pid" 2>/dev/null; then
      return 0
    fi
    rm -f "$RELAY_PID_FILE"
  fi
  nohup python3 "$ROOT/scripts/mavlink-relay.py" >>"$LOG_DIR/mavlink-relay.log" 2>&1 &
  echo $! >"$RELAY_PID_FILE"
  echo "  · mavlink relay pid $(cat "$RELAY_PID_FILE") (WSL -> Windows UDP 14540)"
}

stop_mavlink_relay() {
  if [[ -f "$RELAY_PID_FILE" ]]; then
    local relay_pid
    relay_pid="$(cat "$RELAY_PID_FILE")"
    if kill -0 "$relay_pid" 2>/dev/null; then
      kill "$relay_pid" 2>/dev/null || true
    fi
    rm -f "$RELAY_PID_FILE"
  fi
  pkill -f "scripts/mavlink-relay.py" 2>/dev/null || true
}

stop_sim() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  · stopping PX4 SITL (pid $pid)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
  pkill -f "px4_sitl_default/bin/px4" 2>/dev/null || true
  pkill -f "gz sim" 2>/dev/null || true
  stop_mavlink_relay
}

if [[ "$STOP" -eq 1 ]]; then
  echo "==> PX4 SITL down"
  stop_sim
  exit 0
fi

if pgrep -f "px4_sitl_default/bin/px4" >/dev/null 2>&1; then
  echo "PX4 SITL already running — skipping start"
  start_mavlink_relay
  exit 0
fi

if [[ ! -d "$PX4_DIR" ]]; then
  echo "PX4-Autopilot not found at: $PX4_DIR" >&2
  echo "Clone it in WSL2:" >&2
  echo "  git clone https://github.com/PX4/PX4-Autopilot.git --recursive ~/PX4-Autopilot" >&2
  echo "  cd ~/PX4-Autopilot && bash ./Tools/setup/ubuntu.sh --no-nuttx" >&2
  exit 1
fi

export PX4_HOME_LAT PX4_HOME_LON PX4_HOME_ALT
cd "$PX4_DIR"

echo "==> PX4 SITL ($PX4_SITL_TARGET)"
echo "    dir:   $PX4_DIR"
echo "    home:  $PX4_HOME_LAT, $PX4_HOME_LON @ ${PX4_HOME_ALT}m"

if [[ "$BACKGROUND" -eq 1 ]]; then
  stop_sim
  start_mavlink_relay
  nohup make px4_sitl "$PX4_SITL_TARGET" >"$LOG_DIR/px4-sitl.log" 2>&1 &
  echo $! >"$PID_FILE"
  echo "  · started in background (pid $(cat "$PID_FILE"))"
  echo "  · log: $LOG_DIR/px4-sitl.log"
  exit 0
fi

exec make px4_sitl "$PX4_SITL_TARGET"
