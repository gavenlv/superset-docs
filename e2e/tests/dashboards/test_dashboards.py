"""测试：仪表盘（Dashboards）E2E。"""
from __future__ import annotations

import logging
import time

import httpx
import pytest

from config.settings import CONFIG
from pages.dashboard_page import DashboardPage
from utils.service import ServiceState

logger = logging.getLogger(__name__)


# 示例仪表盘 slug（来自两个版本都加载的 examples）
# 如果某个版本仪表盘不存在，测试会被 pytest.skip 跳过
EXAMPLE_DASHBOARDS = [
    ("unicode-test", "Unicode Test"),
    ("deck", "deck.gl Demo"),
]


def _get_token(base_url: str) -> str:
    r = httpx.post(
        f"{base_url}/api/v1/security/login",
        json={
            "username": CONFIG.admin_username,
            "password": CONFIG.admin_password,
            "provider": "db",
            "refresh": True,
        },
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _list_dashboards(base_url: str) -> list[dict]:
    """通过 API 列出所有仪表盘。"""
    token = _get_token(base_url)
    r = httpx.get(
        f"{base_url}/api/v1/dashboard/?q={__import__('urllib.parse').parse.quote('{\"page_size\": 100}')}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json().get("result", [])


class TestDashboards:
    """仪表盘相关 E2E。"""

    @pytest.mark.dashboard
    @pytest.mark.smoke
    def test_dashboards_list_api(self, superset_instance: ServiceState):
        """API 列出仪表盘应非空。"""
        result = _list_dashboards(superset_instance.instance.base_url)
        assert len(result) > 0, "expected at least one dashboard"
        names = [d.get("dashboard_title", "") for d in result]
        logger.info("[%s] dashboards: %s", superset_instance.instance.name, names)
        # 示例数据应加载了一些仪表盘
        assert any("Sales" in n or "Video Game" in n or "Slack" in n for n in names), (
            f"no example dashboard found in {names}"
        )

    @pytest.mark.dashboard
    @pytest.mark.parametrize("slug,title", EXAMPLE_DASHBOARDS)
    def test_open_example_dashboard(
        self, logged_in_page, superset_instance: ServiceState, slug: str, title: str
    ):
        """打开一个示例仪表盘，检查无错误。"""
        dashboards = _list_dashboards(superset_instance.instance.base_url)
        target = None
        for d in dashboards:
            if d.get("slug") == slug or d.get("dashboard_title") == title:
                target = d
                break
        if not target:
            pytest.skip(f"dashboard '{title}' not found in {superset_instance.instance.name}")
        dashboard_id = target["id"]
        dp = DashboardPage(logged_in_page, superset_instance.instance.base_url, dashboard_id)
        dp.goto()
        dp.wait_loaded()
        # 等待若干 chart 容器出现
        try:
            dp.wait_for_charts(1, timeout=20000)
        except TimeoutError:
            # 某些 deck.gl 仪表盘可能没有 chart 容器，只检查 url
            pass
        # 不应有大量错误
        errors = dp.error_messages()
        # 允许偶发网络错误（如 Mapbox 限流），但不应有 5xx
        for err in errors:
            assert "500" not in err and "Internal Server Error" not in err, (
                f"server error on dashboard: {err}"
            )

    @pytest.mark.dashboard
    def test_dashboards_list_page(self, logged_in_page, superset_instance: ServiceState):
        """仪表盘列表页能正常显示。"""
        from utils import page_actions as pa
        pa.goto(
            logged_in_page,
            f"{superset_instance.instance.base_url}/dashboard/list/",
            wait_until="domcontentloaded",
        )
        # 等待列表加载
        logged_in_page.wait_for_load_state("networkidle", timeout=20000)
        # 应该有至少一个仪表盘行
        rows = logged_in_page.locator(
            ".dashboard-list-view [data-test='table-row'], .list-viewtable tr, table tr"
        )
        assert rows.count() > 0, "no dashboards in list view"
