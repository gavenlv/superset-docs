"""对比当前压测结果与基线，输出 pass/fail。

用法：
    python perf/tools/compare_baseline.py \\
        --version 6.0 \\
        --current perf/reports/locust/current_6.0.json \\
        --strict  # 重点查询 fail 即整体 fail
        --exit-on-fail
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 让 e2e 根目录可被 import
_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.thresholds import compare  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, choices=["4.1", "6.0"])
    ap.add_argument(
        "--current", required=True, help="path to current run JSON (Locust snapshot)"
    )
    ap.add_argument(
        "--strict", action="store_true", help="critical violations cause non-zero exit"
    )
    ap.add_argument("--exit-on-fail", action="store_true")
    args = ap.parse_args()

    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    result = compare(args.version, current, critical_only=args.strict)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.exit_on_fail and not result["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
