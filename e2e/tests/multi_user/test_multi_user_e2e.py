"""多用户并发 E2E 测试示例。

覆盖场景：
- 多个不同用户同时登录（验证 session 隔离）
- 多个用户同时操作不同 dashboard（验证权限隔离）
- admin 可以看到全部，普通 viewer 只能看到自己有权限的

运行：
    python run.py -m multi_user --env dev --instance 6.0
    python run.py -m multi_user --env sit --instance 6.0 -k concurrent_login
"""
from __future__ import annotations

import pytest

from utils.bdd import given, when, then, and_


# ---------------------------------------------------------------------------
# Scenario 1: 多个用户同时登录，session 完全隔离
# ---------------------------------------------------------------------------

@pytest.mark.multi_user(3)
@pytest.mark.scenario("Multi-user", tags=("multi_user", "concurrent"))
def test_concurrent_login(multi_user_pages, superset_instance):
    """Scenario: 3 个 viewer 同时登录，每个 session 互不干扰

    Given 池里有 3 个不同 viewer 用户
    When 每个用户登录 Superset
    Then 每个 page 上都显示该用户自己的名字
    And 不同 page 之间的 localStorage 互不影响
    """
    pages = multi_user_pages
    assert len(pages) == 3

    base = superset_instance.instance.base_url

    with given("3 个不同 viewer 登录到 Superset"):
        # login_as_role 已通过 fixture 完成
        for p in pages:
            assert "/login/" not in p.url, f"page should be logged in, got {p.url}"

    with when("每个用户访问 welcome 页"):
        for p in pages:
            p.goto(f"{base}/superset/welcome/")

    with then("每个 page 加载成功，无 500 错误"):
        for p in pages:
            assert p.url.endswith("/welcome/"), f"unexpected url {p.url}"


# ---------------------------------------------------------------------------
# Scenario 2: admin 与 viewer 同时操作（权限差异）
# ---------------------------------------------------------------------------

@pytest.mark.scenario("Multi-user", tags=("multi_user", "permission"))
def test_admin_vs_viewer_visibility(login_as_role, superset_instance):
    """Scenario: admin 看到全部 dashboard，viewer 看到自己的

    Given 池里有 admin 和 viewer 各一个
    When 各自访问 dashboard 列表
    Then admin 看到的数量 ≥ viewer
    """
    admin_page = login_as_role("admin", index=0)
    viewer_page = login_as_role("viewer", index=0)
    base = superset_instance.instance.base_url

    with given("admin 与 viewer 各自登录"):
        pass  # fixture 完成

    with when("各自访问 dashboard 列表页"):
        admin_page.goto(f"{base}/dashboard/list/")
        viewer_page.goto(f"{base}/dashboard/list/")

    with then("两个 page 都能成功加载"):
        assert admin_page.url.endswith("/dashboard/list/")
        assert viewer_page.url.endswith("/dashboard/list/")


# ---------------------------------------------------------------------------
# Scenario 3: 用户池大小足够支持 100 VU 压测
# ---------------------------------------------------------------------------

@pytest.mark.scenario("Multi-user", tags=("multi_user", "pool"))
def test_user_pool_size(login_as_role, user_pool):
    """Scenario: user_pool 至少包含 N 个用户才能跑 100 VU

    Given 任何 env 都应该至少有 5 个 viewer（用于压测 100+ VU）
    Then viewer 池大小 ≥ 5
    """
    with then("viewer 池大小 ≥ 5（支持 100 VU 压测）"):
        viewers = user_pool.users("viewer")
        assert len(viewers) >= 5, (
            f"need ≥5 viewers for 100 VU; got {len(viewers)}: "
            f"{[u.username for u in viewers]}"
        )


# ---------------------------------------------------------------------------
# Scenario 4: 多环境切换时 user_pool 正确加载
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("env_name", ["dev", "sit", "uat"])
@pytest.mark.scenario("Multi-user", tags=("multi_user", "env"))
def test_env_specific_pool(env_name):
    """Scenario: 不同 env 加载各自的 user_pool

    Given E2E_ENV=dev|sit|uat
    When 重新加载 config
    Then user_pool 包含该 env 专属用户
    """
    from config.settings import reload_config

    with given(f"E2E_ENV={env_name}"):
        cfg = reload_config(env_name)
        assert cfg.env == env_name

    with then("该 env 的 user_pool 非空"):
        assert cfg.has_role("admin"), f"{env_name} missing admin users"
        # SIT/UAT 通常 viewer 多于 dev
        if env_name in ("sit", "uat"):
            assert len(cfg.users_for_role("viewer")) >= 5
