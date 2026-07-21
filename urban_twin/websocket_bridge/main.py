"""WebSocket bridge: Kafka sensor.readings → browser clients.

Clients connect to /ws/live and receive each ReadingEvent as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from urban_twin.config import settings
from urban_twin.messaging.schemas import DroneControlEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        logger.info("client connected (%s total)", len(self._clients))

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        logger.info("client disconnected (%s total)", len(self._clients))

    @property
    def count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(message, default=str)
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


live_manager = ConnectionManager()
drone_manager = ConnectionManager()


async def kafka_to_websocket_loop(
    stop: asyncio.Event,
    *,
    topic: str,
    group_id: str,
    destination: ConnectionManager,
    timeout_ms: int,
    latest_only: bool = False,
) -> None:
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    await consumer.start()
    logger.info(
        "consuming %s from %s",
        topic,
        settings.kafka_bootstrap_servers,
    )
    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=timeout_ms, max_records=100)
            for _tp, messages in batch.items():
                selected = messages[-1:] if latest_only else messages
                for msg in selected:
                    await destination.broadcast(msg.value)
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped for %s", topic)


def create_app() -> FastAPI:
    stop = asyncio.Event()
    consumer_tasks: list[asyncio.Task[None]] = []
    control_producer: AIOKafkaProducer | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal control_producer
        control_producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda value: json.dumps(
                value, default=str, separators=(",", ":")
            ).encode("utf-8"),
        )
        await control_producer.start()
        consumer_tasks.extend(
            [
                asyncio.create_task(
                    kafka_to_websocket_loop(
                        stop,
                        topic=settings.kafka_topic_sensor_readings,
                        group_id="websocket-bridge",
                        destination=live_manager,
                        timeout_ms=500,
                    )
                ),
                asyncio.create_task(
                    kafka_to_websocket_loop(
                        stop,
                        topic=settings.kafka_topic_drone_telemetry,
                        group_id="drone-websocket-bridge",
                        destination=drone_manager,
                        timeout_ms=50,
                        latest_only=True,
                    )
                ),
            ]
        )
        logger.info("WebSocket bridge started")
        yield
        stop.set()
        await asyncio.gather(*consumer_tasks, return_exceptions=True)
        await control_producer.stop()

    app = FastAPI(title="Urban Twin WebSocket Bridge", lifespan=lifespan)

    @app.get("/health")
    async def health() -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket) -> None:
        await live_manager.connect(websocket)
        try:
            # Keep the socket open; Kafka loop pushes outbound messages.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            live_manager.disconnect(websocket)

    @app.websocket("/ws/drone")
    async def ws_drone(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        if origin and origin not in settings.cors_origin_list:
            await websocket.close(code=1008, reason="origin not allowed")
            return
        await drone_manager.connect(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    event = DroneControlEvent.model_validate_json(raw)
                except ValidationError as exc:
                    await websocket.send_json(
                        {
                            "event_type": "drone.control.error",
                            "detail": exc.errors(include_url=False),
                        }
                    )
                    continue
                assert control_producer is not None
                await control_producer.send_and_wait(
                    settings.kafka_topic_drone_control,
                    value=event.model_dump(mode="json"),
                    key=event.client_id.encode("utf-8"),
                )
                await websocket.send_json(
                    {
                        "event_type": "drone.control.ack",
                        "sequence": event.sequence,
                    }
                )
        except WebSocketDisconnect:
            drone_manager.disconnect(websocket)
            if drone_manager.count == 0 and control_producer is not None:
                hold = DroneControlEvent(
                    client_id="websocket-bridge",
                    sequence=int(datetime.now(timezone.utc).timestamp() * 1000),
                    issued_at=datetime.now(timezone.utc),
                    command="hold",
                )
                await control_producer.send_and_wait(
                    settings.kafka_topic_drone_control,
                    value=hold.model_dump(mode="json"),
                    key=b"websocket-bridge",
                )

    return app


app = create_app()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin WebSocket bridge")
    parser.add_argument("--host", default=settings.ws_bridge_host)
    parser.add_argument("--port", type=int, default=settings.ws_bridge_port)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    import uvicorn

    uvicorn.run(
        "urban_twin.websocket_bridge.main:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
