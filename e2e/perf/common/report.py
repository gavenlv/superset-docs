"""性能报告汇总工具。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_snapshot(snapshot: dict[str, Any], path: Path) -> None:
    """把 metrics snapshot 写为 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def render_summary(snapshot: dict[str, Any]) -> str:
    """把 snapshot 渲染为可读的 summary 字符串。"""
    lines: list[str] = []
    lines.append(f"Duration: {snapshot.get('captured_at', 0):.1f}s")
    lines.append("=" * 78)
    header = (
        f"{'Endpoint':<45} {'count':>6} {'err%':>6} "
        f"{'p50':>7} {'p95':>7} {'p99':>7} {'apdex':>6} {'stab':>5}"
    )
    lines.append(header)
    lines.append("-" * 78)
    for name, s in sorted(snapshot.get("endpoints", {}).items()):
        lines.append(
            f"{name[:44]:<45} {s['count']:>6} {s['error_rate_pct']:>5}% "
            f"{s['p50_ms']:>6}ms {s['p95_ms']:>6}ms {s['p99_ms']:>6}ms "
            f"{s['apdex']:>5} {s['stability']:>4}"
        )
    return "\n".join(lines)
