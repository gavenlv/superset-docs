"""Playwright 相关 fixture：浏览器、上下文、登录页面。

设计目标（为什么这样设计）：
- Fixture 生命周期分层：session（全局）→ function（每个测试）
- 隔离性：每个测试用例有独立的 browser context（cookies/localStorage 隔离）
- 可复用性：playwright 和 browser 是 session 级别的，避免重复创建
- 可观测性：失败时自动截图并附加到 Allure 报告
- 灵活性：支持多用户登录（login_as_role 工厂 fixture）

核心 Fixture 关系：
    playwright (session)
        └── browser (session)
            └── context (function)
                └── page (function)
                    └── logged_in_page (function)

关键概念：
- session scope：整个测试会话只创建一次（开销大的资源）
- function scope：每个测试用例创建一次（需要隔离的资源）
- 工厂 fixture：返回一个函数，按需创建多个实例（如多用户测试）
"""
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
# Playwright 启动 / 关闭（session 级别，全局共享）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    """全局 Playwright 实例（session 级别）。
    
    为什么是 session scope：
    - Playwright 启动开销大（加载浏览器引擎）
    - 整个测试会话只需要一个实例
    - 所有测试共享同一个 Playwright 实例
    
    为什么用 with 语句：
    - sync_playwright() 返回上下文管理器
    - 退出 with 块时自动清理资源（关闭浏览器引擎）
    - 保证资源释放，即使测试异常退出
    
    使用方式：
        def test_example(playwright):
            browser = playwright.chromium.launch()
            ...
    """
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    """浏览器实例（session 级别）。
    
    为什么是 session scope：
    - 浏览器进程很重（占用大量内存）
    - 启动/关闭浏览器需要时间
    - 所有测试共享同一个浏览器进程
    
    为什么不是 function scope：
    - 如果每个测试都启动一个浏览器，测试会非常慢
    - 浏览器进程可以安全地被多个测试共享
    
    为什么需要 try/finally：
    - 确保测试结束后浏览器被关闭
    - 即使测试异常失败，也能释放资源
    - 避免浏览器进程残留
    
    浏览器选择逻辑：
    - 从 CONFIG.browser 读取配置（chromium/firefox/webkit）
    - headless 模式由 CONFIG.headless 控制
    - CI 环境通常用 headless，本地调试用 headed
    
    使用方式：
        def test_example(browser):
            context = browser.new_context()
            page = context.new_page()
            ...
    """
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
    """隔离的浏览器 context（function 级别）。
    
    为什么是 function scope（最重要！）：
    - Browser Context 是浏览器的一个独立会话
    - 每个 context 有独立的 cookies、localStorage、sessionStorage
    - 如果两个测试共用一个 context，登录状态会互相污染
    - 一个测试的 logout() 会影响另一个测试的已登录状态
    
    为什么需要 viewport：
    - 设置固定视口大小（1440x900），保证截图一致性
    - 避免不同屏幕分辨率导致的布局差异
    - 模拟桌面端浏览器
    
    为什么 ignore_https_errors：
    - 测试环境可能使用自签名证书
    - 忽略 HTTPS 错误，避免测试失败
    
    为什么设置默认超时：
    - 从 CONFIG 读取超时配置，统一管理
    - page_timeout_ms：元素操作超时
    - navigation_timeout_ms：页面导航超时
    
    使用方式：
        def test_example(context):
            page = context.new_page()
            page.goto("http://localhost:8080")
            ...
    """
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
    """测试页面（function 级别），失败时自动截图。
    
    为什么是 function scope：
    - 每个测试用例需要一个干净的页面
    - 页面状态（DOM、JS 变量）不应在测试间共享
    
    为什么截图由 hook 处理而不是在这里：
    - 截图需要在测试失败时触发
    - pytest_runtest_makereport hook 能捕获测试结果
    - 在这里无法判断测试是否失败
    
    使用方式：
        def test_example(page):
            page.goto("http://localhost:8080")
            page.click("button")
            ...
    """
    p = context.new_page()
    yield p
    # 截图由 pytest_runtest_makereport hook 处理（见下方）
    p.close()


# ---------------------------------------------------------------------------
# Allure 报告附件（自动截图）
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """测试失败时自动附加截图与 HTML 到 Allure。
    
    为什么用 hookwrapper：
    - hookwrapper 允许我们在原始 hook 执行前后插入代码
    - yield 之前是执行前的准备，yield 之后是执行后的处理
    - 可以捕获测试结果（passed/failed/skipped）
    
    为什么 tryfirst=True：
    - 确保这个 hook 在其他 hook 之前执行
    - 保证截图是最新的页面状态
    
    为什么只在 call 阶段截图：
    - pytest 有三个阶段：setup、call、teardown
    - setup 失败：环境准备问题，截图可能没用
    - call 失败：测试逻辑失败，截图最有用
    - teardown 失败：清理问题，截图意义不大
    
    截图命名规则：
        {test_name}__{version}__{timestamp}.png
        例：test_login_admin__6.0__1781961422008.png
    
    为什么附加 HTML：
    - 截图只能看到视觉效果
    - HTML 可以查看完整的 DOM 结构
    - 方便排查元素不存在、样式问题等
    
    为什么用 try/except：
    - 截图可能失败（页面已关闭、网络问题）
    - 即使截图失败，测试结果仍应正常记录
    - 记录 warning 日志，不影响测试流程
    """
    import allure

    outcome = yield
    report = outcome.get_result()
    # 只在测试执行阶段（call）失败时截图
    if report.when != "call":
        return
    if not report.failed:
        return

    # 从测试用例参数中获取 page fixture
    page_obj = item.funcargs.get("page") if hasattr(item, "funcargs") else None
    if not page_obj:
        return

    try:
        # 确保截图目录存在
        screenshots_dir: Path = CONFIG.screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        # 获取 Superset 版本（用于截图命名）
        instance = item.funcargs.get("superset_instance")
        version = instance.instance.name if instance else "unknown"
        test_name = item.name
        screenshot_path = screenshots_dir / f"{test_name}__{version}__{ts}.png"
        # 全屏截图（full_page=True）
        page_obj.screenshot(path=str(screenshot_path), full_page=True)
        # 附加截图到 Allure
        allure.attach.file(
            str(screenshot_path),
            name=f"screenshot-{version}",
            attachment_type=allure.attachment_type.PNG,
        )
        # 附加 HTML（便于排查 DOM 问题）
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
    """已经登录 admin 的页面（function 级别）。
    
    为什么这个 fixture 很常用：
    - 大多数测试需要先登录
    - 避免每个测试都写重复的登录代码
    - 统一登录逻辑，修改时只需改一处
    
    为什么用 CONFIG.admin_username/admin_password：
    - 从配置读取，支持环境变量覆盖
    - 不同环境可能有不同的 admin 凭据
    - 避免硬编码
    
    使用方式：
        def test_example(logged_in_page):
            # 已经是登录状态，可以直接操作
            logged_in_page.goto("/dashboard")
            ...
    
    注意事项：
    - 默认登录 admin 用户
    - 如果需要其他角色，使用 login_as_role fixture
    """
    from pages.login_page import LoginPage

    base = superset_instance.instance.base_url
    lp = LoginPage(page, base)
    lp.goto()
    lp.login(CONFIG.admin_username, CONFIG.admin_password)
    logger.info("[%s] logged in, current url: %s", superset_instance.instance.name, page.url)
    return page


# ---------------------------------------------------------------------------
# 多用户登录 fixture（多用户并发 / 权限测试用）
# ---------------------------------------------------------------------------

@pytest.fixture()
def user_pool():
    """暴露 user_pool 单例（singleton）。
    
    为什么需要这个 fixture：
    - 让测试用例可以直接访问 user_pool
    - 用于自定义用户选择逻辑
    - 与多用户测试配合使用
    
    使用方式：
        def test_example(user_pool):
            viewer = user_pool.pick("viewer")
            print(viewer.username)
    """
    from utils.user_pool import user_pool
    return user_pool


@pytest.fixture()
def login_as_role(superset_instance: ServiceState, browser: Browser):
    """工厂 fixture：login_as_role(role, index=None) 返回已登录 page（独立 context）。
    
    为什么是工厂 fixture：
    - 测试可能需要多个不同角色的用户同时登录
    - 工厂模式允许按需创建任意数量的用户页面
    - 每个用户有独立的 browser context（完全隔离）
    
    为什么每个用户需要独立 context：
    - cookies 和 localStorage 是 context 级别的
    - 如果共用 context，多个用户的登录状态会冲突
    - 独立 context 模拟真实场景（不同浏览器/设备）
    
    为什么需要手动管理 context 生命周期：
    - factory fixture 创建的 context 不在 pytest 自动清理范围内
    - 需要在 yield 之后手动关闭所有创建的 context
    - 避免浏览器资源泄漏
    
    用法：
        def test_xxx(login_as_role):
            page = login_as_role("viewer", index=0)        # 固定 viewer[0]
            page2 = login_as_role("viewer", index=1)       # 固定 viewer[1]
            page3 = login_as_role("viewer")                # 随机 viewer
    """
    pages: list[tuple[Page, BrowserContext]] = []

    def _factory(role: str, *, index: int | None = None) -> Page:
        from pages.login_page import LoginPage
        from utils.user_pool import user_pool

        user = user_pool.pick(role, index=index)
        base = superset_instance.instance.base_url
        # 创建独立的 context（关键！隔离登录状态）
        ctx: BrowserContext = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
            locale="en-US",
        )
        ctx.set_default_timeout(CONFIG.page_timeout_ms)
        ctx.set_default_navigation_timeout(CONFIG.navigation_timeout_ms)
        p = ctx.new_page()
        # 记录已创建的页面和 context（用于清理）
        pages.append((p, ctx))
        lp = LoginPage(p, base)
        lp.goto()
        lp.login(user.username, user.password)
        logger.info(
            "[%s] login_as_role(%s) user=%s label=%s",
            superset_instance.instance.name, role, user.username, user.label,
        )
        return p

    yield _factory

    # 清理：关闭所有创建的页面和 context
    for p, ctx in pages:
        try:
            p.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture()
def multi_user_pages(
    superset_instance: ServiceState,
    request,
):
    """参数化多用户 fixture：从 user_pool 拿 N 个不同用户，每个一个 page。
    
    为什么需要这个 fixture：
    - 批量创建多个用户页面（比 login_as_role 更方便）
    - 支持参数化，通过 @pytest.mark.parametrize 指定用户数量
    - 自动清理所有创建的资源
    
    为什么用 request.param：
    - pytest parametrize 会把参数传给 fixture
    - request.param 就是参数值（用户数量）
    - indirect=True 让 parametrize 的参数传给 fixture
    
    为什么默认角色是 viewer：
    - viewer 用户数量通常最多（适合并发测试）
    - viewer 权限最低（安全，不会误操作）
    - 如需其他角色，使用 login_as_role
    
    用法：
        @pytest.mark.parametrize("multi_user_pages", [3], indirect=True)
        def test_concurrent_login(multi_user_pages):
            page1, page2, page3 = multi_user_pages
            ...

    或者直接通过 marker：
        @pytest.mark.multi_user(3)
        def test_xxx(multi_user_pages): ...
    """
    from pages.login_page import LoginPage
    from utils.user_pool import user_pool

    # 获取参数化的用户数量（默认 1）
    n = getattr(request, "param", 1) or 1
    base = superset_instance.instance.base_url
    role = "viewer"  # 默认 viewer（测试中可重写）

    browser = request.getfixturevalue("browser")
    out: list[Page] = []
    contexts: list = []
    for i in range(n):
        # 按索引取用户（保证每个用户不同）
        user = user_pool.pick(role, index=i)
        # 创建独立 context
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
            locale="en-US",
        )
        ctx.set_default_timeout(CONFIG.page_timeout_ms)
        ctx.set_default_navigation_timeout(CONFIG.navigation_timeout_ms)
        p = ctx.new_page()
        lp = LoginPage(p, base)
        lp.goto()
        lp.login(user.username, user.password)
        out.append(p)
        contexts.append(ctx)
    yield out
    # 清理
    for p, ctx in zip(out, contexts):
        try:
            p.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
