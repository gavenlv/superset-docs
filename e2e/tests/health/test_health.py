"""测试：Superset 健康检查。"""
from __future__ import annotations

import logging

import httpx
import pytest

from config.settings import CONFIG
from utils.service import ServiceState

logger = logging.getLogger(__name__)


class TestHealth:
    """Web / API 基础健康检查。"""

    @pytest.mark.health
    @pytest.mark.smoke
    def test_health_endpoint(self, superset_instance: ServiceState):
        """/health 端点应返回 200。"""
        url = f"{superset_instance.instance.base_url}/health"
        r = httpx.get(url, timeout=10.0)
        assert r.status_code == 200, f"health endpoint returned {r.status_code}"
        # /health 返回 "OK"
        assert r.text.strip() == "OK", f"unexpected health body: {r.text!r}"

    @pytest.mark.health
    @pytest.mark.smoke
    def test_login_api(self, superset_instance: ServiceState):
        """admin 用户应能登录。"""
        url = f"{superset_instance.instance.base_url}/api/v1/security/login"
        r = httpx.post(
            url,
            json={
                "username": CONFIG.admin_username,
                "password": CONFIG.admin_password,
                "provider": "db",
                "refresh": True,
            },
            timeout=15.0,
        )
        assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 50, "token seems too short"

    @pytest.mark.health
    @pytest.mark.smoke
    def test_login_page_loads(self, page, superset_instance: ServiceState):
        """登录页应能正常加载。"""
        from pages.login_page import LoginPage

        lp = LoginPage(page, superset_instance.instance.base_url)
        lp.goto()
        # 4.1 直接渲染表单；6.0 是 SPA 需等待 form 出现
        try:
            page.wait_for_selector('input[name="username"]', timeout=20000, state="attached")
        except Exception:  # noqa: BLE001
            # 退化：找任何 username 输入框
            page.wait_for_selector('input[type="text"]', timeout=10000, state="attached")
        assert "login" in page.url.lower()
