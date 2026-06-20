"""Page Object Model: Superset Explore 页（单图表）。"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, Page, expect

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExplorePage:
    """Superset Explore 单图表页。"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_chart(self, chart_id: int) -> "ExplorePage":
        url = f"{self.base_url}/superset/explore/?slice_id={chart_id}"
        self.page.goto(url, wait_until="domcontentloaded")
        return self

    def wait_chart_rendered(self, timeout: int = 30000) -> None:
        """等待图表渲染（svg 或 canvas 出现）。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            # ECharts 用 svg 或 canvas
            chart_els = self.page.locator("svg, canvas")
            if chart_els.count() > 0:
                # 再等一下让动画完成
                time.sleep(0.5)
                return
            time.sleep(0.5)
        raise TimeoutError("chart not rendered within timeout")

    def has_error(self) -> bool:
        return self.page.locator(".alert-danger, [data-test='query-error']").count() > 0

    def error_message(self) -> str:
        loc = self.page.locator(".alert-danger, [data-test='query-error']").first
        if loc.count() > 0:
            return (loc.text_content() or "").strip()
        return ""

    def viz_type(self) -> str:
        loc = self.page.locator("[data-test='viz-type']")
        if loc.count() > 0:
            return (loc.text_content() or "").strip()
        return ""
