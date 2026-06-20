"""Page Object Model: Superset Explore 页（单图表）。"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, Page, expect

from utils import page_actions as pa

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExplorePage:
    """Superset Explore 单图表页。

    所有用户操作走 `utils.page_actions`，headed 模式下浏览器会实时高亮。
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_chart(self, chart_id: int) -> "ExplorePage":
        url = f"{self.base_url}/superset/explore/?slice_id={chart_id}"
        pa.goto(self.page, url)
        return self

    def click_run_button(self) -> None:
        """点击 Run / Update chart 按钮。"""
        for sel in [
            'button:has-text("Run")',
            '[data-test="run-query-button"]',
            'button:has-text("Update chart")',
            '[data-test="explore-run"]',
        ]:
            loc = self.page.locator(sel).first
            if loc.count() > 0:
                pa.click(self.page, sel)
                return
        # 退化：Ctrl+Enter
        pa.press(self.page, "Control+Enter")

    def select_dataset(self, value: str) -> None:
        """选择数据集（select_option 包装）。"""
        sel = 'select[data-test="datasource-select"], [data-test="datasource-select"] select'
        pa.select(self.page, sel, value)

    def click_save(self) -> None:
        """点击 Save 按钮。"""
        pa.click(self.page, '[data-test="query-save-button"], button:has-text("Save")')

    def wait_chart_rendered(self, timeout: int = 30000) -> None:
        """等待图表渲染（svg 或 canvas 出现）。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            chart_els = self.page.locator("svg, canvas")
            if chart_els.count() > 0:
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
