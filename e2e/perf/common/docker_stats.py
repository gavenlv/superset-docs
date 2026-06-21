"""压测期间后台采集 Superset 相关容器的 CPU/内存。

启动一个 daemon 线程，周期性 docker stats --no-stream，写入 CSV。
压测结束调用 .stop() 停止。
"""
from __future__ import annotations

import csv
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterable


class DockerStatsCollector:
    """后台抓容器 CPU / 内存到 CSV。"""

    def __init__(
        self,
        containers: Iterable[str],
        out_csv: Path,
        interval_sec: float = 2.0,
    ) -> None:
        self._containers = list(containers)
        self._out_csv = out_csv
        self._interval = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fh = None
        self._writer = None

    def start(self) -> None:
        self._out_csv.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._out_csv.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._fh)
        self._writer.writerow(["ts_iso", "container", "cpu_pct", "mem_usage"])
        self._fh.flush()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            ts = time.strftime("%Y-%m-%dT%H:%M:%S")
            for c in self._containers:
                try:
                    out = subprocess.run(
                        [
                            "docker",
                            "stats",
                            c,
                            "--no-stream",
                            "--format",
                            "{{.CPUPerc}};{{.MemUsage}}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    ).stdout.strip()
                    if ";" in out:
                        cpu, mem = out.split(";", 1)
                        # cpu: "12.34%" → 12.34
                        cpu_val = float(cpu.rstrip("%").strip() or 0)
                        # mem: "100MiB / 8GiB" → 100MiB
                        mem_val = mem.split("/")[0].strip()
                        self._writer.writerow([ts, c, cpu_val, mem_val])
                    else:
                        self._writer.writerow([ts, c, -1, "n/a"])
                except Exception:  # noqa: BLE001
                    self._writer.writerow([ts, c, -1, "error"])
            try:
                self._fh.flush()
            except Exception:  # noqa: BLE001
                return
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._fh:
            try:
                self._fh.close()
            except Exception:  # noqa: BLE001
                pass


def start_collector(
    containers: Iterable[str],
    out_csv: Path,
    interval_sec: float = 2.0,
) -> DockerStatsCollector:
    """便捷函数：创建并启动 collector。"""
    c = DockerStatsCollector(containers, out_csv, interval_sec)
    c.start()
    return c
