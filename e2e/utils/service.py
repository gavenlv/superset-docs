"""Docker compose 服务编排。

支持两种模式:
- cold: 冷启动（docker compose down -v && up -d），保证从干净状态加载示例数据
- reuse: 复用已启动的服务，仅做健康检查
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from config.settings import CONFIG, SupersetInstance
from utils.process import get_container_state, run_subprocess, wait_for_http_ok

logger = logging.getLogger(__name__)


@dataclass
class ServiceState:
    """服务启动后的状态信息。"""

    instance: SupersetInstance
    started_by_us: bool
    health_check_seconds: float
    api_token_len: int | None = None


def _docker_compose(
    instance: SupersetInstance,
    *args: str,
    timeout: int = 1800,
) -> None:
    """在指定实例目录下执行 docker compose。"""
    run_subprocess(
        ["docker", "compose", *args],
        cwd=instance.compose_dir,
        timeout=timeout,
        check=True,
    )


def _ensure_healthy(instance: SupersetInstance, *, timeout: float = 300.0) -> None:
    """等待实例的 web 端口健康。"""
    health_url = f"{instance.base_url}/health"
    logger.info("[%s] waiting for %s ...", instance.name, health_url)
    wait_for_http_ok(health_url, timeout=timeout, expected_status=200)


def _login_and_get_token(instance: SupersetInstance) -> int:
    """登录获取 JWT token，返回 token 长度。"""
    api = f"{instance.base_url}/api/v1/security/login"
    resp = httpx.post(
        api,
        json={"username": CONFIG.admin_username, "password": CONFIG.admin_password, "provider": "db", "refresh": True},
        timeout=15.0,
    )
    resp.raise_for_status()
    return len(resp.json()["access_token"])


def cold_start_instance(instance: SupersetInstance) -> ServiceState:
    """冷启动一个 Superset 实例。"""
    started_at = time.time()
    logger.info("[%s] cold start (mode=cold) ...", instance.name)
    logger.info("[%s] docker compose down -v", instance.name)
    _docker_compose(instance, "down", "-v", timeout=120)
    logger.info("[%s] docker compose up -d", instance.name)
    _docker_compose(instance, "up", "-d", timeout=1800)  # init 容器需要几分钟加载示例
    _ensure_healthy(instance, timeout=600)  # web 容器需要更长时间启动
    elapsed = time.time() - started_at
    token_len = _login_and_get_token(instance)
    return ServiceState(
        instance=instance,
        started_by_us=True,
        health_check_seconds=elapsed,
        api_token_len=token_len,
    )


def reuse_instance(instance: SupersetInstance) -> ServiceState:
    """复用已启动的 Superset 实例。"""
    started_at = time.time()
    logger.info("[%s] reuse (mode=reuse) ...", instance.name)
    # 检查 web 容器状态
    web_container = f"superset-{instance.name}"
    state = get_container_state(web_container)
    if state != "running":
        raise RuntimeError(
            f"[{instance.name}] web container '{web_container}' is not running "
            f"(state={state}). Start it manually or use mode=cold."
        )
    _ensure_healthy(instance, timeout=60)
    elapsed = time.time() - started_at
    token_len = _login_and_get_token(instance)
    return ServiceState(
        instance=instance,
        started_by_us=False,
        health_check_seconds=elapsed,
        api_token_len=token_len,
    )


def shutdown_instance(instance: SupersetInstance) -> None:
    """关闭实例（仅冷启动模式下调用）。"""
    logger.info("[%s] docker compose down", instance.name)
    _docker_compose(instance, "down", timeout=120)
