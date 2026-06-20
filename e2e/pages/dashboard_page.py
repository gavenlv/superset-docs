"""Page Object Model: Superset 仪表盘页。"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, Page, expect

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DashboardPage:
    """Superset 仪表盘详情页。"""

    def __init__(self, page: Page, base_url: str, dashboard_id_or_slug: str | int):
        self.page = page
        self.base_url = base_url
        self.dashboard_id = str(dashboard_id_or_slug)

    @property
    def url(self) -> str:
        return f"{self.base_url}/superset/dashboard/{self.dashboard_id}/"

    def goto(self) -> "DashboardPage":
        self.page.goto(self.url, wait_until="domcontentloaded")
        return self

    def wait_loaded(self, timeout: int = 30000) -> None:
        """等待仪表盘加载完成（slice 容器出现）。"""
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def chart_containers(self) -> Locator:
        """所有图表容器。"""
        return self.page.locator(".dashboard-component-chart-holder, [data-test='chart-container']")

    def chart_count(self) -> int:
        return self.chart_containers().count()

    def wait_for_charts(self, expected: int, timeout: int = 30000) -> None:
        """等待图表数量达到预期。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            count = self.chart_count()
            if count >= expected:
                logger.info("dashboard loaded, %d charts visible", count)
                return
            time.sleep(0.5)
        raise TimeoutError(
            f"expected at least {expected} charts on dashboard, got {self.chart_count()}"
        )

    def has_error_banner(self) -> bool:
        """是否存在错误提示。"""
        return self.page.locator(".alert-danger, [data-test='query-error']").count() > 0

    def error_messages(self) -> list[str]:
        locs = self.page.locator(".alert-danger, [data-test='query-error']").all()
        return [l.text_content() or "" for l in locs]

    def title(self) -> str:
        loc = self.page.locator("[data-test='dashboard-title']")
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
        return self.page.title()
