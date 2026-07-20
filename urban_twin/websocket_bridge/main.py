"""WebSocket bridge: Kafka sensor.readings → browser clients.

Clients connect to /ws/live and receive each ReadingEvent as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from urban_twin.config import settings

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


manager = ConnectionManager()


async def kafka_to_websocket_loop(stop: asyncio.Event) -> None:
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_sensor_readings,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="websocket-bridge",
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    await consumer.start()
    logger.info(
        "consuming %s from %s",
        settings.kafka_topic_sensor_readings,
        settings.kafka_bootstrap_servers,
    )
    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=500, max_records=50)
            for _tp, messages in batch.items():
                for msg in messages:
                    await manager.broadcast(msg.value)
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped")


def create_app() -> FastAPI:
    stop = asyncio.Event()
    consumer_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal consumer_task
        consumer_task = asyncio.create_task(kafka_to_websocket_loop(stop))
        logger.info("WebSocket bridge started")
        yield
        stop.set()
        if consumer_task:
            await consumer_task

    app = FastAPI(title="Urban Twin WebSocket Bridge", lifespan=lifespan)

    @app.get("/health")
    async def health() -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            # Keep the socket open; Kafka loop pushes outbound messages.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin WebSocket bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
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
