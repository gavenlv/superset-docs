"""全局配置加载与管理。

设计目标（为什么这样设计）：
- 多环境隔离：dev/sit/uat/prod 四套环境，配置独立，互不影响
- 分层合并：base config.yaml + env 覆盖，遵循 DRY 原则
- 优先级明确：yaml < env yaml < 环境变量，敏感信息可用环境变量覆盖
- 类型安全：用 dataclass 替代 dict，IDE 自动补全，运行时类型检查
- 不可变：frozen=True 防止运行时意外修改配置

核心概念：
- CONFIG：全局单例，程序启动时加载一次
- SUPPORTED_ENVS：允许的环境列表，防止拼写错误
- User/SupersetInstance/TestConfig：配置数据模型
- build_config()：从 yaml + 环境变量构建配置
- reload_config()：重新加载配置（用于测试或环境切换）

用法：
    from config.settings import CONFIG
    print(CONFIG.admin_username)
    print(CONFIG.env)
    
    # 切换环境
    reload_config(env="sit")
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
    """读取布尔类型的环境变量。
    
    为什么需要这个封装：
    - 环境变量值都是字符串，需要转换
    - 支持多种表示 true 的写法：1/true/yes/on
    - None/空字符串返回默认值
    
    示例：
        _env_bool("E2E_HEADLESS", True)  # "1" → True, "0" → False, "" → True
    """
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """读取整数类型的环境变量。
    
    为什么需要这个封装：
    - 环境变量值都是字符串，需要转换
    - None/空字符串返回默认值
    - 转换失败会抛异常（快速失败）
    
    示例：
        _env_int("E2E_RERUNS", 2)  # "3" → 3, "" → 2
    """
    val = os.environ.get(name)
    if val is None:
        return default
    return int(val)


def _env_str(name: str, default: str) -> str:
    """读取字符串类型的环境变量。
    
    为什么需要这个封装：
    - os.environ.get() 返回 None，而我们希望返回默认值
    - 统一处理空字符串（视为未设置）
    
    示例：
        _env_str("E2E_BROWSER", "chromium")  # "firefox" → "firefox", "" → "chromium"
    """
    val = os.environ.get(name)
    return val if val else default


def current_env() -> str:
    """当前激活的环境（dev/sit/uat/prod）。
    
    为什么这样设计：
    - 从 E2E_ENV 环境变量读取，支持 CLI --env 参数和 CI 环境变量
    - 小写 + 去空格，防止用户输入大小写不一致或多余空格
    - 验证是否在 SUPPORTED_ENVS 列表中，快速发现拼写错误
    
    优先级：E2E_ENV 环境变量 > 默认 dev
    
    示例：
        # 命令行设置
        E2E_ENV=sit python run.py
        
        # CLI 参数设置（run.py 内部会设置 E2E_ENV）
        python run.py --env sit
    """
    env = _env_str("E2E_ENV", DEFAULT_ENV).lower().strip()
    if env not in SUPPORTED_ENVS:
        raise ValueError(
            f"unsupported E2E_ENV={env!r}; expected one of {SUPPORTED_ENVS}"
        )
    return env


@dataclass(frozen=True)
class User:
    """一个测试用户的数据模型。
    
    为什么用 dataclass：
    - 自动生成 __init__ / __repr__ / __eq__ 等方法
    - frozen=True：不可变对象，防止测试过程中意外修改用户信息
    - 类型注解：IDE 自动补全，运行时类型检查
    
    字段说明：
    - username/password：登录凭据
    - role：角色（admin/analyst/viewer/embed），用于权限测试和用户池分配
    - label：可选标识，便于调试时区分用户
    - extra：扩展字段，存放额外信息（如用户 ID、部门等）
    
    示例：
        User(username="admin", password="admin", role="admin", label="default")
    """

    username: str
    password: str
    role: str               # admin / analyst / viewer / embed
    label: str = ""         # 可选标识，便于定位
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupersetInstance:
    """一个 Superset 实例的连接信息。
    
    为什么需要这个模型：
    - 支持多版本并行测试（4.1 和 6.0）
    - 每个实例有独立的 base_url 和容器配置
    - is_v6 属性便于判断版本，用于分支逻辑
    
    字段说明：
    - name：实例名称（"4.1" / "6.0"），用于标识和参数化
    - version：完整版本号（"4.1.1" / "6.0.0"），用于报告和日志
    - base_url：访问地址，测试时使用
    - compose_dir：docker compose 目录，冷启动时使用
    - postgres_container/redis_container：容器名称，用于健康检查和统计
    
    示例：
        SupersetInstance(
            name="6.0",
            version="6.0.0",
            base_url="http://localhost:18089",
            compose_dir=Path("../superset-6.0"),
            postgres_container="superset-6.0-postgres",
            redis_container="superset-6.0-redis",
        )
    """

    name: str            # "4.1" / "6.0"
    version: str         # "4.1.1" / "6.0.0"
    base_url: str        # http://localhost:18088
    compose_dir: Path    # ../superset-4.1
    postgres_container: str
    redis_container: str | None

    @property
    def is_v6(self) -> bool:
        """判断是否为 6.0 版本（用于分支逻辑）。
        
        为什么用 name 而不是 version 判断：
        - name 格式固定（"4.1" / "6.0"），version 可能有小版本号（"6.0.1"）
        - 简单直接，避免版本号解析错误
        """
        return self.name.startswith("6")


@dataclass(frozen=True)
class TestConfig:
    """全局测试配置的数据模型。
    
    为什么用 dataclass + frozen=True：
    - dataclass：自动生成构造函数和常用方法，代码简洁
    - frozen=True：配置一旦加载就不可修改，避免运行时意外变更
    - 类型注解：IDE 自动补全，静态检查工具（如 mypy）可以发现类型错误
    
    配置字段分类：
    1. 环境相关：env, mode, cleanup_on_exit
    2. 凭据相关：admin_username, admin_password
    3. 浏览器相关：browser, headless
    4. 超时相关：page_timeout_ms, navigation_timeout_ms
    5. 重试相关：reruns, reruns_delay
    6. 路径相关：reports_dir, screenshots_dir, allure_results_dir
    7. 实例相关：instances（Superset 4.1/6.0）
    8. 用户池：user_pool（按角色分组的用户列表）
    9. 性能测试：perf（透传配置）
    """

    # 激活的环境（dev/sit/uat/prod）
    env: str = DEFAULT_ENV
    # 模式: cold=冷启动(先down再up); reuse=复用现有服务(默认)
    mode: str = "reuse"
    # 是否在测试结束后清理冷启动的服务（生产环境建议关闭）
    cleanup_on_exit: bool = True
    # admin 凭据（兼容旧调用方式）
    admin_username: str = "admin"
    admin_password: str = "admin"
    # 浏览器类型
    browser: str = "chromium"  # chromium | firefox | webkit
    # 是否无头模式（CI 用 headless，本地调试用 headed）
    headless: bool = True
    # 页面操作超时（毫秒）
    page_timeout_ms: int = 30000
    # 页面导航超时（毫秒）
    navigation_timeout_ms: int = 60000
    # 失败重试次数
    reruns: int = 2
    # 重试间隔（秒）
    reruns_delay: int = 3
    # 报告根目录
    reports_dir: Path = field(default_factory=lambda: _REPO_ROOT / "e2e" / "reports")
    # Superset 实例列表（4.1 和 6.0）
    instances: tuple[SupersetInstance, ...] = field(default_factory=tuple)
    # 多用户池：role -> tuple[User, ...]
    user_pool: dict[str, tuple[User, ...]] = field(default_factory=dict)
    # 性能测试段（透传配置，不做解析）
    perf: dict[str, Any] = field(default_factory=dict)

    @property
    def screenshots_dir(self) -> Path:
        """失败截图存放目录（自动创建）。"""
        return self.reports_dir / "screenshots"

    @property
    def allure_results_dir(self) -> Path:
        """Allure 报告原始数据目录。"""
        return self.reports_dir / "allure-results"

    # ------------------------------------------------------------------ #
    # 角色/用户 helpers                                                   #
    # ------------------------------------------------------------------ #

    def users_for_role(self, role: str) -> tuple[User, ...]:
        """返回某角色下的所有用户。
        
        为什么返回 tuple 而不是 list：
        - tuple 是不可变的，防止外部修改用户池
        - 用户池在配置加载时确定，运行时不应变更
        
        示例：
            users = CONFIG.users_for_role("viewer")
            for user in users:
                print(user.username)
        """
        return self.user_pool.get(role, ())

    def has_role(self, role: str) -> bool:
        """检查某角色是否有配置用户。"""
        return bool(self.users_for_role(role))


def _load_env_config(env: str) -> dict:
    """加载配置文件：base config.yaml + env 覆盖。
    
    为什么这样设计（分层配置）：
    - base config.yaml：存放所有环境共用的配置（DRY 原则）
    - config.<env>.yaml：只存放当前环境的差异配置
    - 深度合并：嵌套的 dict 也会合并，不是简单覆盖
    
    加载流程：
    1. 加载 config.yaml（base）
    2. 如果不是 DEFAULT_ENV（dev），加载 config.<env>.yaml
    3. 深度合并：env 配置覆盖 base 配置
    
    示例：
        config.yaml:          config.sit.yaml:
        user_pool:              user_pool:
          viewer:                 viewer:
            - v1/pass               - v1/pass
            - v2/pass               - v2/pass
                                    - v3/pass
                                    - v4/pass
        → 合并后 viewer 有 4 个用户
    
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
