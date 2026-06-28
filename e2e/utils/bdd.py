"""BDD 辅助：让测试自然语言可读 + 报告高亮焦点。

设计目标（为什么这样设计）：
- 可读性：测试用例像自然语言，非技术人员也能看懂
- 轻量：不引入 pytest-bdd（依赖重、配置复杂），自实现轻量版本
- 可观测：每个步骤自动高亮 + 截图 + Allure step
- 灵活：与 Playwright 无缝集成，支持任意页面操作

核心概念：
- given：前置条件（已登录、页面已加载等）
- when：触发动作（点击、输入、导航等）
- then：验证结果（断言、检查状态等）
- and_：补充步骤（连续操作或验证）

为什么不用 pytest-bdd：
- pytest-bdd 需要单独的 feature 文件和 step 定义
- 配置复杂，学习曲线陡峭
- 与 Playwright 集成不够灵活
- 本框架的 BDD 更轻量，直接在测试函数中使用

为什么用上下文管理器（with）：
- 自动管理高亮的添加和移除
- 异常时自动截图
- 自动创建 Allure step

用法：
    from utils.bdd import given, when, then, and_
    
    with given("已登录 admin", page=page, focus="header"):
        pass
    with when("点击提交", page=page, focus="button.submit"):
        pa.click(page, "button.submit")
    with then("显示成功消息", screenshot=True):
        assert page.locator(".success").count() > 0
"""
from __future__ import annotations

import logging
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import allure

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 焦点高亮（仅对有 page 的步骤生效）
# ---------------------------------------------------------------------------

# 高亮 CSS：注入一次，红框 + 渐变 + 角标 + 动画
_HIGHLIGHT_CSS = """
/* BDD focus highlight — visible in headed and headless modes */
.__bdd_focus__ {
    position: relative !important;
    outline: 4px solid #ff3366 !important;
    outline-offset: 3px !important;
    box-shadow:
        0 0 0 8px rgba(255, 51, 102, 0.18),
        0 0 24px 4px rgba(255, 51, 102, 0.55) !important;
    background: rgba(255, 51, 102, 0.06) !important;
    transition: outline 180ms ease-in-out, box-shadow 180ms ease-in-out, background 180ms ease-in-out !important;
    animation: bddPulse 1.4s ease-in-out infinite;
    z-index: 999999 !important;
}

@keyframes bddPulse {
    0%, 100% {
        box-shadow:
            0 0 0 8px rgba(255, 51, 102, 0.18),
            0 0 24px 4px rgba(255, 51, 102, 0.55);
    }
    50% {
        box-shadow:
            0 0 0 12px rgba(255, 51, 102, 0.28),
            0 0 36px 8px rgba(255, 51, 102, 0.85);
    }
}

/* 右上角 BDD 角标 */
.__bdd_focus__::after {
    content: "● BDD";
    position: absolute;
    top: -16px;
    right: -16px;
    background: #ff3366;
    color: #fff;
    font: bold 11px/1 -apple-system, "Segoe UI", sans-serif;
    padding: 4px 8px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    z-index: 1000000;
    pointer-events: none;
    letter-spacing: 0.5px;
}

/* 左上角 step 标签角标 */
.__bdd_focus__::before {
    content: attr(data-bdd-step);
    position: absolute;
    top: -16px;
    left: -16px;
    background: #00b3a4;
    color: #fff;
    font: bold 10px/1 -apple-system, "Segoe UI", sans-serif;
    padding: 4px 8px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    z-index: 1000000;
    pointer-events: none;
    max-width: 200px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
"""

_HIGHLIGHT_JS = """
(target, stepLabel) => {
  if (!target) return false;
  // 移除旧高亮
  document.querySelectorAll('.__bdd_focus__').forEach(el => {
    el.classList.remove('__bdd_focus__');
    if (el.__bdd_old_style !== undefined) {
      el.style.cssText = el.__bdd_old_style;
      delete el.__bdd_old_style;
    }
    el.removeAttribute('data-bdd-step');
  });
  // 加新高亮
  target.classList.add('__bdd_focus__');
  target.__bdd_old_style = target.style.cssText;
  target.style.cssText += '; outline: 4px solid #ff3366 !important; outline-offset: 3px !important;';
  if (stepLabel) {
    target.setAttribute('data-bdd-step', stepLabel);
  }
  // 滚到视野
  try { target.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
  return true;
}
"""

_STYLE_INJECTED_ATTR = "__bdd_styles__"


def _ensure_highlight_css(page: Any) -> None:
    """注入一次高亮 CSS。"""
    try:
        if not page.evaluate(f"!!document.documentElement.getAttribute('{_STYLE_INJECTED_ATTR}')"):
            page.add_style_tag(content=_HIGHLIGHT_CSS)
            page.evaluate(
                f"document.documentElement.setAttribute('{_STYLE_INJECTED_ATTR}', '1')"
            )
    except Exception:  # noqa: BLE001
        pass


def highlight(page: Any, selector: str, *, label: str = "") -> None:
    """高亮一个元素（按 selector 找第一个匹配）。

    Args:
        page: Playwright page
        selector: CSS selector
        label: 显示在左上角角标的步骤描述（短文本）
    """
    if page is None or not selector:
        return
    try:
        _ensure_highlight_css(page)
        loc = page.locator(selector).first
        if loc.count() == 0:
            return
        handle = loc.element_handle()
        if handle is None:
            return
        # 截断 label
        short_label = (label or "").strip()[:30]
        page.evaluate(
            """({el, lbl}) => {
                const target = el;
                if (!target) return false;
                document.querySelectorAll('.__bdd_focus__').forEach(e => {
                    e.classList.remove('__bdd_focus__');
                    if (e.__bdd_old_style !== undefined) {
                        e.style.cssText = e.__bdd_old_style;
                        delete e.__bdd_old_style;
                    }
                    e.removeAttribute('data-bdd-step');
                });
                target.classList.add('__bdd_focus__');
                target.__bdd_old_style = target.style.cssText;
                target.style.cssText += '; outline: 4px solid #ff3366 !important; outline-offset: 3px !important;';
                if (lbl) target.setAttribute('data-bdd-step', lbl);
                try { target.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
                return true;
            }""",
            {"el": handle, "lbl": short_label},
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("highlight failed: %s", e)


# ---------------------------------------------------------------------------
# 截图 / 附件
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "screenshots"


def _attach_screenshot(page: Any, name: str) -> None:
    """截图并附加到当前 allure step。"""
    if page is None:
        return
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        path = REPORTS_DIR / f"{ts}_{name}.png"
        page.screenshot(path=str(path), full_page=False)
        allure.attach.file(
            str(path),
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("screenshot failed: %s", e)


def _attach_html(page: Any, name: str) -> None:
    """附加当前页 HTML 片段（便于排查）。"""
    if page is None:
        return
    try:
        html = page.content()
        allure.attach(
            html[:50000],  # 截断 50KB，避免太大
            name=name,
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("attach html failed: %s", e)


def _attach_text(text: str, name: str) -> None:
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


# ---------------------------------------------------------------------------
# 步骤上下文：与 page 关联
# ---------------------------------------------------------------------------

# 局部线程存储：当前活跃 page（由 step 调用方注入）
_ACTIVE_PAGE: Any = None
_ACTION_LOG: list[str] = []


def set_active_page(page: Any) -> None:
    """测试入口处调用，注入当前 page。"""
    global _ACTIVE_PAGE
    _ACTIVE_PAGE = page


def clear_active_page() -> None:
    global _ACTIVE_PAGE
    _ACTIVE_PAGE = None
    _ACTION_LOG.clear()


def action_log() -> list[str]:
    return list(_ACTION_LOG)


# ---------------------------------------------------------------------------
# Step context managers
# ---------------------------------------------------------------------------

@contextmanager
def given(text: str, *, page: Any = None, focus: str = "", screenshot: bool = False, label: str = "") -> Iterator[None]:
    """Given: 前置条件。

    Args:
        text: 步骤描述
        page: 关联的 Playwright page（可选）
        focus: 高亮元素的 CSS selector
        screenshot: 是否截图附加
        label: 高亮角标文本（默认用 text）
    """
    with allure.step(f"Given: {text}"):
        if page is not None:
            set_active_page(page)
        if focus:
            highlight(page, focus, label=label or text)
        if screenshot and page is not None:
            _attach_screenshot(page, "given")
        _ACTION_LOG.append(f"GIVEN: {text}")
        try:
            yield
        except Exception:
            if page is not None:
                _attach_screenshot(page, "given_failure")
            raise


@contextmanager
def when(text: str, *, page: Any = None, focus: str = "", screenshot: bool = False, label: str = "") -> Iterator[None]:
    """When: 触发动作。"""
    with allure.step(f"When: {text}"):
        if page is not None:
            set_active_page(page)
        if focus:
            highlight(page, focus, label=label or text)
        if screenshot and page is not None:
            _attach_screenshot(page, "when")
        _ACTION_LOG.append(f"WHEN:  {text}")
        try:
            yield
        except Exception:
            if page is not None:
                _attach_screenshot(page, "when_failure")
            raise


@contextmanager
def then(text: str, *, page: Any = None, focus: str = "", screenshot: bool = False, label: str = "") -> Iterator[None]:
    """Then: 验证结果。"""
    with allure.step(f"Then: {text}"):
        if page is not None:
            set_active_page(page)
        if focus:
            highlight(page, focus, label=label or text)
        if screenshot and page is not None:
            _attach_screenshot(page, "then")
        _ACTION_LOG.append(f"THEN:  {text}")
        try:
            yield
        except Exception:
            if page is not None:
                _attach_screenshot(page, "then_failure")
            raise


@contextmanager
def and_(text: str, *, page: Any = None, focus: str = "", screenshot: bool = False, label: str = "") -> Iterator[None]:
    """And: 补充步骤。"""
    with allure.step(f"And: {text}"):
        if page is not None:
            set_active_page(page)
        if focus:
            highlight(page, focus, label=label or text)
        if screenshot and page is not None:
            _attach_screenshot(page, "and")
        _ACTION_LOG.append(f"AND:   {text}")
        try:
            yield
        except Exception:
            if page is not None:
                _attach_screenshot(page, "and_failure")
            raise


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------

def scenario(title: str, *, tags: tuple[str, ...] = (), feature: str | None = None):
    """装饰器：把测试标记为 BDD 场景。

    用法：
        @scenario("列出所有数据库", tags=("database", "smoke"))
        def test_list_databases(superset_instance):
            '''Scenario: List all databases
            When ...
            Then ...
            '''
    """
    import pytest

    def deco(fn):
        fn._bdd_title = title
        fn._bdd_tags = tags
        if feature:
            fn._bdd_feature = feature
        # 自动注册 pytest marker
        for tag in tags:
            marker = getattr(pytest.mark, tag, None)
            if marker is not None:
                fn = marker(fn)
        # 注入 Allure 标签
        try:
            fn = allure.title(title)(fn)
            if feature:
                fn = allure.feature(feature)(fn)
            for tag in tags:
                fn = allure.tag(tag)(fn)
        except Exception:  # noqa: BLE001
            pass
        return fn

    return deco


def attach_action_log_on_failure() -> None:
    """在测试失败时把动作链附加到 allure。"""
    log_text = "\n".join(_ACTION_LOG) or "(no actions logged)"
    _attach_text(log_text, "action_log")


def assert_with_msg(condition: bool, msg: str) -> None:
    """带场景上下文的断言。"""
    assert condition, f"[BDD] {msg}"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """中文 → pytest 英文 slug（保留兼容）。"""
    mapping = {
        "列出": "list", "获取": "get", "创建": "create", "修改": "edit",
        "删除": "delete", "测试连接": "test_connection", "渲染": "render",
        "切换": "switch", "保存": "save", "导出": "export", "导入": "import",
        "下载": "download", "列表": "list", "详情": "details",
    }
    out = text.lower()
    for k, v in mapping.items():
        out = out.replace(k, v)
    out = "".join(c if c.isalnum() or c == "_" else "_" for c in out)
    return "_".join(s for s in out.split("_") if s) or "scenario"
