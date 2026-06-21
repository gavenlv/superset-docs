"""验证 config_loader 默认值与 config.yaml 合并结果合理。"""
from __future__ import annotations

from pathlib import Path
import sys

# 让 e2e 根目录可被 import
_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.config_loader import get_perf_config, get_target_instance  # noqa: E402
from config.settings import CONFIG  # noqa: E402
from utils.user_pool import user_pool  # noqa: E402


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


# ---------------------------------------------------------------------------
# 多环境 / 多用户
# ---------------------------------------------------------------------------


def test_user_pool_has_four_roles():
    """dev 默认 user_pool 应至少有 admin/analyst/viewer/embed 4 角色。"""
    for role in ("admin", "analyst", "viewer", "embed"):
        assert CONFIG.has_role(role), f"missing role {role} in user_pool"


def test_user_pool_viewer_size_supports_load():
    """viewer 池大小应足以支撑 perf 默认 200 VU 压测。

    设计：viewer 至少 5 个，200 VU 配 5 个用户 = 每用户 40 VU（合理）。
    """
    viewers = CONFIG.users_for_role("viewer")
    assert len(viewers) >= 5, (
        f"need ≥5 viewers for 200 VU; got {len(viewers)}: "
        f"{[u.username for u in viewers]}"
    )


def test_user_pool_pick_by_role():
    """user_pool.pick(role) 返回对应角色的用户。"""
    for role in ("admin", "analyst", "viewer", "embed"):
        u = user_pool.pick(role)
        assert u.role == role
        assert u.username
        assert u.password


def test_user_pool_pick_by_index_is_deterministic():
    """user_pool.pick(role, index=i) 始终返回同一用户。"""
    v0_a = user_pool.pick("viewer", index=0)
    v0_b = user_pool.pick("viewer", index=0)
    assert v0_a.username == v0_b.username
    # 不同 index 应给不同用户
    if len(user_pool.users("viewer")) >= 2:
        v1 = user_pool.pick("viewer", index=1)
        assert v0_a.username != v1.username


def test_supported_envs():
    """当前实现的 4 个 env 都应被识别。"""
    from config.settings import SUPPORTED_ENVS
    assert set(SUPPORTED_ENVS) == {"dev", "sit", "uat", "prod"}
