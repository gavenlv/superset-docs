"""Page Object Model: Superset 登录页。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from playwright.sync_api import Page, expect

from utils import page_actions as pa

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LoginPage:
    """Superset 登录页。"""

    URL_TEMPLATE = "{base}/login/"

    # 4.1 / 6.0 选择器兼容
    SEL_USERNAME = 'input[name="username"], input[id="username"]'
    SEL_PASSWORD = 'input[name="password"], input[id="password"]'
    SEL_SUBMIT = 'input[type="submit"], button[type="submit"]'
    SEL_ERROR = ".alert-danger, [role='alert']"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self) -> "LoginPage":
        pa.goto(self.page, self.URL_TEMPLATE.format(base=self.base_url), wait_until="load")
        return self

    def _wait_form(self, timeout: int = 30000) -> None:
        """等待登录表单出现（兼容 4.1 / 6.0 两种 DOM）。"""
        from utils.stability import wait_for
        wait_for(
            lambda: self.page.locator(self.SEL_USERNAME).count() > 0,
            timeout=timeout,
            description="login form username input",
        )

    def login(self, username: str, password: str) -> None:
        self._wait_form()
        # 高亮 + 填值
        pa.fill(self.page, self.SEL_USERNAME, username)
        pa.fill(self.page, self.SEL_PASSWORD, password)
        # 高亮 + 点击
        pa.click(self.page, self.SEL_SUBMIT)
        # 等待跳转
        expect(self.page).not_to_have_url(
            f"{self.base_url}/login/", timeout=20000
        )

    def login_expect_fail(self, username: str, password: str) -> str:
        """尝试登录，期望失败，返回错误信息。"""
        self._wait_form()
        pa.fill(self.page, self.SEL_USERNAME, username)
        pa.fill(self.page, self.SEL_PASSWORD, password)
        pa.click(self.page, self.SEL_SUBMIT)
        # 抓取错误提示
        err_locator = self.page.locator(self.SEL_ERROR)
        if err_locator.count() > 0:
            return err_locator.first.text_content() or ""
        return ""
