"""全局配置加载与管理。

支持：
- 多环境（dev / sit / uat / prod），通过 E2E_ENV 或 CLI --env 切换
- 环境变量覆盖默认值（CI / 本地切换）
- 多用户池（user_pool），按角色分配凭据
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 加载 .env（仓库根目录的）
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=False)

# 支持的环境
SUPPORTED_ENVS = ("dev", "sit", "uat", "prod")
DEFAULT_ENV = "dev"


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


def current_env() -> str:
    """当前激活的环境（dev/sit/uat/prod）。

    优先级：E2E_ENV 环境变量 > 默认 dev
    """
    env = _env_str("E2E_ENV", DEFAULT_ENV).lower().strip()
    if env not in SUPPORTED_ENVS:
        raise ValueError(
            f"unsupported E2E_ENV={env!r}; expected one of {SUPPORTED_ENVS}"
        )
    return env


@dataclass(frozen=True)
class User:
    """一个测试用户。"""

    username: str
    password: str
    role: str               # admin / analyst / viewer / embed
    label: str = ""         # 可选标识，便于定位
    extra: dict[str, Any] = field(default_factory=dict)


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

    # 激活的环境
    env: str = DEFAULT_ENV
    # 模式: cold=冷启动; reuse=复用现有服务
    mode: str = "reuse"
    # 是否在测试结束后清理冷启动的服务
    cleanup_on_exit: bool = True
    # admin 凭据（兼容旧调用）
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
    # 多用户池：role -> tuple[User, ...]
    user_pool: dict[str, tuple[User, ...]] = field(default_factory=dict)
    # 性能测试段（透传）
    perf: dict[str, Any] = field(default_factory=dict)

    @property
    def screenshots_dir(self) -> Path:
        return self.reports_dir / "screenshots"

    @property
    def allure_results_dir(self) -> Path:
        return self.reports_dir / "allure-results"

    # ------------------------------------------------------------------ #
    # 角色/用户 helpers                                                   #
    # ------------------------------------------------------------------ #

    def users_for_role(self, role: str) -> tuple[User, ...]:
        """返回某角色下的所有用户。"""
        return self.user_pool.get(role, ())

    def has_role(self, role: str) -> bool:
        return bool(self.users_for_role(role))


def _load_env_config(env: str) -> dict:
    """加载 e2e/config/config.yaml 与 config.<env>.yaml（env 覆盖 base）。

    优先级：config.<env>.yaml > config.yaml
    """
    cfg_dir = Path(__file__).parent
    base: dict = {}
    base_path = cfg_dir / "config.yaml"
    if base_path.exists():
        with base_path.open("r", encoding="utf-8") as f:
            base = yaml.safe_load(f) or {}

    if env == DEFAULT_ENV:
        return base

    env_path = cfg_dir / f"config.{env}.yaml"
    if not env_path.exists():
        return base
    with env_path.open("r", encoding="utf-8") as f:
        override = yaml.safe_load(f) or {}

    return _deep_merge(base, override)


def _deep_merge(base: dict, override: dict) -> dict:
    """dict 深合并：override 优先级最高。"""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _parse_user_pool(pool: dict | None) -> dict[str, tuple[User, ...]]:
    """解析 user_pool 配置。

    支持两种格式：
    1. 紧凑：`{admin: [admin/admin]}`
    2. 详细：`{admin: [{username: admin, password: admin, label: default}]}`
    """
    if not pool:
        return {}
    out: dict[str, tuple[User, ...]] = {}
    for role, users in pool.items():
        parsed: list[User] = []
        if not isinstance(users, list):
            continue
        for i, u in enumerate(users):
            if isinstance(u, str):
                # "user/pass" 格式
                if "/" in u:
                    name, pwd = u.split("/", 1)
                else:
                    name, pwd = u, ""
                parsed.append(User(username=name, password=pwd, role=role, label=f"{role}-{i}"))
            elif isinstance(u, dict):
                parsed.append(
                    User(
                        username=str(u.get("username", "")),
                        password=str(u.get("password", "")),
                        role=role,
                        label=str(u.get("label", f"{role}-{i}")),
                        extra={k: v for k, v in u.items() if k not in {"username", "password", "label"}},
                    )
                )
        out[role] = tuple(parsed)
    return out


def _resolve_target_instance(
    instances: tuple[SupersetInstance, ...], name: str
) -> SupersetInstance | None:
    for inst in instances:
        if inst.name == name:
            return inst
    return None


def build_config(env: str | None = None) -> TestConfig:
    """从 yaml + 环境变量构造配置。环境变量优先级最高。

    Args:
        env: 强制环境；None 时从 E2E_ENV / DEFAULT_ENV 读
    """
    active_env = env or current_env()
    yaml_cfg = _load_env_config(active_env)
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

    # env 下的 ENV 专属环境变量覆盖（E2E_BASE_URL_<env>_<version>）
    instances = tuple(
        SupersetInstance(
            name=str(i["name"]),
            version=str(i.get("version", i["name"])),
            base_url=_env_str(
                f"E2E_BASE_URL_{active_env.upper()}_{str(i['name']).replace('.', '_')}",
                _env_str(
                    f"E2E_BASE_URL_{str(i['name']).replace('.', '_')}",
                    str(i["base_url"]),
                ),
            ),
            compose_dir=(_REPO_ROOT / i["compose_dir"]).resolve(),
            postgres_container=str(i["postgres_container"]),
            redis_container=(
                str(i["redis_container"]) if i.get("redis_container") else None
            ),
        )
        for i in instances_yaml
    )

    user_pool = _parse_user_pool(yaml_cfg.get("user_pool"))

    return TestConfig(
        env=active_env,
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
        user_pool=user_pool,
        perf=yaml_cfg.get("perf", {}),
    )


def reload_config(env: str | None = None) -> TestConfig:
    """重新构建配置（用于测试或 CLI 切换环境）。"""
    global CONFIG
    CONFIG = build_config(env=env)
    return CONFIG


# 全局实例（默认 dev）
CONFIG = build_config()
