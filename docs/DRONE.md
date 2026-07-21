# PX4/Gazebo drone integration

The simulator remains an independent process. Urban Twin receives MAVLink,
publishes typed telemetry to Kafka, relays the latest value through
`/ws/drone`, and updates one persistent Cesium entity.

## Local topology

```text
Linux: Gazebo <-> PX4 SITL --MAVLink UDP 14540--> Urban Twin drone bridge
                                                     |
                          browser /ws/drone <-> Kafka drone.* topics
```

QGroundControl can remain connected to PX4 on its normal UDP 14550 link.
Do not run the standalone `teleop` script and the Urban Twin drone bridge at
the same time; both would compete for Offboard control.

## 1. Start PX4 at the fixed Kensington origin

On the Linux simulator:

```bash
cd ~/PX4-Autopilot
PX4_HOME_LAT=51.053 \
PX4_HOME_LON=-114.081 \
PX4_HOME_ALT=1045.0 \
make px4_sitl gz_x500
```

Use the exact PX4 target that already works on your laptop if it differs from
`gz_x500`. Confirm arm, takeoff, movement, and landing in QGroundControl first.

`DRONE_HOME_ALT_M` is WGS84 ellipsoid height. If the Cesium vehicle is
consistently above or below the textured ground, calibrate this one value;
do not add an arbitrary offset in the frontend.

## 2. Route MAVLink to Urban Twin

Same machine/WSL: PX4 normally sends the Offboard API stream to
`127.0.0.1:14540`, matching the default `DRONE_SYSTEM_ADDRESS=udp://:14540`.

Separate Linux laptop: allow inbound UDP 14540 in the Windows private-network
firewall, then add a dedicated PX4 API link from the `pxh>` shell:

```text
mavlink start -x -u 14581 -r 4000000 -f -m onboard -o 14540 -t <WINDOWS_LAN_IP>
```

Verify with `mavlink status`. Keep both machines on a trusted private LAN.

## 3. Start the local stack and bridge

Windows:

```bash
npm run dev
npm run drone
```

The drone process waits safely if PX4 is not connected. Expected path:

```text
PX4 -> drone.telemetry -> /ws/drone -> Cesium
browser -> /ws/drone -> drone.control -> PX4
```

## 4. Browser operation

1. Wait for the Drone panel to show a PX4 flight mode.
2. Select **Arm**, then **Take off**.
3. After **Arm** + **Take off**, use WASDQE:
   - `W/S`: forward/back
   - `A/D`: left/right strafe
   - `Q`: climb · `E`: descend
4. Select **Follow** or **FPV** for the drone camera.
5. Select **Land** before stopping the bridge.

The bridge rejects stale/replayed commands, excessive command rates, speeds
outside the configured limits, altitude violations, and predicted AOI
geofence violations. Lost browser input becomes a zero-velocity hold within
500 ms.

## Verification without Cesium tile usage

```bash
.venv/Scripts/python.exe -m pytest
npm --prefix frontend run build
```

These checks do not open the map and consume no Google tile quota.

## Azure cost gate

Terraform defaults keep all compute disabled:

- `enable_demo_vm = false`
- `enable_drone_bridge = false`
- `enable_drone_vm = false`

The cheapest demo path runs Gazebo on the Linux laptop and enables only the
bridge on the existing app VM. The optional cloud simulator is a separate Spot
VM with daily auto-shutdown and simulator autostart disabled by default.
Never run `terraform apply` until the local flythrough passes and the exact
plan and current Azure price are approved.

