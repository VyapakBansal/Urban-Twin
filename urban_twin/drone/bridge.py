"""Persistent MAVSDK ↔ Kafka bridge for telemetry and bounded controls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from urban_twin.config import Settings, settings
from urban_twin.drone.envelope import ControlGuard, ControlRejected, VehicleState
from urban_twin.drone.transform import ned_to_wgs84
from urban_twin.messaging.schemas import DroneControlEvent, DroneTelemetryEvent

logger = logging.getLogger(__name__)


def _serialize(value: dict[str, Any]) -> bytes:
    return json.dumps(value, default=str, separators=(",", ":")).encode("utf-8")


@dataclass
class TelemetrySnapshot:
    north_m: float = 0.0
    east_m: float = 0.0
    down_m: float = 0.0
    velocity_north_m_s: float = 0.0
    velocity_east_m_s: float = 0.0
    velocity_down_m_s: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    armed: bool = False
    flight_mode: str = "UNKNOWN"
    has_position: bool = False
    has_attitude: bool = False

    @property
    def ready(self) -> bool:
        return self.has_position and self.has_attitude

    def vehicle_state(self) -> VehicleState | None:
        if not self.ready:
            return None
        return VehicleState(
            north_m=self.north_m,
            east_m=self.east_m,
            down_m=self.down_m,
            yaw_deg=self.yaw_deg,
        )


def build_telemetry_event(
    snapshot: TelemetrySnapshot,
    config: Settings,
    *,
    sequence: int,
    recorded_at: datetime | None = None,
) -> DroneTelemetryEvent:
    if not snapshot.ready:
        raise ValueError("position and attitude telemetry are required")
    position = ned_to_wgs84(
        snapshot.north_m,
        snapshot.east_m,
        snapshot.down_m,
        home_lat=config.drone_home_lat,
        home_lon=config.drone_home_lon,
        home_altitude_m=config.drone_home_alt_m,
    )
    return DroneTelemetryEvent(
        drone_id=config.drone_id,
        sequence=sequence,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        lat=position.lat,
        lon=position.lon,
        altitude_m=position.altitude_m,
        relative_altitude_m=-snapshot.down_m,
        north_m=snapshot.north_m,
        east_m=snapshot.east_m,
        down_m=snapshot.down_m,
        velocity_north_m_s=snapshot.velocity_north_m_s,
        velocity_east_m_s=snapshot.velocity_east_m_s,
        velocity_down_m_s=snapshot.velocity_down_m_s,
        roll_deg=snapshot.roll_deg,
        pitch_deg=snapshot.pitch_deg,
        yaw_deg=snapshot.yaw_deg % 360.0,
        armed=snapshot.armed,
        flight_mode=snapshot.flight_mode,
    )


class DroneBridge:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self.snapshot = TelemetrySnapshot()
        self.guard = ControlGuard(config)
        self.drone: Any = None
        self.producer: AIOKafkaProducer | None = None
        self.control_consumer: AIOKafkaConsumer | None = None
        self.sequence = 0
        self.offboard_started = False
        self._command = (0.0, 0.0, 0.0, 0.0)
        self._last_command_at = 0.0
        self._offboard_lock = asyncio.Lock()

    async def run(self, stop: asyncio.Event) -> None:
        from mavsdk import System

        self.drone = System()
        await self.drone.connect(system_address=self.config.drone_system_address)
        logger.info("waiting for PX4 at %s", self.config.drone_system_address)
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                logger.info("PX4 connected")
                break

        await self._configure_sitl()

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            value_serializer=_serialize,
        )
        self.control_consumer = AIOKafkaConsumer(
            self.config.kafka_topic_drone_control,
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            group_id=f"drone-bridge-{self.config.drone_id}",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )
        await self.producer.start()
        await self.control_consumer.start()
        tasks = [
            asyncio.create_task(self._collect_position()),
            asyncio.create_task(self._collect_attitude()),
            asyncio.create_task(self._collect_armed()),
            asyncio.create_task(self._collect_flight_mode()),
            asyncio.create_task(self._publish_telemetry(stop)),
            asyncio.create_task(self._consume_controls(stop)),
            asyncio.create_task(self._offboard_loop(stop)),
        ]
        try:
            await stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._stop_offboard()
            await self.control_consumer.stop()
            await self.producer.stop()
            logger.info("drone bridge stopped")

    async def _configure_sitl(self) -> None:
        """Relax headless SITL arming checks (no QGC on UDP 14550)."""
        sitl_params: tuple[tuple[str, int], ...] = (
            ("CBRK_SUPPLY_CHK", 894281),  # skip power-rail check in sim
            ("NAV_DLL_ACT", 0),  # no GCS/data-link arming block
            ("NAV_RCL_ACT", 0),  # no RC-link arming block
            ("COM_RCL_EXCEPT", 4),  # allow offboard without physical RC
        )
        for name, value in sitl_params:
            try:
                await self.drone.param.set_param_int(name, value)
                logger.info("PX4 param %s=%s", name, value)
            except Exception:
                logger.warning("failed to set PX4 param %s", name, exc_info=True)

    async def _collect_position(self) -> None:
        async for value in self.drone.telemetry.position_velocity_ned():
            self.snapshot.north_m = value.position.north_m
            self.snapshot.east_m = value.position.east_m
            self.snapshot.down_m = value.position.down_m
            self.snapshot.velocity_north_m_s = value.velocity.north_m_s
            self.snapshot.velocity_east_m_s = value.velocity.east_m_s
            self.snapshot.velocity_down_m_s = value.velocity.down_m_s
            self.snapshot.has_position = True

    async def _collect_attitude(self) -> None:
        async for value in self.drone.telemetry.attitude_euler():
            self.snapshot.roll_deg = value.roll_deg
            self.snapshot.pitch_deg = value.pitch_deg
            self.snapshot.yaw_deg = value.yaw_deg
            self.snapshot.has_attitude = True

    async def _collect_armed(self) -> None:
        async for armed in self.drone.telemetry.armed():
            self.snapshot.armed = armed

    async def _collect_flight_mode(self) -> None:
        async for mode in self.drone.telemetry.flight_mode():
            self.snapshot.flight_mode = getattr(mode, "name", str(mode))

    async def _publish_telemetry(self, stop: asyncio.Event) -> None:
        period = 1.0 / self.config.drone_telemetry_hz
        while not stop.is_set():
            if self.snapshot.ready and self.producer is not None:
                event = build_telemetry_event(
                    self.snapshot,
                    self.config,
                    sequence=self.sequence,
                )
                self.sequence += 1
                await self.producer.send_and_wait(
                    self.config.kafka_topic_drone_telemetry,
                    value=event.model_dump(mode="json"),
                    key=self.config.drone_id.encode("utf-8"),
                )
            await asyncio.sleep(period)

    async def _consume_controls(self, stop: asyncio.Event) -> None:
        assert self.control_consumer is not None
        while not stop.is_set():
            batch = await self.control_consumer.getmany(timeout_ms=100, max_records=20)
            for messages in batch.values():
                for message in messages:
                    try:
                        event = DroneControlEvent.model_validate(message.value)
                        self.guard.validate(event, self.snapshot.vehicle_state())
                        await self._apply_control(event)
                    except (ValueError, ControlRejected) as exc:
                        logger.warning("rejected drone command: %s", exc)
                    except Exception:
                        logger.exception("drone command failed")

    async def _apply_control(self, event: DroneControlEvent) -> None:
        if event.command == "arm":
            try:
                await self.drone.action.arm()
            except Exception as exc:
                logger.warning("PX4 arm failed: %s", exc)
            return
        if event.command == "takeoff":
            try:
                await self.drone.action.takeoff()
            except Exception as exc:
                logger.warning("PX4 takeoff failed: %s", exc)
            return
        if event.command == "land":
            await self._stop_offboard()
            await self.drone.action.land()
            return
        if event.command == "disarm":
            await self._stop_offboard()
            await self.drone.action.disarm()
            return

        if event.command == "hold":
            self._command = (0.0, 0.0, 0.0, 0.0)
        else:
            self._command = (
                event.forward_m_s,
                event.right_m_s,
                event.down_m_s,
                event.yaw_rate_deg_s,
            )
        self._last_command_at = time.monotonic()
        await self._ensure_offboard()

    async def _ensure_offboard(self) -> None:
        from mavsdk.offboard import VelocityBodyYawspeed

        async with self._offboard_lock:
            if self.offboard_started:
                return
            await self.drone.offboard.set_velocity_body(
                VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)
            )
            await self.drone.offboard.start()
            self.offboard_started = True
            logger.info("PX4 Offboard mode started")

    async def _offboard_loop(self, stop: asyncio.Event) -> None:
        from mavsdk.offboard import VelocityBodyYawspeed

        period = 1.0 / self.config.drone_control_hz
        while not stop.is_set():
            if self.offboard_started:
                stale = (
                    time.monotonic() - self._last_command_at
                    > self.config.drone_command_timeout_sec
                )
                command = (0.0, 0.0, 0.0, 0.0) if stale else self._command
                async with self._offboard_lock:
                    if self.offboard_started:
                        await self.drone.offboard.set_velocity_body(
                            VelocityBodyYawspeed(*command)
                        )
            await asyncio.sleep(period)

    async def _stop_offboard(self) -> None:
        if self.drone is None:
            return
        async with self._offboard_lock:
            if not self.offboard_started:
                return
            try:
                await self.drone.offboard.stop()
            except Exception:
                logger.warning("PX4 Offboard stop failed", exc_info=True)
            finally:
                self.offboard_started = False
                self._command = (0.0, 0.0, 0.0, 0.0)

