"""公共 fixture：服务生命周期、Playwright 浏览器、参数化版本。"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

# 把项目根目录加入 sys.path，使 `config` / `utils` 可被导入
E2E_ROOT = Path(__file__).resolve().parent.parent
if str(E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(E2E_ROOT))

from config.settings import CONFIG, SupersetInstance, TestConfig  # noqa: E402
from utils.logging import setup_logging  # noqa: E402
from utils.service import (  # noqa: E402
    ServiceState,
    cold_start_instance,
    reuse_instance,
    shutdown_instance,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 顶层 fixture: 配置 / 日志
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """暴露全局配置。"""
    return CONFIG


@pytest.fixture(scope="session", autouse=True)
def _setup_logging() -> None:
    """测试启动时初始化日志。"""
    setup_logging(level=os.environ.get("E2E_LOG_LEVEL", "INFO"))


# ---------------------------------------------------------------------------
# 顶层 fixture: 每个 Superset 实例的服务状态
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def instance_4_1() -> Iterator[ServiceState]:
    """Superset 4.1 实例的 ServiceState。"""
    inst = next(i for i in CONFIG.instances if i.name == "4.1")
    if CONFIG.mode == "cold":
        state = cold_start_instance(inst)
        try:
            yield state
        finally:
            if CONFIG.cleanup_on_exit:
                shutdown_instance(inst)
    else:
        state = reuse_instance(inst)
        yield state


@pytest.fixture(scope="session")
def instance_6_0() -> Iterator[ServiceState]:
    """Superset 6.0 实例的 ServiceState。"""
    inst = next(i for i in CONFIG.instances if i.name == "6.0")
    if CONFIG.mode == "cold":
        state = cold_start_instance(inst)
        try:
            yield state
        finally:
            if CONFIG.cleanup_on_exit:
                shutdown_instance(inst)
    else:
        state = reuse_instance(inst)
        yield state


@pytest.fixture(
    scope="session",
    params=["4.1", "6.0"],
    ids=["v4.1", "v6.0"],
)
def superset_instance(
    request: pytest.FixtureRequest,
    instance_4_1: ServiceState,
    instance_6_0: ServiceState,
) -> ServiceState:
    """参数化的 Superset 实例 fixture。

    用法:
        def test_xxx(superset_instance):
            base = superset_instance.instance.base_url
            ...
    """
    return instance_4_1 if request.param == "4.1" else instance_6_0


# ---------------------------------------------------------------------------
# pytest hook: 用参数化 ID 在 Allure 报告中区分版本
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """自动给每个测试加上版本标签。"""
    for item in items:
        # 根据 fixture 名推断版本
        if "superset_instance" in item.fixturenames:
            # 此时还不知道 parametrize 的具体值，靠 Allure 动态标记
            pass
