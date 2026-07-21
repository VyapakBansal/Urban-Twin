"""CLI entry point for the PX4/MAVSDK drone bridge."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from urban_twin.config import settings
from urban_twin.drone.bridge import DroneBridge


async def _run() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            # Windows Proactor loops do not implement POSIX signal handlers.
            pass
    await DroneBridge().run(stop)


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="PX4/MAVSDK telemetry and bounded-control bridge"
    )
    parser.add_argument(
        "--system-address",
        help="MAVSDK address (defaults to DRONE_SYSTEM_ADDRESS)",
    )
    args = parser.parse_args()
    if args.system_address:
        settings.drone_system_address = args.system_address

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()

