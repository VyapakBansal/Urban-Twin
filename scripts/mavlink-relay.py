#!/usr/bin/env python3
"""Bidirectional UDP relay: WSL PX4 (127.0.0.1:14540) <-> Windows MAVSDK host."""

from __future__ import annotations

import select
import socket
import subprocess
import sys


def windows_host() -> str:
    route = subprocess.check_output(["ip", "route"], text=True)
    return route.split("default via ")[1].split()[0]


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 14540
    win_host = windows_host()

    px4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    px4.bind(("127.0.0.1", port))

    bridge = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bridge.bind(("0.0.0.0", 0))

    px4_peer: tuple[str, int] | None = None
    print(
        f"mavlink relay: 127.0.0.1:{port} <-> {win_host}:{port}",
        flush=True,
    )

    while True:
        readable, _, _ = select.select([px4, bridge], [], [])
        for sock in readable:
            data, addr = sock.recvfrom(65535)
            if sock is px4:
                px4_peer = addr
                bridge.sendto(data, (win_host, port))
            elif px4_peer is not None:
                px4.sendto(data, px4_peer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
