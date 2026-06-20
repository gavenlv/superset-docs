"""稳定性辅助：通用重试 + 健壮选择器。

不依赖 Playwright auto-wait 的场景（如同步的 wait_for_x）可使用这里。
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, TypeVar

from playwright.sync_api import Locator, Page, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

T = TypeVar("T")


def wait_for(
    func: Callable[[], T],
    *,
    timeout: float = 30.0,
    interval: float = 0.5,
    description: str = "condition",
) -> T:
    """通用轮询等待。"""
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            result = func()
            if result:
                return result
        except Exception as e:  # noqa: BLE001
            last_exc = e
        time.sleep(interval)
    raise TimeoutError(f"timeout waiting for: {description} (last exc: {last_exc})")


def robust_click(
    page: Page,
    selectors: Iterable[str],
    *,
    timeout: float = 10.0,
    description: str = "click target",
) -> None:
    """尝试多个 selector 直到点击成功。"""
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        for sel in selectors:
            loc: Locator = page.locator(sel).first
            try:
                if loc.count() > 0 and loc.is_visible():
                    loc.click()
                    logger.debug("clicked %s via %s", description, sel)
                    return
            except Exception as e:  # noqa: BLE001
                last_err = e
        time.sleep(0.2)
    raise PWTimeout(f"failed to click {description}: {last_err}")


def safe_text(loc: Locator, default: str = "") -> str:
    """获取文本，找不到返回默认值。"""
    try:
        if loc.count() > 0:
            return (loc.first.text_content() or "").strip()
    except Exception:  # noqa: BLE001
        pass
    return default
