"""Page Object Model: Superset SQL Lab 页。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from playwright.sync_api import Page, expect

from utils import page_actions as pa

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SqlLabPage:
    """Superset SQL Lab 页。

    所有用户操作走 `utils.page_actions`，headed 模式下浏览器会实时高亮。
    """

    SEL_EDITOR = ".ace_editor, [data-test='sql-editor']"
    SEL_RUN_BTN = 'button:has-text("Run"), [data-test="run-query-button"], button.btn-primary:has-text("Run")'

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self) -> "SqlLabPage":
        # 4.1 / 6.0 都是 /sqllab/，不是 /superset/sqllab/
        pa.goto(
            self.page,
            f"{self.base_url}/sqllab/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        return self

    def wait_loaded(self, timeout: int = 30000) -> None:
        """等待 SQL Lab 加载完成。

        6.0 / 4.1 用 ace editor，可能没有固定 selector；退化为等 sql 面板容器。
        """
        from utils.stability import wait_for
        try:
            wait_for(
                lambda: self.page.locator(
                    '.ace_editor, .ace_content, [data-test="sql-editor"], .SqlEditor, .sql-editor'
                ).count() > 0,
                timeout=timeout / 1000,
                description="SQL Lab editor",
            )
        except Exception:  # noqa: BLE001
            wait_for(
                lambda: self.page.locator(
                    '[class*="SqlEditor"], [class*="sql"], [class*="Ace"]'
                ).count() > 0,
                timeout=10,
                description="SQL Lab any selector",
            )

    def new_tab(self) -> "SqlLabPage":
        """新建一个 SQL 查询 tab（如果当前没有编辑器）。"""
        return self

    def click_editor(self) -> None:
        """点击编辑器区域获得焦点。"""
        pa.click(self.page, self.SEL_EDITOR)

    def type_query(self, sql: str) -> None:
        """在当前编辑器输入 SQL。"""
        # 高亮 + 点击获得焦点
        self.click_editor()
        # 全选 + 删除（高亮不必要，纯键盘操作）
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        # 直接输入
        self.page.keyboard.type(sql, delay=10)

    def run_query(self, timeout: int = 30000) -> None:
        """点击 Run 按钮（高亮 + click）。"""
        # Run 按钮的常见 selector
        clicked = False
        for sel in [
            'button:has-text("Run")',
            '[data-test="run-query-button"]',
            'button.btn-primary:has-text("Run")',
        ]:
            loc = self.page.locator(sel).first
            if loc.count() > 0:
                pa.click(self.page, sel)
                clicked = True
                break
        if not clicked:
            # 快捷键 Ctrl+Enter
            pa.press(self.page, "Control+Enter")
        # 等待结果
        self.wait_results(timeout)

    def wait_results(self, timeout: int = 30000) -> None:
        """等待查询结果出现。

        6.0 / 4.1 结果展示: ant-table / .sql-result-table / table 标签
        至少要出现结果表或错误提示。
        """
        from utils.stability import wait_for
        result_selectors = [
            ".sql-result-table",
            "[data-test='table-row']",
            ".ant-table-cell",
            ".ant-table-row",
            ".result-set",
            "[data-test='query-result']",
        ]
        error_selectors = [
            ".alert-danger",
            "[data-test='query-error']",
        ]
        try:
            wait_for(
                lambda: any(
                    self.page.locator(sel).count() > 0
                    for sel in result_selectors + error_selectors
                ),
                timeout=timeout / 1000,
                description="SQL Lab query result or error",
            )
        except TimeoutError:
            if self.page.locator(".ant-spin, .loading, [class*='Loading']").count() > 0:
                raise TimeoutError("query still loading after timeout")
            raise

    def has_error(self) -> bool:
        return self.page.locator(".alert-danger, [data-test='query-error']").count() > 0

    def error_message(self) -> str:
        loc = self.page.locator(".alert-danger, [data-test='query-error']").first
        if loc.count() > 0:
            return (loc.text_content() or "").strip()
        return ""

    def result_row_count(self) -> int:
        """返回结果行数。

        6.0 用 .ant-table-row, 4.1 用 .sql-result-table tbody tr
        """
        n = self.page.locator(".ant-table-row").count()
        if n > 0:
            return n
        rows = self.page.locator(".sql-result-table tbody tr, [data-test='table-row']")
        return rows.count()
