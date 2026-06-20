"""测试：Superset 认证。"""
from __future__ import annotations

import logging

import pytest
from playwright.sync_api import expect

from config.settings import CONFIG
from pages.login_page import LoginPage
from utils.service import ServiceState

logger = logging.getLogger(__name__)


class TestAuth:
    """认证 / 登录相关 E2E。"""

    @pytest.mark.auth
    @pytest.mark.smoke
    def test_admin_login_success(self, page, superset_instance: ServiceState):
        """admin 用正确凭据登录应成功。"""
        lp = LoginPage(page, superset_instance.instance.base_url)
        lp.goto()
        lp.login(CONFIG.admin_username, CONFIG.admin_password)
        # 登录成功后页面不应该停在 /login/
        assert "/login/" not in page.url, f"still on login page: {page.url}"

    @pytest.mark.auth
    def test_wrong_password_fails(self, page, superset_instance: ServiceState):
        """错误密码应登录失败。"""
        lp = LoginPage(page, superset_instance.instance.base_url)
        lp.goto()
        msg = lp.login_expect_fail(CONFIG.admin_username, "wrong_password")
        # 应当有错误提示，或者仍然停留在登录页
        assert ("/login/" in page.url) or (msg != ""), (
            "expected login failure feedback, but page navigated away"
        )

    @pytest.mark.auth
    def test_logout_via_api(self, logged_in_page, superset_instance: ServiceState, context):
        """通过 API 登出（点击 UI 菜单因版本变化较大，API 更稳定）。"""
        import httpx
        from config.settings import CONFIG

        base = superset_instance.instance.base_url
        # 获取 CSRF token
        page = logged_in_page
        # Superset 登出走 /logout/ 路径，会清 session
        resp = context.request.get(f"{base}/logout/", max_redirects=0)
        # 应当 302 跳到 /login/，session 被清
        assert resp.status in (200, 302), f"unexpected logout status: {resp.status}"
        # 再次访问 /superset/welcome/ 应被重定向到 login
        page.goto(f"{base}/superset/welcome/", wait_until="load", timeout=20000)
        assert "/login" in page.url.lower(), f"after logout, expected /login, got {page.url}"

    @pytest.mark.auth
    def test_logout(self, logged_in_page, superset_instance: ServiceState):
        """点击 UI 菜单 Logout（尽力兼容，未找到则 skip）。"""
        page = logged_in_page
        # 进入用户菜单（右上角头像）— 各版本不同 selector
        clicked_menu = False
        for sel in [
            "[data-test='user-info']",
            "[data-test='navbar-user']",
            ".navbar-right .dropdown-toggle",
            ".ant-avatar",
        ]:
            if page.locator(sel).count() > 0:
                try:
                    page.locator(sel).first.click(timeout=3000)
                    clicked_menu = True
                    break
                except Exception:  # noqa: BLE001
                    continue
        if not clicked_menu:
            pytest.skip("user menu selector not found, use test_logout_via_api instead")
        # 点击 Logout
        for sel in [
            'a:has-text("Logout")',
            '[data-test="menu-item-logout"]',
            'button:has-text("Logout")',
            'a:has-text("退出")',
        ]:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                break
        else:
            pytest.skip("logout button not found in menu")
        try:
            page.wait_for_url(f"{superset_instance.instance.base_url}/login/", timeout=10000)
        except Exception:  # noqa: BLE001
            assert "/login" in page.url.lower()
