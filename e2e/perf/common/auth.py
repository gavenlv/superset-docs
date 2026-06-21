"""性能测试的认证工具（多用户池版）。

每个 Locust User 在 on_start 时调用 `acquire_user(role)` 拿到自己的 User 对象，
之后用 `token_for(user, base_url)` / `csrf_for(user, base_url)` 取凭据。

兼容性：旧的 `get_cached_token(base_url)` 仍然可用，回退到 admin 单用户。
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from config.settings import CONFIG, User
from utils.api import login_client
from utils.user_pool import user_pool as _pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Locust 上下文：把当前 VU 的 user 绑到 thread-local
# ---------------------------------------------------------------------------

_tls = threading.local()


def bind_user(user: User) -> None:
    """把当前线程的 user 绑到 thread-local（Locust User 类用）。"""
    _tls.user = user


def current_user() -> User | None:
    """当前线程绑定的 user（Locust task 里取）。"""
    return getattr(_tls, "user", None)


def acquire_user(role: str) -> User:
    """为当前 VU 分配一个用户（round_robin），并绑到 thread-local。"""
    user = _pool.acquire(role)
    bind_user(user)
    _pool.mark_active(user)
    logger.debug("[acquire] role=%s user=%s", role, user.username)
    return user


# ---------------------------------------------------------------------------
# 凭据获取（per-user）
# ---------------------------------------------------------------------------


def get_cached_token(base_url: str) -> str:
    """获取登录 token，缓存 10 分钟。回退到 admin（兼容旧调用）。"""
    user = current_user()
    if user is None:
        # 旧调用：没有绑 user，回退到 admin
        return _legacy_cached_token(base_url)
    return _pool.token_for(user, base_url)


def get_csrf(base_url: str) -> str:
    user = current_user()
    if user is None:
        # 旧调用路径下没有 CSRF，给个空字符串（GET 操作不需要）
        return ""
    return _pool.csrf_for(user, base_url)


# ---------------------------------------------------------------------------
# 旧路径（admin 单用户），保留兼容
# ---------------------------------------------------------------------------

_legacy_cache: dict[str, tuple[str, float]] = {}
_legacy_lock = threading.Lock()
_LEGACY_TTL = 600


def _legacy_cached_token(base_url: str) -> str:
    now = time.time()
    with _legacy_lock:
        cached = _legacy_cache.get(base_url)
        if cached and (now - cached[1]) < _LEGACY_TTL:
            return cached[0]
    client, token = login_client(base_url)
    client.close()
    with _legacy_lock:
        _legacy_cache[base_url] = (token, now)
    return token


# ---------------------------------------------------------------------------
# 显式 client（per-user），写操作需要
# ---------------------------------------------------------------------------


def make_auth_client(base_url: str) -> tuple[httpx.Client, str, dict[str, str]]:
    """构造带认证的 httpx.Client + JWT + headers（per-user）。

    调用方负责 client.close()。
    """
    user = current_user()
    if user is not None:
        token = _pool.token_for(user, base_url)
    else:
        token = _legacy_cached_token(base_url)
    client = httpx.Client(base_url=base_url, timeout=15.0)
    headers = {"Authorization": f"Bearer {token}"}
    return client, token, headers


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def admin_creds() -> dict[str, str]:
    """admin 凭据（兼容旧调用）。"""
    return {"username": CONFIG.admin_username, "password": CONFIG.admin_password}


def pool_summary() -> dict:
    """当前池状态（调试用）。"""
    return {
        "active": _pool.active_count(),
        "by_role": {r: _pool.active_count(r) for r in _pool.all_roles()},
    }
