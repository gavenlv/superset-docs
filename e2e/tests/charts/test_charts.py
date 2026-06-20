"""测试：单图表（Charts）E2E。"""
from __future__ import annotations

import json
import logging
import urllib.parse

import httpx
import pytest

from config.settings import CONFIG
from pages.explore_page import ExplorePage
from utils.service import ServiceState

logger = logging.getLogger(__name__)


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


def _list_charts(base_url: str, page_size: int = 200) -> list[dict]:
    token = _get_token(base_url)
    q = json.dumps({"page_size": page_size})
    r = httpx.get(
        f"{base_url}/api/v1/chart/?q={urllib.parse.quote(q)}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json().get("result", [])


class TestCharts:
    """单图表 E2E。"""

    @pytest.mark.chart
    @pytest.mark.smoke
    def test_charts_list_api(self, superset_instance: ServiceState):
        """API 列出图表应非空。"""
        charts = _list_charts(superset_instance.instance.base_url)
        assert len(charts) > 0, "expected at least one chart"
        logger.info("[%s] %d charts", superset_instance.instance.name, len(charts))

    @pytest.mark.chart
    def test_charts_query_data_api(self, superset_instance: ServiceState):
        """至少一个图表能成功执行查询。"""
        charts = _list_charts(superset_instance.instance.base_url)
        token = _get_token(superset_instance.instance.base_url)
        success = 0
        for c in charts:
            viz = c.get("viz_type")
            if viz in ("pivot_table", "table", "pivot_table_v2"):
                # 4.1 / 6.0 对这些类型的查询参数格式略不同，跳过
                continue
            try:
                r = httpx.get(
                    f"{superset_instance.instance.base_url}/api/v1/chart/{c['id']}/data/?q={urllib.parse.quote(json.dumps({'force': True}))}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0,
                )
                if r.status_code == 200:
                    success += 1
                    if success >= 3:
                        break
            except httpx.HTTPError as e:
                logger.debug("chart %s query error: %s", c["id"], e)
        assert success >= 1, "no chart returned data successfully"

    @pytest.mark.chart
    @pytest.mark.slow
    def test_open_one_chart_in_explore(
        self, logged_in_page, superset_instance: ServiceState
    ):
        """打开一个图表到 Explore 页，检查能渲染。"""
        charts = _list_charts(superset_instance.instance.base_url)
        # 找一个 big_number 或 bar 类型的简单图表
        target = None
        for c in charts:
            if c.get("viz_type") in ("big_number", "big_number_total", "bar", "echarts_timeseries_bar"):
                target = c
                break
        if not target:
            target = charts[0]
        chart_id = target["id"]
        logger.info(
            "[%s] opening chart %s (%s) in Explore",
            superset_instance.instance.name,
            chart_id,
            target.get("viz_type"),
        )
        ep = ExplorePage(logged_in_page, superset_instance.instance.base_url)
        ep.goto_chart(chart_id)
        ep.wait_chart_rendered(timeout=45000)
        # 不应有错误
        if ep.has_error():
            msg = ep.error_message()
            # 允许 Mapbox 类限流错误
            assert "429" in msg or "rate" in msg.lower() or "Mapbox" in msg, (
                f"unexpected error in chart: {msg}"
            )
