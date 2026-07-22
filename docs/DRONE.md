# PX4 drone simulation — setup and operation

Urban Twin runs **PX4 SITL + Gazebo** as an independent simulator. A MAVSDK bridge converts MAVLink to Kafka, the WebSocket bridge relays `/ws/drone`, and the Cesium map renders one smoothed 3D vehicle with browser keyboard control.

This is a **simulated** vehicle with real PX4 flight dynamics — not a scripted path. Control latency is intended for same-machine / same-LAN use, not internet-scale teleoperation.

---

## Architecture

```text
WSL2/Linux                          Windows (or same Linux host)
┌─────────────────────┐             ┌──────────────────────────────┐
│ Gazebo ◄──► PX4     │  MAVLink    │ urban_twin.drone (MAVSDK)    │
│ SITL (UDP 14540)    │ ──relay──►  │  → Kafka drone.telemetry     │
│                     │             │  ← Kafka drone.control       │
│ mavlink-relay.py    │             │ WebSocket bridge /ws/drone   │
│ (WSL→Windows only)  │             │ React + Cesium map           │
└─────────────────────┘             └──────────────────────────────┘
```

| Component | Port / topic | Role |
|---|---|---|
| PX4 Offboard API | UDP `14540` | MAVLink stream |
| MAVLink relay | WSL only | Forwards WSL `127.0.0.1:14540` ↔ Windows host IP |
| Kafka | `drone.telemetry`, `drone.control` | Typed events |
| WebSocket | `ws://127.0.0.1:8001/ws/drone` | Browser telemetry + control |
| QGroundControl (optional) | UDP `14550` | Normal PX4 GCS link |

Do **not** run Urban Twin’s drone bridge and a separate PX4 teleop/offboard script at the same time — both compete for Offboard control.

---

## Platform support

| OS | PX4 / Gazebo | Urban Twin bridge | Notes |
|---|---|---|---|
| **Windows 10/11** | WSL2 (Ubuntu) | Windows Python venv | Primary tested path. Relay starts automatically in WSL. |
| **Linux** | Native `~/PX4-Autopilot` | Same machine | No MAVLink relay needed. |
| **macOS** | Possible with PX4 docs | Native Python | Gazebo/`gz_x500` setup varies; treat as advanced / self-supported. |

Minimum stack (all platforms):

- Docker Desktop — PostGIS + Kafka
- Python **3.11+** with project venv
- Node.js **18+**
- **WSL2 + Ubuntu** on Windows (for the simulator)

---

## One-time PX4 install

Run inside **WSL2** (Windows) or native **Linux**:

```bash
sudo apt update && sudo apt install -y build-essential git wget curl lsb-release ca-certificates gnupg python3
git clone https://github.com/PX4/PX4-Autopilot.git --recursive ~/PX4-Autopilot
cd ~/PX4-Autopilot
bash ./Tools/setup/ubuntu.sh --no-nuttx
```

First `make px4_sitl gz_x500` can take **10–20 minutes** (full compile). Use the PX4 target that already works on your machine if `gz_x500` differs.

Optional sanity check with QGroundControl before integrating Urban Twin: arm, takeoff, move, land on UDP 14550.

---

## Local setup (any machine)

### 1. Clone Urban Twin and configure `.env`

```bash
git clone https://github.com/VyapakBansal/Urban-Twin.git
cd Urban-Twin
cp .env.example .env
# Set OPENWEATHER_API_KEY=... (required for the rest of the twin)
```

Drone-related defaults in `.env` (usually fine as-is):

| Variable | Default | Meaning |
|---|---|---|
| `DRONE_SYSTEM_ADDRESS` | `udpin://0.0.0.0:14540` | MAVSDK listen address (**use `udpin://` on Windows**) |
| `DRONE_HOME_LAT/LON/ALT_M` | `51.053`, `-114.081`, `1045.0` | PX4 home origin (Kensington); must match `PX4_HOME_*` |
| `DRONE_TELEMETRY_HZ` | `20` | Kafka publish rate |
| `DRONE_MAX_*` / `DRONE_MIN/MAX_ALTITUDE_M` | see `.env.example` | Flight envelope enforced in the bridge |

### 2. Python + Node dependencies

```bash
python -m venv .venv

# Windows (Git Bash / PowerShell):
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# macOS / Linux:
# .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"

npm install   # root scripts only; frontend deps install on first dev run
```

### 3. Start the twin stack

**Terminal 1** — map, API, Kafka, WebSocket:

```bash
npm run dev
```

Open **http://127.0.0.1:5173**. Enable the **Drone** layer in the layer panel.

**Terminal 2** — PX4 + MAVSDK bridge:

```bash
npm run drone
```

Expected console output:

```text
==> Starting PX4 + Gazebo
  · mavlink relay pid … (WSL -> Windows UDP 14540)   # Windows + WSL only
  · PX4 SITL ready
==> Starting Urban Twin drone bridge
waiting for PX4 at udpin://0.0.0.0:14540
PX4 connected
```

Logs:

| Log | Path |
|---|---|
| PX4 / Gazebo | `.run/logs/px4-sitl.log` |
| MAVLink relay | `.run/logs/mavlink-relay.log` |
| Bridge / stack | `.run/logs/` (via `npm run dev`) |

Stop everything:

```bash
npm run down
```

This stops app processes, the WSL PX4 sim, the MAVLink relay, and stale `mavsdk_server.exe` on Windows.

### 4. npm drone commands

| Command | Purpose |
|---|---|
| `npm run drone` | WSL2/native sim + MAVSDK bridge (default) |
| `npm run drone:bridge` | Bridge only — PX4 already running |
| `npm run drone:sim` | Sim only — no bridge |

Environment overrides for `scripts/px4-sitl.sh`:

| Variable | Default |
|---|---|
| `PX4_DIR` | `~/PX4-Autopilot` |
| `PX4_SITL_TARGET` | `gz_x500` |
| `PX4_HOME_LAT/LON/ALT` | Same as `DRONE_HOME_*` |
| `URBAN_TWIN_MAVLINK_RELAY` | `1` (set `0` to disable relay on WSL) |

---

## Browser operation

1. Status bar: **WS** green when `/ws/drone` is open; **DRONE** green when live telemetry arrives.
2. Drone panel shows **waiting for PX4** until telemetry is fresh (< 1.5 s).
3. Click **Arm**, then **Take off**.
4. Use **WASD** + **Q/E** (desktop only; disabled on phone layout):
   - `W` / `S` — forward / back
   - `A` / `D` — strafe left / right
   - `Q` — climb · `E` — descend
5. **Follow** or **FPV** attaches the camera; **free** leaves the map camera alone (best for testing motion).
6. **Land**, then stop the bridge with Ctrl+C in the drone terminal or `npm run down`.

Closing the browser tab sends a **hold** command so the vehicle stops rather than continuing offboard input.

---

## Altitude on the map

PX4 reports **WGS84 ellipsoid height** (`altitude_m`, ~1045 m at Kensington home). Cesium photorealistic tiles and world terrain use a different vertical reference, so raw ellipsoid height looks “insanely high.”

The map **samples Cesium surface height** at the AOI center and renders at:

```text
visual height = sampledSurface + relative_altitude_m (AGL)
```

Position updates are **smoothed in a requestAnimationFrame loop** (~120 ms time constant) to avoid 20 Hz jitter and terrain reclamp snap-back.

If the vehicle is still slightly above/below ground after a hard refresh:

1. Wait for photorealistic tiles to finish loading (surface sample re-runs).
2. Fine-tune **`DRONE_HOME_ALT_M`** in `.env` and restart PX4 so sim home matches (single calibration knob — do not hard-code offsets in the frontend).

---

## Headless SITL arming (no QGroundControl)

On connect, the bridge sets PX4 parameters so arm/takeoff works without a GCS on UDP 14550:

- `CBRK_SUPPLY_CHK=894281` — skip sim power-rail check
- `NAV_DLL_ACT=0` — no data-link arming block
- `NAV_RCL_ACT=0` — no RC-link arming block
- `COM_RCL_EXCEPT=4` — allow offboard without physical RC

If arm still fails after upgrading the bridge code, restart `npm run drone` so this runs on a fresh PX4 session.

---

## MAVLink routing details

### Windows + WSL2 (default)

PX4 inside WSL sends MAVLink to `127.0.0.1:14540` **inside WSL**. Windows MAVSDK binding `0.0.0.0:14540` does not receive those packets directly.

`scripts/mavlink-relay.py` runs in WSL and bidirectionally forwards:

```text
127.0.0.1:14540 (PX4) ↔ <Windows-host-IP>:14540 (MAVSDK)
```

Started automatically by `scripts/px4-sitl.sh` when `/proc/version` indicates WSL. Disable with `URBAN_TWIN_MAVLINK_RELAY=0` only if you run the bridge inside WSL next to PX4.

### Linux (single host)

PX4 and the bridge share localhost — set `DRONE_SYSTEM_ADDRESS=udpin://0.0.0.0:14540`, no relay.

### Separate Linux laptop (sim on laptop, twin on Windows PC)

Allow UDP 14540 on the Windows private firewall, then from the PX4 shell (`pxh>`):

```text
mavlink start -x -u 14581 -r 4000000 -f -m onboard -o 14540 -t <WINDOWS_LAN_IP>
```

Verify with `mavlink status`. Use a trusted private LAN only.

---

## Verification (no Cesium tile quota)

```bash
.venv/Scripts/python.exe -m pytest tests/test_drone_transform.py
npm --prefix frontend run build
```

Quick connectivity check while `npm run drone` is running:

```bash
# Kafka telemetry (should print JSON within a few seconds)
.venv/Scripts/python.exe -c "
import asyncio, json
from aiokafka import AIOKafkaConsumer
async def main():
    c = AIOKafkaConsumer('drone.telemetry', bootstrap_servers='localhost:9092',
        auto_offset_reset='latest', consumer_timeout_ms=8000)
    await c.start()
    async for msg in c:
        print(json.loads(msg.value)['flight_mode'], json.loads(msg.value)['relative_altitude_m'])
        break
    await c.stop()
asyncio.run(main())
"
```

PX4 log should contain lines like `remote port 14540` and `Startup script returned successfully` in `.run/logs/px4-sitl.log` (repo path, not `~/PX4-Autopilot/.run/logs/`).

---

## Azure / cloud

The optional drone VM and bridge flags in Terraform default **off** (`enable_drone_bridge = false`, `enable_drone_vm = false`). The cheapest demo path is **Gazebo on your laptop** + bridge on the existing app VM.

See [infra/README.md](../infra/README.md) and `infra/terraform.tfvars.example` before enabling cloud sim compute.

Cloud Vercel frontends do **not** include PX4 or `/ws/drone` unless you deploy the WebSocket bridge and expose it — drone flythrough is designed for **local** use first.

---

## Troubleshooting

For symptom → cause → fix tables, see **[docs/DRONE_TROUBLESHOOTING.md](DRONE_TROUBLESHOOTING.md)**.

Common quick fixes:

| Symptom | Try |
|---|---|
| **waiting for PX4** forever | `npm run down` then `npm run drone`; confirm relay line + `PX4 connected` in bridge log |
| **Port 14540 in use** | `npm run down` (kills stale `mavsdk_server.exe`) |
| **Empty px4-sitl.log** | Restart sim after pulling latest `scripts/px4-sitl.sh` (log path fix) |
| **Won’t arm** | Restart bridge after code update; check `.run/logs/px4-sitl.log` for `Preflight Fail` |
| **Drone floating / jittery** | Hard refresh; use **free** camera; wait for terrain/tiles to load |
| **Flight bridge rejected** | See troubleshooting doc for the exact rejection reason |

---

## Related docs

| Doc | Purpose |
|---|---|
| [DRONE_TROUBLESHOOTING.md](DRONE_TROUBLESHOOTING.md) | Error catalog and diagnostics |
| [README.md](../README.md) | Full twin quick start |
| [CHANGES.md](../CHANGES.md) | Product scope for drone + visual fidelity |
| [.env.example](../.env.example) | All configuration variables |
