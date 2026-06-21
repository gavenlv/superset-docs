"""把当前 Locust 快照保存为基线。

自动聚合角色变体：'GET /api/v1/dashboard/  (viewer)' + '...' (embed) + '...' (analyst)
合并为 'GET /api/v1/dashboard/'（按方法+路径聚合 p50/p95/p99/count）。

用法：
    python perf/tools/save_baseline.py --version 6.0 \\
        --current perf/reports/locust/current_6.0.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.thresholds import save_baseline  # noqa: E402

# 端点名尾部的角色/内容变体，例如 ' (viewer)' / ' (analyst)' / ' (html)' / ' (embed html)'
_ROLE_SUFFIX_RE = re.compile(
    r"\s*\((?:admin_ops|admin|analyst|viewer|embed|html|embed\s+html)\)\s*$"
)


def _strip_role(name: str) -> str:
    """把 'GET /api/v1/dashboard/  (viewer)' → 'GET /api/v1/dashboard/'。
    同样剥离 ' (html)' / ' (embed html)' 等内容类型后缀。"""
    return _ROLE_SUFFIX_RE.sub("", name).strip()


def _aggregate_endpoints(eps: dict) -> dict:
    """按 (method, path) 聚合多个角色变体的指标。"""
    bucket: dict[str, dict] = {}
    for raw_name, vals in eps.items():
        name = _strip_role(raw_name)
        if " " not in name:
            continue
        method, path = name.split(" ", 1)
        # key 用 method + path 稳定
        key = f"{method}|{path}"
        if key not in bucket:
            bucket[key] = {
                "count": 0,
                "failures": 0,
                "_p50_sum": 0.0,
                "_p95_sum": 0.0,
                "_p99_sum": 0.0,
                "_p50_weighted": 0.0,
                "_p95_weighted": 0.0,
                "_p99_weighted": 0.0,
            }
        b = bucket[key]
        c = vals.get("count", 0) or 0
        b["count"] += c
        b["failures"] += vals.get("failures", 0) or 0
        # 加权平均 p50/p95/p99（按 count）
        b["_p50_weighted"] += (vals.get("p50_ms", 0) or 0) * c
        b["_p95_weighted"] += (vals.get("p95_ms", 0) or 0) * c
        b["_p99_weighted"] += (vals.get("p99_ms", 0) or 0) * c

    out: dict = {}
    for key, b in bucket.items():
        method, path = key.split("|", 1)
        display = f"{method} {path}"
        total = b["count"]
        if total > 0:
            p50_avg = b["_p50_weighted"] / total
            p95_avg = b["_p95_weighted"] / total
            p99_avg = b["_p99_weighted"] / total
            err_rate = (b["failures"] / total) * 100
        else:
            p50_avg = p95_avg = p99_avg = 0.0
            err_rate = 0.0
        out[display] = {
            "count": total,
            "failures": b["failures"],
            "error_rate_pct": round(err_rate, 2),
            "p50_ms": round(p50_avg, 1),
            "p95_ms": round(p95_avg, 1),
            "p99_ms": round(p99_avg, 1),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, choices=["4.1", "6.0"])
    ap.add_argument("--current", required=True, help="path to current run JSON")
    ap.add_argument(
        "--note",
        default="",
        help="optional note to add to baseline (e.g. 'cold-start 10 VU 2 min')",
    )
    args = ap.parse_args()

    raw = json.loads(Path(args.current).read_text(encoding="utf-8"))
    aggregated = _aggregate_endpoints(raw.get("endpoints", {}))
    snapshot = {
        "version": args.version,
        "note": args.note,
        "endpoints": aggregated,
    }
    out = save_baseline(args.version, snapshot)
    print(f"saved baseline ({len(aggregated)} endpoints) to {out}")
    for name, vals in sorted(aggregated.items()):
        print(
            f"  {name:45s} p50={vals['p50_ms']:>7.1f}ms "
            f"p95={vals['p95_ms']:>7.1f}ms p99={vals['p99_ms']:>7.1f}ms "
            f"err={vals['error_rate_pct']:.1f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

