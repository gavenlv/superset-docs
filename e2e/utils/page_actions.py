"""Page Action 包装器：让 Playwright 操作自带高亮和动作记录。

设计目标（headed 模式可观测）：
- click()  / hover()  / fill()  / type()  / press()  / select_option()  / check()
- 操作前 1.2s：高亮目标元素（红框 + 角标 + 呼吸动画）
- 操作中：执行原 Playwright 调用
- 操作后 0.3s：保留高亮（便于观察结果）
- 整个动作链写到 Allure step + 动作日志

为不影响性能与现有调用，所有函数接受 Page 和 selector，并返回 Playwright 原生结果。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import allure
from playwright.sync_api import Locator, Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _locator(page: Page, selector: str) -> Locator:
    """统一拿 locator。"""
    return page.locator(selector).first


def _highlight(page: Page, selector: str, *, action: str, value: str = "") -> None:
    """高亮目标 + 在角标显示动作名。"""
    try:
        from utils.bdd import highlight

        loc = page.locator(selector).first
        if loc.count() == 0:
            return
        handle = loc.element_handle()
        if handle is None:
            return
        # 角标：<action> + 可选 value
        if value:
            label = f"{action}: {value[:20]}"
        else:
            label = action
        highlight(page, selector, label=label)
        # 慢一点，让 headed 模式用户能看到
        page.wait_for_timeout(50)
    except Exception as e:  # noqa: BLE001
        logger.debug("highlight failed: %s", e)


def _unhighlight(page: Page) -> None:
    """清除所有高亮（内部通过重新设置空 selector 触发）。"""
    try:
        page.evaluate(
            """() => {
                document.querySelectorAll('.__bdd_focus__').forEach(e => {
                    e.classList.remove('__bdd_focus__');
                    if (e.__bdd_old_style !== undefined) {
                        e.style.cssText = e.__bdd_old_style;
                        delete e.__bdd_old_style;
                    }
                    e.removeAttribute('data-bdd-step');
                });
            }"""
        )
    except Exception:  # noqa: BLE001
        pass


def _with_action(
    page: Page,
    selector: str,
    action: str,
    value: Any,
    func: Callable[[Locator], Any],
) -> Any:
    """通用包装：highlight + run + keep highlight 一会儿。"""
    with allure.step(f"Action: {action} -> {selector} {f'(value={value!r})' if value is not None else ''}"):
        _highlight(page, selector, action=action, value=str(value) if value is not None else "")
        try:
            loc = page.locator(selector).first
            result = func(loc)
        finally:
            # 操作后保留高亮 300ms（headed 模式可观察）
            try:
                page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                pass
        return result


# ---------------------------------------------------------------------------
# 操作 API
# ---------------------------------------------------------------------------

def click(page: Page, selector: str, *, timeout: float = 10000) -> None:
    """高亮并点击。"""
    def _do(loc: Locator) -> None:
        loc.click(timeout=timeout)
    _with_action(page, selector, "click", None, _do)


def hover(page: Page, selector: str, *, timeout: float = 10000) -> None:
    """高亮并 hover。"""
    def _do(loc: Locator) -> None:
        loc.hover(timeout=timeout)
    _with_action(page, selector, "hover", None, _do)


def fill(page: Page, selector: str, value: str, *, timeout: float = 10000) -> None:
    """高亮并 fill（清空后填值）。"""
    def _do(loc: Locator) -> None:
        loc.fill(value, timeout=timeout)
    _with_action(page, selector, "fill", value, _do)


def type_text(page: Page, selector: str, value: str, *, delay_ms: int = 30, timeout: float = 10000) -> None:
    """高亮并逐字 type（保留原有内容 + 追加）。"""
    def _do(loc: Locator) -> None:
        loc.press_sequentially(value, delay=delay_ms, timeout=timeout)
    _with_action(page, selector, "type", value, _do)


def press(page: Page, key: str) -> None:
    """按键（在当前焦点元素上）。"""
    with allure.step(f"Action: press {key!r}"):
        page.keyboard.press(key)


def select(page: Page, selector: str, value: str, *, timeout: float = 10000) -> None:
    """高亮并 select_option。"""
    def _do(loc: Locator) -> None:
        loc.select_option(value, timeout=timeout)
    _with_action(page, selector, "select", value, _do)


def check(page: Page, selector: str, *, timeout: float = 10000) -> None:
    """高亮并勾选 checkbox。"""
    def _do(loc: Locator) -> None:
        loc.check(timeout=timeout)
    _with_action(page, selector, "check", None, _do)


def uncheck(page: Page, selector: str, *, timeout: float = 10000) -> None:
    """高亮并取消勾选。"""
    def _do(loc: Locator) -> None:
        loc.uncheck(timeout=timeout)
    _with_action(page, selector, "uncheck", None, _do)


def focus(page: Page, selector: str) -> None:
    """只高亮 + 聚焦，不做操作。"""
    with allure.step(f"Action: focus -> {selector}"):
        _highlight(page, selector, action="focus")
        loc = page.locator(selector).first
        loc.focus()


def goto(page: Page, url: str, *, wait_until: str = "domcontentloaded", timeout: int = 30000) -> None:
    """带动作记录的 goto。"""
    with allure.step(f"Action: goto {url}"):
        page.goto(url, wait_until=wait_until, timeout=timeout)


def clear_highlights(page: Page) -> None:
    """手动清除所有高亮。"""
    _unhighlight(page)
