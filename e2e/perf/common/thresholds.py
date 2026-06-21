"""性能基线加载与对比。

- load_baseline(version): 读 perf/baselines/vX_Y.json
- compare(version, current, critical_endpoints): 按重点/普通分级对比
- is_critical_endpoint(name, critical_list): 判断端点是否在重点白名单
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from perf.common.config_loader import get_perf_config

# 仓库根目录
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _baseline_path(version: str) -> Path:
    """version: '4.1' / '6.0' → perf/baselines/v4_1.json / v6_0.json。"""
    safe = version.replace(".", "_")
    cfg = get_perf_config()
    base_dir = _REPO_ROOT / "e2e" / cfg.get("baseline_dir", "perf/baselines")
    return base_dir / f"v{safe}.json"


def load_baseline(version: str) -> dict[str, Any]:
    """加载指定版本的基线 JSON。"""
    path = _baseline_path(version)
    if not path.exists():
        return {"version": version, "endpoints": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(version: str, snapshot: dict[str, Any]) -> Path:
    """把当前快照保存为基线。返回写入路径。"""
    path = _baseline_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def is_critical_endpoint(name: str, critical_list: list[str] | None = None) -> bool:
    """判断端点是否在重点白名单。name 例：'GET /api/v1/dashboard/'。"""
    if not critical_list:
        cfg = get_perf_config()
        critical_list = cfg.get("critical_endpoints", [])
    # 端点名是 "METHOD path"，白名单是 "METHOD:path"
    if " " not in name:
        return False
    method, path = name.split(" ", 1)
    needle = f"{method}:{path}"
    for item in critical_list:
        # 兼容 /dashboard/{id} 这种模板匹配
        item_path = item.split(":", 1)[1] if ":" in item else item
        if item_path == path:
            return True
        # 把模板 {xxx} 转成正则
        import re
        regex = re.sub(r"\{[^}]+\}", r"[^/]+", item_path) + r"(?:/.*)?$"
        if re.match(regex, path):
            return True
    return False


def compare(
    version: str,
    current: dict[str, Any],
    *,
    critical_only: bool = False,
) -> dict[str, Any]:
    """对比 current 与基线，输出 pass/fail + violations/warnings。

    current 格式（与 metrics.MetricsCollector.snapshot 一致）：
        {"endpoints": {"GET /api/v1/dashboard/": {"p95_ms": N, "error_rate_pct": N, ...}}}

    返回：
        {
            "passed": bool,
            "violations": [...],   # 重点 +20% / 普通 +50%
            "warnings":  [...],   # 重点 +15% / 普通 +20%
            "critical_violations": [...],
        }
    """
    cfg = get_perf_config()
    th = cfg.get("thresholds", {})
    fail_pct_crit = float(th.get("p95_fail_pct_critical", 15))
    fail_pct = float(th.get("p95_fail_pct", 20))
    warn_pct = float(th.get("p95_warn_pct", 15))
    err_fail_crit = float(th.get("error_rate_fail_pct", 0.5))
    err_fail_normal = float(th.get("error_rate_fail_pct_normal", 1.0))

    baseline = load_baseline(version)
    base_eps = baseline.get("endpoints", {})

    violations: list[dict] = []
    warnings: list[dict] = []
    critical_violations: list[dict] = []

    for name, cur in current.get("endpoints", {}).items():
        is_crit = is_critical_endpoint(name, cfg.get("critical_endpoints"))
        if critical_only and not is_crit:
            continue

        base = base_eps.get(name)
        if not base:
            continue

        base_p95 = base.get("p95_ms")
        cur_p95 = cur.get("p95_ms", 0)
        if not base_p95:
            continue

        delta_pct = ((cur_p95 - base_p95) / base_p95) * 100
        cur_err = cur.get("error_rate_pct", 0)
        base_err = base.get("error_rate_pct", 0)

        item = {
            "endpoint": name,
            "critical": is_crit,
            "base_p95_ms": round(base_p95, 1),
            "cur_p95_ms": round(cur_p95, 1),
            "delta_pct": round(delta_pct, 1),
        }

        if is_crit:
            if delta_pct > fail_pct_crit or cur_err > err_fail_crit:
                critical_violations.append(item)
                violations.append(item)
            elif delta_pct > warn_pct:
                warnings.append(item)
        else:
            if delta_pct > fail_pct or cur_err > err_fail_normal:
                violations.append(item)
            elif delta_pct > warn_pct:
                warnings.append(item)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "critical_violations": critical_violations,
        "summary": {
            "total_endpoints": len(current.get("endpoints", {})),
            "violations": len(violations),
            "warnings": len(warnings),
            "critical_violations": len(critical_violations),
        },
    }
