"""验证 config_loader 默认值与 config.yaml 合并结果合理。"""
from __future__ import annotations

from pathlib import Path
import sys

# 让 e2e 根目录可被 import
_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.config_loader import get_perf_config, get_target_instance  # noqa: E402


def test_perf_config_has_keys():
    cfg = get_perf_config()
    for k in ("framework", "duration_sec", "spawn_rate", "users", "thresholds", "role_weights"):
        assert k in cfg, f"missing key: {k}"


def test_role_weights_have_four_roles():
    cfg = get_perf_config()
    rw = cfg["role_weights"]
    for role in ("admin_ops", "analyst", "viewer", "embed"):
        assert role in rw
    # viewer 应是最高权重
    assert rw["viewer"] >= rw["analyst"] >= rw["admin_ops"]


def test_thresholds_have_critical_and_normal():
    cfg = get_perf_config()
    th = cfg["thresholds"]
    # 重点查询 fail_pct 应严于普通
    assert th["p95_fail_pct_critical"] <= th["p95_fail_pct"]
    assert th["p95_fail_pct"] <= th["p95_fail_pct_normal"]


def test_target_instance_lookup():
    inst = get_target_instance("6.0")
    assert "base_url" in inst
    assert inst["base_url"].startswith("http")
