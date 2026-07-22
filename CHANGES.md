# Urban Twin — Change PRD: Visual Fidelity + Drone Simulation

**Author:** Vyapak
**Status:** Draft v1
**Base:** Urban Twin v1 (existing, unchanged) — PostGIS, Kafka, ingestion, forecast worker, WebSocket bridge, FastAPI, Terraform/Azure deployment, CesiumJS frontend
**Scope of this document:** additions only. The existing backend, data pipeline, forecasting, and infra are not modified by this change — this document assumes they continue to work exactly as already built and tested.
**Timeline:** +4 weeks on top of the current build

---

## 1. Summary

Two additions to the existing, working Urban Twin platform:

1. **Visual fidelity** — swap the current OSM-extruded building layer for Google Photorealistic 3D Tiles as the primary basemap, plus lighting, terrain, and post-processing, so the scene looks like Google Earth instead of a GIS wireframe.
2. **User-controllable drone simulation** — PX4 SITL running in Gazebo, with a telemetry bridge that streams live position/attitude through the existing Kafka/WebSocket pipeline, rendered as a live 3D entity in Cesium with real-time keyboard/gamepad control from the browser.

Neither addition touches the existing sensor ingestion, forecasting, or database schema for weather/river/air-quality data. They plug into the existing Kafka broker and WebSocket bridge pattern as new topics and a new consumer, and into the existing CesiumJS scene as new layers.

---

## 2. Goals (of this change)

- Make the existing scene visually convincing (real building mesh, correct lighting/shadows/terrain) rather than a GIS wireframe
- Add a second, independent real-time data stream (drone telemetry) proving the existing Kafka/WebSocket architecture generalizes beyond the original sensor use case
- Add a genuine coordinate-frame transform under real-time constraints (local NED → global WGS84), which is a stronger geomatics demonstration than the static building import it partially replaces
- Ship a full round-trip control loop (browser → simulation → browser), not just one-directional playback

### Non-goals
- Any change to existing sensor ingestion, forecasting, or their database tables
- Multi-drone or swarm simulation — one vehicle only
- Deleting the existing OSM building pipeline — it becomes a fallback/secondary layer, not removed
- Global-latency-tolerant control — the control loop is judged against same-machine/same-region latency (see Section 6)
- Any change to the existing Terraform provider (Azure) or deployment pattern — new compute is added using the same approach already in place

---

## 3. What's not changing (context, not part of this change)

Listed explicitly so it's clear what this document does *not* cover: weather/river/air-quality ingestion, the multi-source ingestion orchestrator, PostGIS schema for `sensor_readings`/`forecasts`, the LightGBM forecasting pipeline and its validation, the existing FastAPI REST endpoints for readings/forecasts, the existing Kafka broker and its `sensor.readings`/`forecasts.generated` topics, the existing WebSocket bridge for sensor data, Alembic migrations for existing tables, and the existing Azure/Terraform deployment for those services. All of this stays as-is.

---

## 4. New architecture (additions to the existing system)

```
                    [existing pipeline — unchanged]
   Weather/River/AQ APIs → Ingestion → PostGIS + Kafka → Forecast Worker
                                              │
                                              ▼
                                   WebSocket Bridge (existing)
                                              │
                                              ▼
   ══════════════════════════════════════════╪══════════════════════════
                    [new, this change]        │
                                              ▼
┌──────────────────────┐         ┌──────────────────────────┐
│  Gazebo + PX4 SITL      │  MAVLink │  Telemetry Bridge            │
│  (simulated drone,       │◄────────►│  - MAVLink ↔ Kafka             │
│   real flight dynamics)  │         │  - NED → WGS84 transform       │
└──────────────────────┘         │    (see Section 5)             │
                                    │  - publishes drone.telemetry    │
                                    │  - consumes drone.control       │
                                    └───────────┬──────────────────┘
                                                │
                                                ▼
                              ┌──────────────────────────┐
                              │  Kafka (existing broker,     │
                              │  new topics added):           │
                              │  - drone.telemetry (20-50Hz)  │
                              │  - drone.control                │
                              └───────────┬──────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────────┐
                              │  WebSocket Bridge (extended)  │
                              │  - existing /ws/live unchanged │
                              │  - new /ws/drone endpoint       │
                              └───────────┬──────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────┐
│  Frontend (CesiumJS, extended)                                  │
│  - NEW: Google Photorealistic 3D Tiles (primary basemap)          │
│  - EXISTING: OSM buildings (demoted to fallback/toggle layer)     │
│  - EXISTING: live sensor overlay, forecast overlay (unchanged)     │
│  - NEW: terrain, lighting/shadows, atmosphere, post-processing     │
│  - NEW: live drone entity, drone POV camera, control input handling│
└────────────────────────────────────────────────────────────┘
```

**Integration points with the existing system (this is the part worth being precise about):**
- The telemetry bridge is a new consumer/producer pair on the *existing* Kafka broker — no new broker, no new infra pattern, just new topics
- The WebSocket bridge gets a new endpoint (`/ws/drone`) alongside the existing `/ws/live` — same service, same deployment unit, extended rather than duplicated
- The frontend's existing layer-toggle pattern (used for sensor/forecast layers) is reused for the new basemap and drone layers, rather than inventing a new UI pattern

---

## 5. Coordinate frame transform (NED → WGS84)

This is the highest-value technical addition in this change, and the part most worth documenting carefully:

- PX4/Gazebo report vehicle position in a local NED (North-East-Down) frame relative to a fixed home/origin point
- The telemetry bridge converts each position update to geodetic WGS84 (lat, lon, height) using the origin's known coordinates as the reference for a local tangent-plane transform
- This runs continuously at stream rate (20-50Hz), not once — a live transform under real-time constraints, not a one-time georeferencing step
- Cesium consumes WGS84 directly; get the origin point wrong and the drone renders in the wrong place relative to the existing buildings and sensor data
- **Test this against known reference points** (Section 8) — a transform bug here is a silent, hard-to-notice failure mode, not a crash

---

## 6. What to be honest about (README material)

- This is a *simulated* vehicle with real PX4 flight-model dynamics, not a scripted animation or path — say this plainly
- Control latency is bounded by same-machine/same-region conditions; this is not claimed to work at internet scale
- Flight envelope constraints (max altitude, geofence around the AOI) are enforced in the telemetry bridge, not just assumed — the drone shouldn't be flyable somewhere nonsensical relative to the buildings/terrain data
- Google's Photorealistic 3D Tiles require attribution (Google logo + data-attribution text in the Cesium credit display) — a Terms of Service requirement, not optional UI chrome

**Implementation docs (local):** [docs/DRONE.md](docs/DRONE.md) (setup on any machine), [docs/DRONE_TROUBLESHOOTING.md](docs/DRONE_TROUBLESHOOTING.md) (error catalog).

---

## 7. Visual fidelity changes (frontend only, no backend impact)

- **Primary basemap:** Google Photorealistic 3D Tiles via Cesium ion (`Cesium3DTileset`) — confirm Kensington/Calgary coverage before building anything else on top of this, it's a hard dependency
- **OSM buildings:** demoted from primary layer to a toggle-able fallback — code stays, default visibility changes
- **Terrain:** Cesium World Terrain via ion, replacing the flat ellipsoid
- **Lighting:** `scene.globe.enableLighting = true` + shadow maps
- **Atmosphere:** verify `scene.skyAtmosphere` isn't at a flat default
- **Post-processing:** ambient occlusion + bloom via Cesium post-process stages

None of this requires backend changes — it's entirely within the existing frontend's Cesium scene setup.

---

## 8. Testing (additions only)

- Unit test for the NED→WGS84 transform against known reference coordinate pairs — this is the single most important new test, given the silent-failure risk noted in Section 5
- Test that the telemetry bridge correctly relays a MAVLink position message to a Kafka message matching the expected schema
- Test that flight envelope constraints actually reject out-of-bounds control input rather than silently clamping or ignoring it
- Existing test suite for ingestion/forecasting/API is untouched and should continue passing unmodified — a regression there would indicate this change leaked into code it shouldn't have

---

## 9. Deployment (additions only)

- New compute for Gazebo + PX4 SITL, provisioned via the existing Terraform/Azure pattern already in the repo — same provider, same approach, just a new resource
- Size this instance deliberately and separately from the existing services — headless simulation is CPU-intensive and will starve the existing sensor pipeline if co-located on undersized shared compute
- Telemetry bridge deploys alongside the existing WebSocket bridge/API services, same pattern as those
- No change to the existing database, existing Kafka broker instance, or existing budget-alarm setup beyond confirming the new compute is covered by it

---

## 10. Timeline (4 weeks)

**Week 1 — Visual fidelity**
- Confirm Google Photorealistic 3D Tiles coverage for the AOI via Cesium ion (do this first — gates the rest of the week)
- Swap basemap, wire OSM buildings in as toggle-able fallback
- Terrain, lighting/shadows, atmosphere, post-processing
- Should end with a visibly better-looking scene, independent of any drone work

**Week 2 — PX4 + Gazebo fundamentals (local only)**
- Get PX4 SITL running in Gazebo locally, fly it with existing PX4 tooling (e.g. QGroundControl) before writing any integration code
- Confirm the simulator itself works in isolation before bridging it to anything else

**Week 3 — Telemetry bridge + coordinate transform**
- Build the MAVLink → Kafka telemetry bridge, add the new topics to the existing broker
- Implement and test the NED→WGS84 transform against known reference points
- Render live telemetry as a moving Cesium entity — one-directional first, no control loop yet
- This is the milestone worth demoing even if Week 4 doesn't fully land

**Week 4 — Control loop + deployment + writeup**
- Build the browser → Kafka → PX4 control path, keyboard/gamepad input, drone POV camera
- Flight envelope constraints enforced in the telemetry bridge
- Provision Gazebo/PX4 compute via Terraform, deploy telemetry bridge alongside existing services
- Record a flythrough demo clip — given how much of the payoff is visual, this is the primary artifact most reviewers will actually see
- Update README: what's new, the coordinate transform writeup, honest scope notes from Section 6

**If Week 4 runs long:** ship telemetry-only playback (Week 3's output) and document the control loop as a near-complete stretch item rather than rushing it or dropping it silently.

---

## 11. Success criteria

- The existing sensor/forecast pipeline continues to work exactly as before — this change adds to it, nothing regresses
- The scene visibly reads as photorealistic (real building mesh, shadows, terrain) rather than a GIS wireframe
- A stranger can fly the drone with keyboard/gamepad and see real-time response over the real-looking city
- The NED→WGS84 transform is documented clearly enough that a reviewer understands it as a real geomatics problem
- A recorded flythrough clip exists independent of whether the live deployment happens to be up
