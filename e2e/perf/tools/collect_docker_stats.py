"""压测期间后台采集容器 CPU/内存。

用法：
    python perf/tools/collect_docker_stats.py \\
        --containers superset-6.0-web,superset-6.0-postgres,superset-6.0-redis \\
        --out perf/reports/locust/docker_stats.csv \\
        --interval 2
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.docker_stats import start_collector  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--containers", required=True, help="comma-separated container names")
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--duration", type=int, default=0, help="0=run until SIGINT")
    args = ap.parse_args()

    containers = [c.strip() for c in args.containers.split(",") if c.strip()]
    collector = start_collector(containers, Path(args.out), args.interval)
    print(f"collecting stats for {containers} → {args.out} (interval={args.interval}s)")
    print("Ctrl+C to stop")

    stop_flag = {"stop": False}

    def _on_sigint(*_a):  # noqa: ANN001
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _on_sigint)
    try:
        if args.duration > 0:
            time.sleep(args.duration)
            stop_flag["stop"] = True
        else:
            while not stop_flag["stop"]:
                time.sleep(1)
    finally:
        collector.stop()
        print("docker stats collector stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
