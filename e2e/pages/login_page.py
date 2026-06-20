"""Page Object Model: Superset 登录页。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LoginPage:
    """Superset 登录页。"""

    URL_TEMPLATE = "{base}/login/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self) -> "LoginPage":
        # 4.1 是 server-rendered；6.0 是 SPA，需等待 JS 加载
        # 用 load 事件确保所有资源加载完
        self.page.goto(
            self.URL_TEMPLATE.format(base=self.base_url),
            wait_until="load",
            timeout=30000,
        )
        return self

    def _wait_form(self, timeout: int = 30000) -> None:
        """等待登录表单出现（兼容 4.1 / 6.0 两种 DOM）。"""
        from utils.stability import wait_for
        wait_for(
            lambda: self.page.locator(
                'input[name="username"], input[id="username"]'
            ).count() > 0,
            timeout=timeout,
            description="login form username input",
        )

    def login(self, username: str, password: str) -> None:
        self._wait_form()
        # 优先用 name；4.1 仅有 name，6.0 仅有 id
        user_sel = 'input[name="username"], input[id="username"]'
        pass_sel = 'input[name="password"], input[id="password"]'
        # submit: 4.1 是 input[type=submit]，6.0 是 button[type=submit]
        submit_sel = (
            'input[type="submit"], button[type="submit"]'
        )
        self.page.locator(user_sel).first.fill(username)
        self.page.locator(pass_sel).first.fill(password)
        self.page.locator(submit_sel).first.click()
        # 等待跳转到非 /login/
        expect(self.page).not_to_have_url(
            f"{self.base_url}/login/", timeout=20000
        )

    def login_expect_fail(self, username: str, password: str) -> str:
        """尝试登录，期望失败，返回错误信息。"""
        self._wait_form()
        user_sel = 'input[name="username"], input[id="username"]'
        pass_sel = 'input[name="password"], input[id="password"]'
        submit_sel = 'input[type="submit"], button[type="submit"]'
        self.page.locator(user_sel).first.fill(username)
        self.page.locator(pass_sel).first.fill(password)
        self.page.locator(submit_sel).first.click()
        # 抓取错误提示
        err_locator = self.page.locator(".alert-danger, [role='alert']")
        if err_locator.count() > 0:
            return err_locator.first.text_content() or ""
        return ""
