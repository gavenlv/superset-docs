"""从 e2e/config/config.yaml 加载 perf 段，附带默认值。

独立于 utils.config.settings 中的 TestConfig（后者是 dataclass，不含 perf 段）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# 仓库根目录（perf/ 向上两级）
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _REPO_ROOT / "e2e" / "config" / "config.yaml"

# 默认配置（与 PLAN.md 6.1 一致；config.yaml 缺失时兜底）
_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "framework": "locust",
    "duration_sec": 600,
    "spawn_rate": 20,
    "users": 200,
    "role_weights": {
        "admin_ops": 1,
        "analyst": 10,
        "viewer": 30,
        "embed": 8,
    },
    "dataset_multiplier": 5,
    "baseline_dir": "perf/baselines",
    "thresholds": {
        "p95_warn_pct": 15,
        "p95_fail_pct": 20,
        "p95_fail_pct_critical": 15,
        "p95_warn_pct_normal": 20,
        "p95_fail_pct_normal": 50,
        "error_rate_fail_pct": 0.5,
        "error_rate_fail_pct_normal": 1.0,
    },
    "docker_metrics": True,
    "reports_dir": "perf/reports",
    "k6_binary": "k6",
    "critical_endpoints": [
        "GET:/api/v1/dashboard/",
        "GET:/api/v1/dashboard/{id}",
        "GET:/api/v1/dashboard/{id}/charts/",
        "GET:/superset/dashboard/{id}/",
        "GET:/api/v1/chart/",
        "GET:/api/v1/chart/{id}",
        "POST:/api/v1/chart/data",
    ],
}


def _deep_merge(base: dict, override: dict) -> dict:
    """简单的 deep merge：override 覆盖 base。"""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_perf_config() -> dict[str, Any]:
    """返回 perf 段配置（merged with defaults）。"""
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        yaml_cfg = yaml.safe_load(f) or {}
    perf = yaml_cfg.get("perf") or {}
    return _deep_merge(_DEFAULTS, perf)


def get_target_instance(version: str = "6.0") -> dict[str, Any]:
    """返回指定版本（"4.1" / "6.0"）的实例 base_url。"""
    if not _CONFIG_PATH.exists():
        defaults = {
            "4.1": {"name": "4.1", "base_url": "http://localhost:18088"},
            "6.0": {"name": "6.0", "base_url": "http://localhost:18089"},
        }
        return defaults[version]
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        yaml_cfg = yaml.safe_load(f) or {}
    for inst in yaml_cfg.get("instances", []):
        if str(inst.get("name")) == version:
            return {"name": str(inst["name"]), "base_url": str(inst["base_url"])}
    raise KeyError(f"instance {version!r} not found in config.yaml")
