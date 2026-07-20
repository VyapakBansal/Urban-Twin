"""Async Kafka producer helpers."""

from __future__ import annotations

import json
import logging

from aiokafka import AIOKafkaProducer

from urban_twin.config import settings
from urban_twin.messaging.schemas import ReadingEvent

logger = logging.getLogger(__name__)


def _json_serializer(value: dict) -> bytes:
    return json.dumps(value, default=str).encode("utf-8")


async def publish_readings(events: list[ReadingEvent]) -> None:
    """Publish reading events to the sensor.readings topic."""
    if not events:
        return

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=_json_serializer,
    )
    await producer.start()
    try:
        topic = settings.kafka_topic_sensor_readings
        for event in events:
            await producer.send_and_wait(
                topic,
                value=event.model_dump(mode="json"),
                key=event.station_id.encode("utf-8"),
            )
            logger.info(
                "published %s=%s to %s",
                event.reading_type,
                event.value,
                topic,
            )
    finally:
        await producer.stop()
