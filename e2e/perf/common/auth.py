"""性能测试的认证工具。

包装 utils.api 的 login_client / csrf_token，提供 Locust 友好的同步接口。
"""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from utils.api import login_client
from config.settings import CONFIG


# 线程级 token 缓存（同一 worker 复用登录结果）
_token_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()
_TOKEN_TTL = 600  # 10 分钟重新登录


def get_cached_token(base_url: str) -> str:
    """获取登录 token，缓存 10 分钟。

    Locust 每个 user 会调用一次；同 base_url 共享缓存。
    """
    now = time.time()
    with _cache_lock:
        cached = _token_cache.get(base_url)
        if cached and (now - cached[1]) < _TOKEN_TTL:
            return cached[0]
    # 缓存外登录
    client, token = login_client(base_url)
    client.close()
    with _cache_lock:
        _token_cache[base_url] = (token, now)
    return token


def make_auth_client(base_url: str) -> tuple[httpx.Client, str, dict[str, str]]:
    """构造带认证的 httpx.Client + JWT + headers。

    返回 (client, token, headers)。调用方负责 client.close()。
    """
    client, token = login_client(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    return client, token, headers


def admin_creds() -> dict[str, str]:
    """从 CONFIG 读 admin 凭据。"""
    return {
        "username": CONFIG.admin_username,
        "password": CONFIG.admin_password,
    }
