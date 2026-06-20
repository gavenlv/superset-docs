"""全局配置加载与管理。

支持通过环境变量覆盖默认值，方便 CI 与本地切换。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 加载 .env（仓库根目录的）
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    return int(val)


def _env_str(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val else default


@dataclass(frozen=True)
class SupersetInstance:
    """一个 Superset 实例的连接信息。"""

    name: str            # "4.1" / "6.0"
    version: str         # "4.1.1" / "6.0.0"
    base_url: str        # http://localhost:18088
    compose_dir: Path    # ../superset-4.1
    postgres_container: str
    redis_container: str | None

    @property
    def is_v6(self) -> bool:
        return self.name.startswith("6")


@dataclass(frozen=True)
class TestConfig:
    """全局测试配置。"""

    # 模式: cold=冷启动; reuse=复用现有服务
    mode: str = "reuse"
    # 是否在测试结束后清理冷启动的服务
    cleanup_on_exit: bool = True
    # admin 凭据
    admin_username: str = "admin"
    admin_password: str = "admin"
    # 浏览器
    browser: str = "chromium"  # chromium | firefox | webkit
    headless: bool = True
    # 超时（毫秒）
    page_timeout_ms: int = 30000
    navigation_timeout_ms: int = 60000
    # 重试
    reruns: int = 2
    reruns_delay: int = 3
    # 报告路径
    reports_dir: Path = field(default_factory=lambda: _REPO_ROOT / "e2e" / "reports")
    # Superset 实例列表
    instances: tuple[SupersetInstance, ...] = field(default_factory=tuple)

    @property
    def screenshots_dir(self) -> Path:
        return self.reports_dir / "screenshots"

    @property
    def allure_results_dir(self) -> Path:
        return self.reports_dir / "allure-results"


def _load_yaml_config() -> dict:
    cfg_path = Path(__file__).parent / "config.yaml"
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def build_config() -> TestConfig:
    """从 yaml + 环境变量构造配置。环境变量优先级最高。"""
    yaml_cfg = _load_yaml_config()
    mode = _env_str("E2E_MODE", yaml_cfg.get("mode", "reuse"))
    instances_yaml = yaml_cfg.get("instances", [])

    # 默认实例（4.1 / 6.0）
    if not instances_yaml:
        instances_yaml = [
            {
                "name": "4.1",
                "version": "4.1.1",
                "base_url": "http://localhost:18088",
                "compose_dir": "../superset-4.1",
                "postgres_container": "superset-4.1-postgres",
                "redis_container": "superset-4.1-redis",
            },
            {
                "name": "6.0",
                "version": "6.0.0",
                "base_url": "http://localhost:18089",
                "compose_dir": "../superset-6.0",
                "postgres_container": "superset-6.0-postgres",
                "redis_container": "superset-6.0-redis",
            },
        ]

    instances = tuple(
        SupersetInstance(
            name=str(i["name"]),
            version=str(i.get("version", i["name"])),
            base_url=_env_str(
                f"E2E_BASE_URL_{str(i['name']).replace('.', '_')}",
                str(i["base_url"]),
            ),
            compose_dir=(_REPO_ROOT / i["compose_dir"]).resolve(),
            postgres_container=str(i["postgres_container"]),
            redis_container=(
                str(i["redis_container"]) if i.get("redis_container") else None
            ),
        )
        for i in instances_yaml
    )

    return TestConfig(
        mode=mode,
        cleanup_on_exit=_env_bool("E2E_CLEANUP", yaml_cfg.get("cleanup_on_exit", True)),
        admin_username=_env_str("E2E_ADMIN_USER", yaml_cfg.get("admin_username", "admin")),
        admin_password=_env_str("E2E_ADMIN_PASSWORD", yaml_cfg.get("admin_password", "admin")),
        browser=_env_str("E2E_BROWSER", yaml_cfg.get("browser", "chromium")),
        headless=_env_bool("E2E_HEADLESS", yaml_cfg.get("headless", True)),
        page_timeout_ms=_env_int("E2E_PAGE_TIMEOUT_MS", yaml_cfg.get("page_timeout_ms", 30000)),
        navigation_timeout_ms=_env_int(
            "E2E_NAV_TIMEOUT_MS", yaml_cfg.get("navigation_timeout_ms", 60000)
        ),
        reruns=_env_int("E2E_RERUNS", yaml_cfg.get("reruns", 2)),
        reruns_delay=_env_int("E2E_RERUNS_DELAY", yaml_cfg.get("reruns_delay", 3)),
        instances=instances,
    )


CONFIG = build_config()
