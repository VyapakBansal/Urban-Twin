#!/usr/bin/env bash
# Start PX4 SITL in WSL2 (when on Windows), wait for readiness, then run the MAVSDK bridge.
#
# Usage:
#   npm run drone
#   ./scripts/drone.sh --skip-sim     # bridge only (PX4 already running)
#   ./scripts/drone.sh --sim-only     # PX4/Gazebo only

set -euo pipefail
export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/.run/logs"
PID_DIR="$ROOT/.run/pids"
SKIP_SIM=0
SIM_ONLY=0
PX4_STARTED=0

for arg in "$@"; do
  case "$arg" in
    --skip-sim) SKIP_SIM=1 ;;
    --sim-only) SIM_ONLY=1 ;;
    --help|-h)
      cat <<'EOF'
Urban Twin drone — PX4/Gazebo (WSL2) + MAVSDK bridge

Usage:
  npm run drone
  ./scripts/drone.sh [--skip-sim] [--sim-only]

  --skip-sim   Do not start PX4; connect bridge to an existing simulator
  --sim-only   Start PX4/Gazebo and exit (no bridge)

Typical local flow:
  Terminal 1:  npm run dev
  Terminal 2:  npm run drone
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

to_wsl_path() {
  local p="${1//\\//}"
  if [[ "$p" =~ ^/[a-zA-Z]/ ]]; then
    echo "/mnt/$(echo "${p:1:1}" | tr '[:upper:]' '[:lower:]')${p:2}"
    return 0
  fi
  if [[ "$p" =~ ^[A-Za-z]: ]]; then
    echo "/mnt/$(echo "${p:0:1}" | tr '[:upper:]' '[:lower:]')${p:2}"
    return 0
  fi
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -a "$p"
    return 0
  fi
  wsl wslpath -a "$p"
}

on_windows() {
  [[ "${OS:-}" == "Windows_NT" ]] || [[ "$(uname -s 2>/dev/null)" == MINGW* ]] || [[ "$(uname -s 2>/dev/null)" == MSYS* ]]
}

run_px4_script() {
  local wsl_root
  wsl_root="$(to_wsl_path "$ROOT")"
  if ! MSYS_NO_PATHCONV=1 wsl bash -lc "cd '$wsl_root' && test -f scripts/px4-sitl.sh"; then
    echo "Cannot reach repo in WSL at: $wsl_root" >&2
    echo "Expected: $(to_wsl_path "$ROOT")/scripts/px4-sitl.sh" >&2
    exit 1
  fi
  MSYS_NO_PATHCONV=1 wsl bash -lc "cd '$wsl_root' && export URBAN_TWIN_LOG_DIR=.run/logs URBAN_TWIN_PID_DIR=.run/pids && bash scripts/px4-sitl.sh --background"
}

stop_px4_sim() {
  if [[ "$PX4_STARTED" -eq 0 ]]; then
    return 0
  fi
  echo ""
  echo "==> Stopping PX4 SITL"
  if on_windows; then
    local wsl_root
    wsl_root="$(to_wsl_path "$ROOT")"
    MSYS_NO_PATHCONV=1 wsl bash -lc "cd '$wsl_root' && bash scripts/px4-sitl.sh --stop" || true
  else
    bash "$ROOT/scripts/px4-sitl.sh" --stop || true
  fi
}

wait_for_px4() {
  local log="$LOG_DIR/px4-sitl.log"
  local tries=90

  if on_windows; then
    if MSYS_NO_PATHCONV=1 wsl test -f ~/PX4-Autopilot/build/px4_sitl_default/bin/px4 2>/dev/null; then
      tries=90
    else
      tries=450
    fi
  elif [[ -f "$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4" ]]; then
    tries=90
  else
    tries=450
  fi

  echo "==> Waiting for PX4 SITL (up to $((tries * 2))s; first build can take ~15 min)"
  local i=0
  while (( i < tries )); do
    if [[ -f "$log" ]] && grep -qE \
      'Ready for takeoff|remote port 14540|Startup script returned successfully|Gazebo world is ready|px4 entered.*running|INFO  \[simulator_mavlink\]' \
      "$log" 2>/dev/null; then
      echo "  · PX4 SITL ready"
      return 0
    fi
    if [[ -f "$log" ]] && grep -qE 'ninja: build stopped|make: \*\*\*|PX4-Autopilot not found' "$log" 2>/dev/null; then
      echo "PX4 build/sim failed — tail of log:" >&2
      tail -n 30 "$log" >&2
      return 1
    fi
    sleep 2
    ((i++)) || true
  done

  echo "WARN: PX4 readiness timeout — starting bridge anyway (check $log)" >&2
  return 1
}

start_px4_sim() {
  echo "==> Starting PX4 + Gazebo"
  if on_windows; then
    if ! command -v wsl >/dev/null 2>&1; then
      echo "WSL not found. Install WSL2 or run with --skip-sim if PX4 is already up." >&2
      exit 1
    fi
    run_px4_script
  else
    export URBAN_TWIN_LOG_DIR="$LOG_DIR"
    export URBAN_TWIN_PID_DIR="$PID_DIR"
    bash "$ROOT/scripts/px4-sitl.sh" --background
  fi
  PX4_STARTED=1
  wait_for_px4 || true
}

cleanup_stale_mavsdk() {
  if ! on_windows; then
    return 0
  fi
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //IM mavsdk_server.exe >/dev/null 2>&1 || true
  fi
}

cleanup() {
  stop_px4_sim
}

if [[ "$SKIP_SIM" -eq 0 ]]; then
  start_px4_sim
fi

if [[ "$SIM_ONLY" -eq 1 ]]; then
  echo ""
  echo "PX4 SITL running. Logs: $LOG_DIR/px4-sitl.log"
  echo "Stop with:  npm run down"
  exit 0
fi

trap cleanup INT TERM

cleanup_stale_mavsdk

echo "==> Starting Urban Twin drone bridge"
echo "    MAVSDK: udpin://0.0.0.0:14540 (override with DRONE_SYSTEM_ADDRESS in .env)"
echo "    Ctrl+C stops the bridge and the WSL2 simulator started by this script"
echo ""

"$PY" -m urban_twin.drone.main "$@"
