"""多用户池（多环境 / 多角色 / 多用户并发）。

设计目标（为什么这样设计）：
- 线程安全：性能测试 200+ VU 并发请求用户，必须保证线程安全
- Token 缓存：避免每次请求都登录，提升测试吞吐量
- 多策略选用户：支持 random/round_robin/index 三种策略，满足不同场景
- 角色回退：当某角色没有用户时，自动回退到 admin，保证测试不中断
- 单例模式：全局唯一实例，避免重复初始化

核心概念：
- UserPool：线程安全的用户池类
- _UserToken：per-user, per-base_url 的 token 缓存项
- user_pool：全局单例，所有测试共享
- pick()：选用户（支持三种策略）
- acquire()：为压测 VU 分配用户（round_robin）
- token_for()：获取/刷新用户的 JWT token

用法（E2E 测试）：
    from utils.user_pool import user_pool
    viewer = user_pool.pick("viewer")             # 随机一个 viewer
    v1     = user_pool.pick("viewer", index=1)    # 索引取（确定）
    token  = user_pool.token_for(viewer, base_url)

用法（性能测试）：
    # 每个 VU 在 on_start 里调用
    user = user_pool.acquire("viewer")  # round_robin 分配
    token = user_pool.token_for(user, base_url)
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
    """per-user, per-base_url 的 token 缓存项。
    
    为什么需要这个类：
    - 登录 API 开销大，每次请求都登录会降低测试吞吐量
    - Superset JWT 默认有效期 1 小时，可以缓存复用
    - CSRF token 也需要缓存（写操作需要）
    
    为什么用 __slots__：
    - 性能优化：减少内存占用，提升访问速度
    - 明确字段：防止运行时动态添加属性
    
    字段说明：
    - token：JWT access_token
    - csrf：CSRF token（写操作需要）
    - expires_at：过期时间戳（秒）
    
    is_valid 为什么提前 30s：
    - 防止 token 在请求过程中过期
    - 比如请求发出时有效，但响应回来时过期
    - 30s 缓冲足够覆盖大多数 API 请求时间
    """

    __slots__ = ("token", "csrf", "expires_at")

    def __init__(self, token: str, csrf: str, expires_at: float) -> None:
        self.token = token
        self.csrf = csrf
        self.expires_at = expires_at

    @property
    def is_valid(self) -> bool:
        """检查 token 是否有效（提前 30s 过期）。"""
        return time.time() < self.expires_at - 30


# ---------------------------------------------------------------------------
# UserPool
# ---------------------------------------------------------------------------


class UserPool:
    """线程安全的用户池。
    
    为什么需要线程安全：
    - 性能测试中，200+ VU（虚拟用户）并发运行，每个 VU 都需要获取用户
    - 如果不加锁，可能出现：
      1. 同一用户被多个 VU 同时使用（导致登录冲突）
      2. Token 缓存竞争条件（缓存被覆盖）
      3. 轮询游标不一致（用户分配不均匀）
    
    为什么用 RLock 而不是 Lock：
    - RLock 是可重入锁，允许同一线程多次获取同一把锁
    - pick() 内部可能调用其他需要锁的方法，不会死锁
    - Lock 会导致死锁（同一线程第二次获取同一把锁时阻塞）
    
    内部数据结构：
    - _tokens：(username, base_url) -> _UserToken，缓存用户的 JWT
    - _cursor：role -> int，轮询策略的游标
    - _active：role -> set[str]，当前活跃用户（用于统计）
    """

    def __init__(self) -> None:
        # 可重入锁，保护所有共享状态
        self._lock = threading.RLock()
        # (username, base_url) -> _UserToken，token 缓存
        self._tokens: dict[tuple[str, str], _UserToken] = {}
        # role -> cursor，轮询策略的游标（defaultdict 自动初始化）
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
        
        三种策略对比：
        
        | 策略 | 适用场景 | 特点 |
        |-----|---------|------|
        | random | E2E 测试 | 随机选，模拟真实场景 |
        | round_robin | 性能测试 | 均匀分配，避免某用户被过度使用 |
        | index | 多用户 E2E | 固定用户，方便调试和复现 |
        
        为什么需要角色回退：
        - 如果某角色没有配置用户（比如 sit 环境的 embed 角色），测试会失败
        - 自动回退到 admin，保证测试能继续运行
        - 记录 warning 日志，提醒用户补充配置
        
        为什么 round_robin 需要锁：
        - 多个线程同时调用时，需要保证游标递增的原子性
        - 不加锁可能导致多个线程拿到相同的索引
        
        Args:
            role: 角色（admin/analyst/viewer/embed）
            index: 固定索引（确定性取，index % len(users) 处理越界）
            strategy: random | round_robin
        
        Returns:
            User 对象
        
        Raises:
            RuntimeError: admin 角色也没有用户时抛出
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
            # 固定索引：取 users[index % len(users)]，处理越界
            return users[index % len(users)]

        if strategy == "round_robin":
            # 轮询：线程安全的游标递增
            with self._lock:
                idx = self._cursor[role] % len(users)
                self._cursor[role] += 1
            return users[idx]

        # 随机：简单随机选择
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
        """获取（必要时刷新）user 在 base_url 的 JWT。
        
        为什么 key 是 (username, base_url) 而不是只 username：
        - 同一用户可能在不同环境（dev/sit/uat）有不同的 token
        - base_url 不同，token 也不同
        - 双维度 key 保证缓存的正确性
        
        为什么登录在锁外：
        - 登录 API 调用耗时较长（网络请求）
        - 如果在锁内登录，其他线程会阻塞等待
        - 先检查缓存（快速），需要登录时再释放锁去登录
        
        TTL 为什么默认 600s（10 分钟）：
        - Superset 默认 JWT 有效期是 1 小时
        - 10 分钟足够完成一个测试场景
        - 不会太长导致 token 过期
        - 可通过参数调整（比如长时间性能测试可以设更长）
        
        Args:
            user: User 对象
            base_url: Superset 实例的基础 URL
            ttl_sec: token 缓存有效期（秒），默认 10 分钟
        
        Returns:
            JWT access_token
        """
        key = (user.username, base_url)
        # 先检查缓存（快速路径）
        with self._lock:
            cached = self._tokens.get(key)
            if cached and cached.is_valid:
                return cached.token

        # 缓存失效，需要登录（慢路径，在锁外执行）
        token, csrf = _login(user, base_url)
        # 登录成功后更新缓存
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
