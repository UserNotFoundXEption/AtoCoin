from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from .node import Node


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--advertise-host")
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--heartbeat", type=float, default=10.0)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )

    try:
        node = Node(
            host=args.host,
            port=args.port,
            advertise_host=args.advertise_host,
            seeds=args.seed,
            heartbeat_interval=args.heartbeat,
        )
        node.start()
    except (OSError, ValueError) as e:
        print(f"Can't start node: {e}", file=sys.stderr)
        return 1

    def _terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _terminate)

    print(f"Node started: {node.url}  (node_id: {node.node_id})", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping node")
    finally:
        node.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
