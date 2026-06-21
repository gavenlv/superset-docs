"""自定义性能指标：Apdex、Stability score、p99 漂移。

- Apdex: 用户满意度指数（0~1）
- Stability: p99/p50 比值
- 增量写入 JSON 报告
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EndpointStats:
    """单个端点的累计指标。"""

    name: str
    count: int = 0
    failures: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    # Apdex 阈值（ms）：响应时间 < T 满意；< 4T 容忍；>= 4T 挫败
    apdex_t_ms: float = 500.0

    def record(self, latency_ms: float, success: bool) -> None:
        self.count += 1
        if not success:
            self.failures += 1
        self.latencies_ms.append(latency_ms)

    def p50(self) -> float:
        return _percentile(self.latencies_ms, 50)

    def p95(self) -> float:
        return _percentile(self.latencies_ms, 95)

    def p99(self) -> float:
        return _percentile(self.latencies_ms, 99)

    def error_rate(self) -> float:
        if self.count == 0:
            return 0.0
        return (self.failures / self.count) * 100

    def apdex(self) -> float:
        """Apdex = (satisfied + tolerating/2) / total。"""
        if not self.latencies_ms:
            return 1.0
        satisfied = sum(1 for x in self.latencies_ms if x <= self.apdex_t_ms)
        tolerating = sum(
            1 for x in self.latencies_ms if self.apdex_t_ms < x <= 4 * self.apdex_t_ms
        )
        return (satisfied + tolerating / 2) / len(self.latencies_ms)

    def stability(self) -> float:
        """p99 / p50，越接近 1 越稳定。"""
        p50 = self.p50()
        if p50 == 0:
            return 1.0
        return self.p99() / p50

    def snapshot(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "failures": self.failures,
            "error_rate_pct": round(self.error_rate(), 2),
            "p50_ms": round(self.p50(), 1),
            "p95_ms": round(self.p95(), 1),
            "p99_ms": round(self.p99(), 1),
            "apdex": round(self.apdex(), 3),
            "stability": round(self.stability(), 2),
        }


def _percentile(values: list[float], pct: float) -> float:
    """简单 percentile（线性插值）。"""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


class MetricsCollector:
    """聚合多个端点的指标，提供快照输出。"""

    def __init__(self) -> None:
        self._stats: dict[str, EndpointStats] = defaultdict(
            lambda: EndpointStats(name="unknown")
        )
        self._start = time.time()

    def record(self, endpoint: str, latency_ms: float, success: bool) -> None:
        if endpoint not in self._stats:
            self._stats[endpoint] = EndpointStats(name=endpoint)
        self._stats[endpoint].record(latency_ms, success)

    def snapshot(self) -> dict[str, Any]:
        return {
            "captured_at": time.time() - self._start,
            "endpoints": {
                name: stats.snapshot() for name, stats in self._stats.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.snapshot(), indent=2, ensure_ascii=False)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
