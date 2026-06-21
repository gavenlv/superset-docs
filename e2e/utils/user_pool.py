"""多用户池（多环境 / 多角色 / 多用户并发）。

能力：
- 从 config 读取 user_pool
- 按角色挑用户（随机 / 轮询 / 索引）
- 线程安全的 per-user token 缓存
- 角色未配用户时回退到 admin（兼容旧调用）

用法（E2E）：
    from utils.user_pool import user_pool
    viewer = user_pool.pick("viewer")             # 随机一个 viewer
    v1     = user_pool.pick("viewer", index=1)    # 索引取（确定）
    token  = user_pool.token_for(viewer, base_url)

用法（性能）：
    见 perf/common/auth.py —— 每个 VU 在 on_start 里调 user_pool.acquire(role)
"""
from __future__ import annotations

import logging
import random
import threading
import time
from collections import defaultdict
from typing import Any, Iterator

import httpx

from config.settings import CONFIG, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# token 缓存（per-user, per-base_url）
# ---------------------------------------------------------------------------


class _UserToken:
    """per-user, per-base_url 的 token 缓存项。"""

    __slots__ = ("token", "csrf", "expires_at")

    def __init__(self, token: str, csrf: str, expires_at: float) -> None:
        self.token = token
        self.csrf = csrf
        self.expires_at = expires_at

    @property
    def is_valid(self) -> bool:
        return time.time() < self.expires_at - 30  # 提前 30s 刷新


# ---------------------------------------------------------------------------
# UserPool
# ---------------------------------------------------------------------------


class UserPool:
    """线程安全的用户池。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # (username, base_url) -> _UserToken
        self._tokens: dict[tuple[str, str], _UserToken] = {}
        # role -> cursor（用于轮询）
        self._cursor: dict[str, int] = defaultdict(int)
        # role -> 当前活跃用户集合（压测统计用）
        self._active: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------ #
    # 选用户                                                             #
    # ------------------------------------------------------------------ #

    def users(self, role: str) -> tuple[User, ...]:
        return CONFIG.users_for_role(role)

    def has(self, role: str) -> bool:
        return CONFIG.has_role(role)

    def pick(self, role: str, *, index: int | None = None, strategy: str = "random") -> User:
        """挑一个用户。

        Args:
            role: 角色
            index: 固定索引（确定性取）
            strategy: random | round_robin
        """
        users = self.users(role)
        if not users:
            # 兼容旧代码：回退到 admin
            if role != "admin":
                logger.warning(
                    "[user_pool] role %r has no users; falling back to admin", role
                )
                return self.pick("admin", index=index, strategy=strategy)
            raise RuntimeError(
                f"no users configured for role {role!r}; check user_pool in config"
            )

        if index is not None:
            return users[index % len(users)]

        if strategy == "round_robin":
            with self._lock:
                idx = self._cursor[role] % len(users)
                self._cursor[role] += 1
            return users[idx]

        return random.choice(users)

    def acquire(self, role: str) -> User:
        """为压测 VU 分配一个用户。round_robin 分配（保证均匀使用）。"""
        return self.pick(role, strategy="round_robin")

    def release(self, user: User) -> None:
        """标记用户空闲（压测统计用）。"""
        with self._lock:
            self._active[user.role].discard(user.username)

    def mark_active(self, user: User) -> None:
        with self._lock:
            self._active[user.role].add(user.username)

    def active_count(self, role: str | None = None) -> int:
        if role:
            return len(self._active[role])
        return sum(len(v) for v in self._active.values())

    def all_roles(self) -> tuple[str, ...]:
        return tuple(CONFIG.user_pool.keys())

    # ------------------------------------------------------------------ #
    # token 缓存                                                          #
    # ------------------------------------------------------------------ #

    def token_for(
        self,
        user: User,
        base_url: str,
        *,
        ttl_sec: int = 600,
    ) -> str:
        """获取（必要时刷新）user 在 base_url 的 JWT。"""
        key = (user.username, base_url)
        with self._lock:
            cached = self._tokens.get(key)
            if cached and cached.is_valid:
                return cached.token

        # 登录
        token, csrf = _login(user, base_url)
        with self._lock:
            self._tokens[key] = _UserToken(
                token=token, csrf=csrf, expires_at=time.time() + ttl_sec
            )
        return token

    def csrf_for(self, user: User, base_url: str) -> str:
        key = (user.username, base_url)
        with self._lock:
            cached = self._tokens.get(key)
            if cached and cached.is_valid:
                return cached.csrf
        # 触发重新登录
        self.token_for(user, base_url)
        return self._tokens[key].csrf

    def invalidate(self, user: User, base_url: str | None = None) -> None:
        """清掉某用户的 token（强制重登）。"""
        with self._lock:
            if base_url:
                self._tokens.pop((user.username, base_url), None)
            else:
                keys = [k for k in self._tokens if k[0] == user.username]
                for k in keys:
                    self._tokens.pop(k, None)

    def clear_cache(self) -> None:
        with self._lock:
            self._tokens.clear()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _login(user: User, base_url: str) -> tuple[str, str]:
    """登录 + 拉 CSRF。失败抛异常（不要静默回退到 admin）。"""
    client = httpx.Client(base_url=base_url, timeout=15.0)
    r = client.post(
        "/api/v1/security/login",
        json={
            "username": user.username,
            "password": user.password,
            "provider": "db",
            "refresh": True,
        },
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    # CSRF
    r2 = client.get(
        "/api/v1/security/csrf_token/",
        headers={"Authorization": f"Bearer {token}"},
    )
    r2.raise_for_status()
    csrf = r2.json()["result"]
    client.close()
    return token, csrf


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------


user_pool = UserPool()


# ---------------------------------------------------------------------------
# helpers for fixtures
# ---------------------------------------------------------------------------


def iter_users(role: str) -> Iterator[User]:
    """遍历某角色所有用户（pytest parametrize 用）。"""
    return iter(user_pool.users(role))


def list_usernames(role: str) -> list[str]:
    return [u.username for u in user_pool.users(role)]


def pool_summary() -> dict[str, Any]:
    """调试用：当前池状态。"""
    return {
        "env": CONFIG.env,
        "roles": {
            role: [
                {"username": u.username, "label": u.label}
                for u in user_pool.users(role)
            ]
            for role in user_pool.all_roles()
        },
        "active": {
            role: sorted(user_pool._active[role])  # type: ignore[attr-defined]
            for role in user_pool.all_roles()
        },
        "cached_tokens": len(user_pool._tokens),  # type: ignore[attr-defined]
    }
