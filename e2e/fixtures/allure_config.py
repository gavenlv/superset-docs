"""Allure 环境与分类配置。

pytest-allure 自动读取 allure-results 目录。
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import allure
import pytest

from config.settings import CONFIG


@pytest.fixture(scope="session", autouse=True)
def _allure_environment() -> None:
    """写入 Allure environment.properties 与 categories.json。"""
    reports_dir = CONFIG.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    env_file = reports_dir / "allure-results" / "environment.properties"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    instances_str = ", ".join(
        f"{i.name}({i.base_url})" for i in CONFIG.instances
    )
    env_file.write_text(
        f"mode={CONFIG.mode}\n"
        f"browser={CONFIG.browser}\n"
        f"headless={CONFIG.headless}\n"
        f"python={sys.version.split()[0]}\n"
        f"platform={platform.platform()}\n"
        f"instances={instances_str}\n",
        encoding="utf-8",
    )

    # categories.json: 失败分类（CI 仪表盘用）
    cat_file = reports_dir / "allure-results" / "categories.json"
    cat_file.write_text(
        json.dumps(
            [
                {
                    "name": "Superset internal errors",
                    "matchedStatuses": ["failed"],
                    "messageRegex": ".*(query error|sqlalchemy|IntegrityError|NoSuchTable).*",
                },
                {
                    "name": "Network / Mapbox rate limit",
                    "matchedStatuses": ["failed"],
                    "messageRegex": ".*(429|Mapbox|rate.?limit).*",
                },
                {
                    "name": "Service unavailable",
                    "matchedStatuses": ["failed"],
                    "messageRegex": ".*(Connection refused|Timeout|not running).*",
                },
                {"name": "Other failures", "matchedStatuses": ["failed"]},
                {"name": "Broken tests", "matchedStatuses": ["broken"]},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
    """为每个测试添加 Allure label。"""
    if call.when != "call":
        return
    # 根据 fixture 推断版本
    try:
        instance = item.funcargs.get("superset_instance")
        if instance is not None:
            allure.dynamic.label("instance", instance.instance.name)
            allure.dynamic.label("version", instance.instance.version)
    except Exception:  # noqa: BLE001
        pass
    # 添加 marker 标签
    for marker in item.iter_markers():
        allure.dynamic.tag(marker.name)
