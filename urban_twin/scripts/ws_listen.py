"""Listen to /ws/live and print every ReadingEvent (Week 2 smoke test).

Usage (with the bridge running):
  .venv/Scripts/python.exe -m urban_twin.scripts.ws_listen
"""

from __future__ import annotations

import argparse
import asyncio
import json

import websockets


async def listen(url: str) -> None:
    print(f"Connecting to {url} …")
    async with websockets.connect(url) as ws:
        print("Connected. Waiting for live readings (run ingestion in another terminal)…")
        async for raw in ws:
            data = json.loads(raw)
            print(
                f"  {data.get('reading_type')}={data.get('value')} {data.get('unit')} "
                f"station={data.get('station_id')} id={data.get('reading_id')}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8001/ws/live",
        help="WebSocket URL",
    )
    args = parser.parse_args()
    asyncio.run(listen(args.url))


if __name__ == "__main__":
    main()
