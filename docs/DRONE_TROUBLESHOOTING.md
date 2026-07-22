# Drone simulation — errors and troubleshooting

Reference for failures seen during local PX4 + Urban Twin integration. Each entry lists **symptoms**, **typical cause**, and **what to do**.

For setup steps, see [DRONE.md](DRONE.md).

---

## How to diagnose (in order)

1. **Stop cleanly:** `npm run down`
2. **Terminal 1:** `npm run dev` — confirm API `:8000`, WS `:8001`, Vite `:5173`
3. **Terminal 2:** `npm run drone` — watch for `mavlink relay`, `PX4 SITL ready`, `PX4 connected`
4. **Logs:**
   - `.run/logs/px4-sitl.log` — Gazebo / PX4 / preflight
   - `.run/logs/mavlink-relay.log` — WSL ↔ Windows UDP (Windows only)
   - Bridge stdout in terminal 2
5. **Browser:** hard refresh (Ctrl+Shift+R); status bar **WS** + **DRONE** green; drone panel not stuck on **waiting for PX4**
6. Still stuck → find your symptom below

---

## 1. Startup and environment

### WSL not found

| | |
|---|---|
| **Symptoms** | `npm run drone` exits: `WSL not found. Install WSL2…` |
| **Cause** | Windows without WSL2, or `wsl` not on PATH |
| **Fix** | Install WSL2 + Ubuntu (`wsl --install`), reboot, rerun. Or start PX4 manually in WSL and use `npm run drone:bridge` |

### Cannot reach repo in WSL / double `/mnt/c/c/…`

| | |
|---|---|
| **Symptoms** | `Cannot reach repo in WSL at: /mnt/c/c/Projects/…` |
| **Cause** | Git Bash path conversion mangled the project path |
| **Fix** | Use latest `scripts/drone.sh` / `scripts/down.sh` (manual `/mnt/c/…` conversion with `MSYS_NO_PATHCONV=1`). Run from repo root |

### PX4-Autopilot not found

| | |
|---|---|
| **Symptoms** | `PX4-Autopilot not found at: ~/PX4-Autopilot` in px4 log or script output |
| **Cause** | One-time PX4 clone/setup not done in WSL/Linux |
| **Fix** | Follow [DRONE.md — One-time PX4 install](DRONE.md#one-time-px4-install) inside WSL |

### PX4 first build / readiness timeout

| | |
|---|---|
| **Symptoms** | `Waiting for PX4 SITL (up to …s)` for many minutes; panel shows **waiting for PX4** |
| **Cause** | First compile of PX4 + Gazebo can take 10–20+ minutes |
| **Fix** | Tail `.run/logs/px4-sitl.log` — wait for `ninja` / `make` to finish. Subsequent starts are much faster |

### PX4 build failed

| | |
|---|---|
| **Symptoms** | Script prints `PX4 build/sim failed`; log contains `ninja: build stopped` or `make: ***` |
| **Cause** | Missing deps, wrong target, or Gazebo not installed |
| **Fix** | Re-run PX4 `Tools/setup/ubuntu.sh`. Try `make px4_sitl gz_x500` manually in WSL. Check disk space |

### PX4 exits immediately after start

| | |
|---|---|
| **Symptoms** | Log shows `PX4 Exiting…` / `Exiting NOW.` soon after boot; no sustained MAVLink |
| **Cause** | Gazebo crash, wrong `PX4_SITL_TARGET`, or resource limits in WSL |
| **Fix** | Run `./scripts/px4-sitl.sh` in foreground in WSL for live errors. Increase WSL memory in `.wslconfig` if OOM |

### Empty or stale `px4-sitl.log` in repo

| | |
|---|---|
| **Symptoms** | `.run/logs/px4-sitl.log` empty while sim runs; readiness never triggers |
| **Cause** | Older script `cd`'d to `~/PX4-Autopilot` before redirecting logs to a relative `.run/logs` there |
| **Fix** | Update to current `scripts/px4-sitl.sh` (anchors `LOG_DIR` to repo `ROOT`). Delete stray `~/PX4-Autopilot/.run/logs/px4-sitl.log` if huge |

### Python venv missing

| | |
|---|---|
| **Symptoms** | `No .venv found` from `drone.sh` |
| **Cause** | Dependencies not installed |
| **Fix** | `python -m venv .venv` and `pip install -e ".[dev]"` per [README](../README.md) |

### Docker / Kafka not running

| | |
|---|---|
| **Symptoms** | Bridge crashes on Kafka connect; ingest/API unhealthy |
| **Cause** | `npm run dev` not started or Docker stopped |
| **Fix** | Start Docker Desktop, `npm run dev`, confirm `localhost:9092` and `curl http://127.0.0.1:8000/health` |

---

## 2. MAVLink and MAVSDK connectivity

### UDP port 14540 already in use / bind error

| | |
|---|---|
| **Symptoms** | MAVSDK: `bind error` / `Address already in use`; bridge never logs `PX4 connected` |
| **Cause** | Stale `mavsdk_server.exe` or another listener on 14540 |
| **Fix** | `npm run down` (kills mavsdk on Windows). `netstat -ano \| findstr 14540` on Windows. Ensure only one `npm run drone` instance |

### Bridge waits forever — no `PX4 connected` (Windows + WSL)

| | |
|---|---|
| **Symptoms** | PX4 log shows `remote port 14540` in WSL; Windows bridge still waiting |
| **Cause** | WSL `127.0.0.1:14540` is not the same socket as Windows localhost — MAVLink never crosses the boundary |
| **Fix** | Confirm `mavlink relay pid … (WSL -> Windows UDP 14540)` in px4 start output. Check `.run/logs/mavlink-relay.log`. Do not set `URBAN_TWIN_MAVLINK_RELAY=0` unless bridge runs inside WSL |

### Wrong `DRONE_SYSTEM_ADDRESS`

| | |
|---|---|
| **Symptoms** | No MAVSDK connection on Windows |
| **Cause** | Using `udp://:14540` instead of **`udpin://0.0.0.0:14540`** (listen vs dial semantics) |
| **Fix** | Match [.env.example](../.env.example). Restart bridge after `.env` change |

### MAVLink relay not starting

| | |
|---|---|
| **Symptoms** | No relay pid line; Windows listener receives zero packets |
| **Cause** | Not running in WSL, relay disabled, or `python3` missing in WSL |
| **Fix** | `python3 --version` in WSL. `URBAN_TWIN_MAVLINK_RELAY=1` (default). Start sim via `npm run drone`, not raw `make` without relay |

### PX4 connected but no Kafka / WS telemetry

| | |
|---|---|
| **Symptoms** | Bridge logs `PX4 connected`; browser **waiting for PX4**; Kafka consumer silent |
| **Cause** | WebSocket bridge not running, or drone layer off |
| **Fix** | Confirm `npm run dev` includes WS on `:8001`. Enable **Drone** layer. `curl http://127.0.0.1:8001/health` |

---

## 3. PX4 preflight and arming

### Preflight Fail: system power unavailable

| | |
|---|---|
| **Symptoms** | Arm fails; px4 log repeats preflight failure |
| **Cause** | SITL power check without QGC |
| **Fix** | Bridge sets `CBRK_SUPPLY_CHK=894281` on connect — **restart `npm run drone`** after pulling bridge code |

### Preflight Fail: No connection to the GCS

| | |
|---|---|
| **Symptoms** | Arm blocked; no QGroundControl running |
| **Cause** | PX4 expects GCS heartbeat on classic UDP 14550 |
| **Fix** | Bridge sets `NAV_DLL_ACT=0` and related params — restart bridge. Optional: run QGC |

### Arm / Take off button no effect

| | |
|---|---|
| **Symptoms** | UI clicks; no mode change; no error in panel |
| **Cause** | No live telemetry, WS not open, or PX4 not connected to bridge |
| **Fix** | Fix MAVLink first. Panel must show flight mode + AGL, not **waiting for PX4** |

### PX4 arm / takeoff failed (bridge warning)

| | |
|---|---|
| **Symptoms** | Bridge log: `PX4 arm failed` / `PX4 takeoff failed` |
| **Cause** | Not in ready state, already armed, or preflight still failing |
| **Fix** | Read px4-sitl.log around the click time. Disarm in QGC if stuck. Restart sim |

---

## 4. WebSocket and browser UI

### WS status gray / reconnecting

| | |
|---|---|
| **Symptoms** | Status bar **WS** gray; panel **connecting…** or **reconnecting…** |
| **Cause** | WS bridge down, wrong port, Vite HMR reload, or CORS origin mismatch |
| **Fix** | `npm run dev` running. Page served from `http://127.0.0.1:5173` or `localhost:5173` matching `CORS_ORIGINS` in `.env` |

### Drone status **waiting for PX4** (WS open)

| | |
|---|---|
| **Symptoms** | **WS** green, **DRONE** gray; panel **waiting for PX4** |
| **Cause** | No telemetry on `/ws/drone` — MAVLink or bridge issue, or stale telemetry (> 1.5 s) |
| **Fix** | Fix sections 2–3. Confirm Kafka topic `drone.telemetry` updates |

### Drone status **bridge error**

| | |
|---|---|
| **Symptoms** | Panel shows **bridge error** |
| **Cause** | WebSocket closed abnormally |
| **Fix** | Check WS bridge logs in `.run/logs/`. Restart `npm run dev` |

### `drone.control.error` — validation failed

| | |
|---|---|
| **Symptoms** | Panel: **Flight bridge rejected the command**; WS payload with Pydantic `detail` array |
| **Cause** | Malformed control JSON (wrong types, bad `issued_at`, **`ttl_ms` > 2000**, etc.) |
| **Fix** | Hard refresh frontend. Valid `ttl_ms` is **100–2000** (default 500). Do not send custom keepalives with invalid TTL |

Common validation fields:

| Field | Constraint |
|---|---|
| `ttl_ms` | 100–2000 |
| `sequence` | must increase per `client_id` |
| `command` | `arm`, `takeoff`, `land`, `disarm`, `velocity_body`, `hold` |
| velocity fields | within schema max (±20 m/s horizontal, etc.) |

### WebSocket closed: origin not allowed

| | |
|---|---|
| **Symptoms** | `/ws/drone` closes immediately; code 1008 |
| **Cause** | Browser `Origin` header not in `CORS_ORIGINS` |
| **Fix** | Add your dev URL to `CORS_ORIGINS` in `.env`; restart WS bridge |

---

## 5. Control and flight envelope

Bridge and guard reject unsafe commands with `ControlRejected` — surfaced in the UI as **Flight bridge rejected the command** or in bridge logs as `rejected drone command: …`.

| Message | Meaning | Fix |
|---|---|---|
| `command is stale or has an invalid timestamp` | Clock skew or `issued_at` too old vs `ttl_ms` / timeout | Sync system clock; don’t pause debugger on control path |
| `command sequence must increase` | Duplicate or out-of-order `sequence` | Hard refresh; single browser tab controlling |
| `command rate exceeds the configured limit` | Faster than `DRONE_CONTROL_HZ` (~20 Hz) | Normal during spam — reduce key repeat or rate |
| `vehicle telemetry is not ready` | Velocity command before first position fix | Wait for live telemetry after takeoff |
| `horizontal speed exceeds the flight envelope` | \|forward,right\| above `DRONE_MAX_HORIZONTAL_SPEED_M_S` | Lower speeds in UI constants or `.env` max |
| `vertical speed exceeds the flight envelope` | \|down_m_s\| above max | Same |
| `yaw rate exceeds the flight envelope` | \|yaw_rate\| above max | Same |
| `command would cross the altitude envelope` | Predicted AGL outside min/max (default 2–120 m) | Climb/descend within limits |
| `command would cross the AOI geofence` | Predicted position outside `AOI_*` bbox | Fly back toward Kensington AOI |

### WASD / QE does nothing

| | |
|---|---|
| **Symptoms** | Keys ignored |
| **Cause** | Not armed, stale telemetry, phone layout, or focus in an input field |
| **Fix** | Arm + takeoff first. Desktop only. Click map to focus. Panel must not show **waiting for PX4** |

### Vehicle keeps moving after releasing keys

| | |
|---|---|
| **Symptoms** | Drift after key release |
| **Cause** | Last velocity command held until zero frame arrives |
| **Fix** | Expected short lag (< 500 ms). Close tab → bridge sends **hold** |

### Competing offboard clients

| | |
|---|---|
| **Symptoms** | Erratic motion; arm/offboard fights |
| **Cause** | QGC offboard, custom teleop script, or second bridge instance |
| **Fix** | Single controller: Urban Twin bridge only |

---

## 6. Cesium map rendering

### Drone appears very high above buildings

| | |
|---|---|
| **Symptoms** | Icon hundreds of meters above photorealistic tiles |
| **Cause** | Raw WGS84 ellipsoid height used instead of terrain-relative placement |
| **Fix** | Hard refresh (current `CesiumMap.tsx` uses surface sample + `relative_altitude_m`). Wait for tiles/terrain to load |

### Drone snaps back to same spot / jitter

| | |
|---|---|
| **Symptoms** | Icon rubber-bands while telemetry moves |
| **Cause** | `RELATIVE_TO_GROUND` reclamp every telemetry frame, or unsmoothed 20 Hz updates |
| **Fix** | Update frontend (rAF smoothing + ellipsoid + AGL). Use **free** camera to isolate entity motion vs camera |

### Follow / FPV camera motion feels bad

| | |
|---|---|
| **Symptoms** | Nauseating or jerky camera |
| **Cause** | Camera `setView` tied to raw telemetry |
| **Fix** | Camera follows **smoothed** pose; try **free** mode while tuning flight. Lower follow sensitivity if still needed |

### Drone invisible with layer on

| | |
|---|---|
| **Symptoms** | Layer enabled; no entity |
| **Cause** | Surface sample not finished and no fallback height yet |
| **Fix** | Wait 1–2 s after load. Pan map to AOI center. Check browser console for Cesium errors |

### Drone offset horizontally from expected position

| | |
|---|---|
| **Symptoms** | Wrong neighbourhood or shifted east/north |
| **Cause** | `DRONE_HOME_*` / `PX4_HOME_*` mismatch with actual sim home |
| **Fix** | Align all home lat/lon/alt env vars; restart PX4 |

---

## 7. Stop / cleanup

### PX4 or Gazebo orphaned after Ctrl+C

| | |
|---|---|
| **Symptoms** | Next start says already running; high CPU in WSL |
| **Fix** | `npm run down` or WSL: `./scripts/px4-sitl.sh --stop` |

### Huge log files

| | |
|---|---|
| **Symptoms** | Multi-GB `px4-sitl.log` |
| **Cause** | Verbose PX4 shell spam over long sessions; old log path under `~/PX4-Autopilot` |
| **Fix** | Truncate or delete logs. Use repo `.run/logs/` after script fix |

### `mavsdk_server.exe` zombie

| | |
|---|---|
| **Symptoms** | Bind errors on 14540 after crash |
| **Fix** | `npm run down` or Task Manager → end `mavsdk_server.exe` |

---

## 8. Azure / Terraform (optional cloud sim)

| Error / check | Meaning |
|---|---|
| `enable_drone_vm requires enable_demo_vm` | Drone VM needs the main demo host for MAVLink routing |
| `px4_git_ref` empty with drone VM enabled | Must pin a locally tested PX4 commit |
| `allowed_ssh_cidr` must be `/32` for drone VM | Open SSH restricted to your IP |
| NSG / `drone_mavlink_source_cidr` | UDP 14540 only from your sim laptop IP |
| Spot VM deallocated | Expected cost guard — restart VM for demo |

Cloud drone path is **off by default**. Local flythrough must pass before enabling.

---

## 9. Log grep cheatsheet

```bash
# PX4 ready?
grep -E 'remote port 14540|Startup script returned|Gazebo world is ready' .run/logs/px4-sitl.log | tail

# Preflight failures
grep -i 'preflight fail' .run/logs/px4-sitl.log | tail

# Relay running (WSL)
grep 'mavlink relay' .run/logs/mavlink-relay.log 2>/dev/null | tail

# Bridge rejections (run bridge in foreground or check app logs)
grep -i 'rejected drone command' .run/logs/*.log 2>/dev/null
```

---

## Still stuck?

Capture and include in an issue:

1. OS (Windows/Linux/macOS) and WSL version if applicable
2. Output of `npm run drone` through first 30 lines after start
3. Last 50 lines of `.run/logs/px4-sitl.log`
4. Browser status bar: WS / DRONE colors and drone panel label
5. Whether QGroundControl or another offboard tool is running
