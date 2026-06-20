"""Playwright 相关 fixture：浏览器、上下文、登录页面。"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    expect,
    sync_playwright,
)

from config.settings import CONFIG
from fixtures.conftest import superset_instance  # noqa: F401  注入实例 fixture
from utils.service import ServiceState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playwright 启动 / 关闭
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    """全局 Playwright 实例。"""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    """浏览器实例。"""
    browser_name = CONFIG.browser
    if browser_name == "chromium":
        b = playwright.chromium.launch(headless=CONFIG.headless)
    elif browser_name == "firefox":
        b = playwright.firefox.launch(headless=CONFIG.headless)
    elif browser_name == "webkit":
        b = playwright.webkit.launch(headless=CONFIG.headless)
    else:
        raise ValueError(f"Unknown browser: {browser_name}")
    try:
        yield b
    finally:
        b.close()


# ---------------------------------------------------------------------------
# 每个测试一个全新的 context / page（隔离 cookies、localStorage）
# ---------------------------------------------------------------------------

@pytest.fixture()
def context(browser: Browser, superset_instance: ServiceState) -> Iterator[BrowserContext]:
    """隔离的浏览器 context。"""
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
        locale="en-US",
    )
    ctx.set_default_timeout(CONFIG.page_timeout_ms)
    ctx.set_default_navigation_timeout(CONFIG.navigation_timeout_ms)
    yield ctx
    ctx.close()


@pytest.fixture()
def page(context: BrowserContext, superset_instance: ServiceState) -> Iterator[Page]:
    """测试页面，失败时自动截图。"""
    p = context.new_page()
    yield p
    # 截图由 pytest_runtest_makereport hook 处理
    p.close()


# ---------------------------------------------------------------------------
# Allure 报告附件
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """测试失败时自动附加截图与 HTML 到 Allure。"""
    import allure

    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    if not report.failed:
        return

    # 找 page fixture
    page_obj = item.funcargs.get("page") if hasattr(item, "funcargs") else None
    if not page_obj:
        return

    try:
        screenshots_dir: Path = CONFIG.screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        # 用例名 + 版本
        instance = item.funcargs.get("superset_instance")
        version = instance.instance.name if instance else "unknown"
        test_name = item.name
        screenshot_path = screenshots_dir / f"{test_name}__{version}__{ts}.png"
        page_obj.screenshot(path=str(screenshot_path), full_page=True)
        allure.attach.file(
            str(screenshot_path),
            name=f"screenshot-{version}",
            attachment_type=allure.attachment_type.PNG,
        )
        # 附加 HTML
        html = page_obj.content()
        allure.attach(html, name=f"html-{version}", attachment_type=allure.attachment_type.HTML)
    except Exception as e:  # noqa: BLE001
        logger.warning("failed to attach screenshot: %s", e)


# ---------------------------------------------------------------------------
# 登录后的 page（最常用）
# ---------------------------------------------------------------------------

@pytest.fixture()
def logged_in_page(
    page: Page,
    superset_instance: ServiceState,
) -> Page:
    """已经登录 admin 的页面。"""
    from pages.login_page import LoginPage

    base = superset_instance.instance.base_url
    lp = LoginPage(page, base)
    lp.goto()
    lp.login(CONFIG.admin_username, CONFIG.admin_password)
    logger.info("[%s] logged in, current url: %s", superset_instance.instance.name, page.url)
    return page
