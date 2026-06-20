"""顶层 conftest：启动日志、Allure 配置，并暴露共享 fixtures。"""
# 让 pytest 发现 fixtures 目录下的所有 conftest
from fixtures.conftest import (  # noqa: F401
    _setup_logging,
    instance_4_1,
    instance_6_0,
    superset_instance,
    test_config,
)
from fixtures.allure_config import _allure_environment  # noqa: F401
from fixtures.playwright_fixtures import (  # noqa: F401
    browser,
    context,
    logged_in_page,
    page,
    playwright,
)
