"""测试：数据库 / 数据集 E2E。"""
from __future__ import annotations

import json
import logging
import urllib.parse

import httpx
import pytest

from config.settings import CONFIG
from utils.service import ServiceState

logger = logging.getLogger(__name__)


def _get_token(base_url: str) -> str:
    r = httpx.post(
        f"{base_url}/api/v1/security/login",
        json={
            "username": CONFIG.admin_username,
            "password": CONFIG.admin_password,
            "provider": "db",
            "refresh": True,
        },
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _list_dbs(base_url: str) -> list[dict]:
    token = _get_token(base_url)
    q = json.dumps({"page_size": 100})
    r = httpx.get(
        f"{base_url}/api/v1/database/?q={urllib.parse.quote(q)}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["result"]


def _check_db_uri_in_container(container: str) -> str:
    """通过 docker exec 直接查 PostgreSQL 里的 examples URI。

    返回 sqlalchemy_uri 字符串。
    """
    import subprocess

    proc = subprocess.run(
        [
            "docker", "exec", container,
            "psql", "-U", "superset", "-d", "superset", "-tA", "-c",
            "SELECT sqlalchemy_uri FROM dbs WHERE database_name = 'examples' LIMIT 1;",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr}")
    return proc.stdout.strip()


class TestDatabases:
    """数据库 / 数据集相关。"""

    @pytest.mark.database
    @pytest.mark.smoke
    def test_examples_database_exists(self, superset_instance: ServiceState):
        """examples 数据库应存在（API 视角）。"""
        dbs = _list_dbs(superset_instance.instance.base_url)
        names = {d.get("database_name") for d in dbs}
        assert "examples" in names, f"examples db missing in API, have: {names}"

    @pytest.mark.database
    def test_examples_database_uri_is_postgres(
        self, superset_instance: ServiceState
    ):
        """examples 数据库的 URI 应指向 PostgreSQL（通过 DB 直查）。"""
        uri = _check_db_uri_in_container(superset_instance.instance.postgres_container)
        assert "postgresql" in uri, f"examples URI is not postgres: {uri!r}"

    @pytest.mark.database
    def test_datasets_loaded(self, superset_instance: ServiceState):
        """示例数据集应已加载。"""
        token = _get_token(superset_instance.instance.base_url)
        q = json.dumps({"page_size": 200})
        r = httpx.get(
            f"{superset_instance.instance.base_url}/api/v1/dataset/?q={urllib.parse.quote(q)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20.0,
        )
        r.raise_for_status()
        datasets = r.json()["result"]
        assert len(datasets) >= 10, f"expected >=10 datasets, got {len(datasets)}"
        # schema 应都是 public
        schemas = {d.get("schema") for d in datasets}
        # 允许 None 和 public
        assert schemas.issubset({None, "public"}), f"unexpected schemas: {schemas}"
        # 应包含常见示例
        names = {d.get("table_name") for d in datasets}
        common = {"birth_names", "video_game_sales", "cleaned_sales_data"}
        # 至少应包含 1 个常见数据集
        assert names & common, f"no common example dataset found in {names}"

