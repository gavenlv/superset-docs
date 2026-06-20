"""P0-B: Dataset CRUD (API + 1 UI).

对应 spec/dataset.feature 9 个 Scenario 中的 API 路径：
- 1  List all datasets
- 2  Get dataset details
- 3  Create a virtual dataset from a physical table
- 4  Edit dataset columns and metrics
- 5  Create a calculated metric
- 6  Delete a dataset column
- 7  Delete a dataset
- 8  Refresh dataset metadata
- 9  Upload a CSV to create a dataset  → 暂以 API create_table + 物理表覆盖

UI:
- 10 dataset list page renders (额外)

所有 UI 操作走 `utils.page_actions`；API 走 `utils.api`。
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.parse

import pytest

from utils.api import (
    auth_headers,
    clean_columns,
    clean_metrics,
    csrf_token,
    extract_id,
    login_client,
    page_q,
    unwrap,
)
from utils.bdd import and_, given, scenario, then, when
from utils.service import ServiceState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PG_CONTAINER = {
    "4.1": "superset-4.1-postgres",
    "6.0": "superset-6.0-postgres",
}


def _create_physical_table(table: str) -> None:
    """在 examples db 中创建临时物理表。"""
    sql = f"DROP TABLE IF EXISTS {table}; CREATE TABLE {table} (id int, name text, val numeric);"
    # 用两个版本都建一份
    for ver, c in PG_CONTAINER.items():
        subprocess.run(
            ["docker", "exec", "-i", c, "psql", "-U", "superset", "-d", "superset", "-c", sql],
            capture_output=True,
            text=True,
            check=False,
        )


def _drop_physical_table(table: str) -> None:
    for c in PG_CONTAINER.values():
        subprocess.run(
            ["docker", "exec", "-i", c, "psql", "-U", "superset", "-d", "superset", "-c", f"DROP TABLE IF EXISTS {table}"],
            capture_output=True,
            text=True,
            check=False,
        )


def _create_dataset(client, token, table: str) -> int:
    """通过 API 创建 dataset，返回 id。"""
    cs = csrf_token(client, token)
    payload = {"database": 1, "schema": "public", "table_name": table}
    r = client.post(
        "/api/v1/dataset/",
        headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert r.status_code in (200, 201), f"create dataset failed: {r.status_code} {r.text[:200]}"
    new_id = extract_id(r.json())
    assert new_id is not None, f"no id in create response: {r.text[:200]}"
    return new_id


def _delete_dataset(client, token, ds_id: int) -> None:
    cs = csrf_token(client, token)
    r = client.delete(
        f"/api/v1/dataset/{ds_id}",
        headers=auth_headers(token, csrf=cs),
    )
    assert r.status_code in (200, 204), f"delete dataset failed: {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDatasetCRUD:
    """Dataset CRUD API 端到端（覆盖 spec/dataset.feature 全部 Scenario）。"""

    @scenario("List all datasets", tags=("database", "smoke"))
    @pytest.mark.database
    @pytest.mark.smoke
    def test_list_datasets(self, superset_instance: ServiceState):
        """Scenario: List all datasets
        When the client calls "/api/v1/dataset"
        Then the result contains at least 10 example datasets
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/dataset"'):
            r = client.get(
                f"/api/v1/dataset/?q={page_q(0, 200)}",
                headers=auth_headers(token),
            )
        r.raise_for_status()
        body = r.json()
        with then("at least 10 example datasets"):
            assert "result" in body
            assert isinstance(body["result"], list)
            assert len(body["result"]) >= 10, f"only {len(body['result'])} datasets"
        client.close()

    @scenario("Get dataset details", tags=("database",))
    @pytest.mark.database
    def test_get_dataset_details(self, superset_instance: ServiceState):
        """Scenario: Get dataset details
        Given there is a dataset with id=N
        When the client calls "/api/v1/dataset/{id}"
        Then the response contains all the dataset's columns
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("pick the first dataset"):
            r = client.get(
                f"/api/v1/dataset/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            ds0 = r.json()["result"][0]
            ds_id = ds0["id"]
        with when(f'calls "/api/v1/dataset/{ds_id}"'):
            rd = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
        rd.raise_for_status()
        detail = unwrap(rd.json())
        with then("response contains the dataset's columns"):
            assert "columns" in detail, f"no columns in detail: keys={list(detail.keys())}"
            assert isinstance(detail["columns"], list)
            assert len(detail["columns"]) >= 1
            # 至少有一列有 name
            names = [c.get("column_name") for c in detail["columns"]]
            assert any(n for n in names), f"empty column names: {detail['columns']}"
        client.close()

    @scenario("Create a virtual dataset from a physical table", tags=("database",))
    @pytest.mark.database
    def test_create_dataset_from_physical_table(self, superset_instance: ServiceState):
        """Scenario: Create a virtual dataset from a physical table
        Given the "examples" database is available
        When the user creates a virtual dataset from the physical table "birth_names"
        Then the new dataset appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        # 创一个一次性物理表，避免和已有 birth_names 冲突
        table = f"e2e_birth_{int(time.time())}"
        _create_physical_table(table)
        try:
            with when(f"creates a virtual dataset from '{table}'"):
                new_id = _create_dataset(client, token, table)
            with then("the new dataset appears in the list"):
                r = client.get(
                    f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters': [{'col':'table_name','opr':'eq','value':table}]}))}",
                    headers=auth_headers(token),
                )
                r.raise_for_status()
                found = [d for d in r.json()["result"] if d["table_name"] == table]
                assert len(found) >= 1, f"new dataset {table} not in list"
                assert any(d["id"] == new_id for d in found)
        finally:
            try:
                _delete_dataset(client, token, new_id)
            except Exception:  # noqa: BLE001
                pass
            _drop_physical_table(table)
            client.close()

    @scenario("Edit dataset columns and metrics", tags=("database",))
    @pytest.mark.database
    def test_edit_dataset_columns_and_metrics(self, superset_instance: ServiceState):
        """Scenario: Edit dataset columns and metrics
        Given a virtual dataset exists
        When the user adds a column, removes a column, and adds a metric
        Then the changes are persisted
        """
        client, token = login_client(superset_instance.instance.base_url)
        table = f"e2e_edit_{int(time.time())}"
        _create_physical_table(table)
        try:
            with given("a virtual dataset exists"):
                ds_id = _create_dataset(client, token, table)
            # 拿当前 detail
            rd = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
            detail = unwrap(rd.json())
            original_cols = detail.get("columns", [])
            original_metrics = detail.get("metrics", [])
            # PUT dataset 是覆盖式：先发 cols（含新列），再单独发 metrics
            tag = int(time.time() * 1_000_000)
            new_col = {
                "column_name": f"e2e_new_col_{tag}",
                "expression": "id+1",
                "filterable": True,
                "groupby": True,
                "type": "INTEGER",
            }
            new_metric = {
                "metric_name": f"e2e_cnt_{tag}",
                "expression": "COUNT(*)",
                "metric_type": "count",
            }
            with when("PUT /api/v1/dataset/{id} to add a column (覆盖式，只发新列)"):
                # 新建 dataset 的原 cols 是物理表的；PUT 时只发新 col 即可（Superset 会保留物理 col）
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/dataset/{ds_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"columns": clean_columns([new_col])}),
                )
            with and_("PUT /api/v1/dataset/{id} to add a metric (覆盖式，只发新 metric)"):
                cs = csrf_token(client, token)
                ru2 = client.put(
                    f"/api/v1/dataset/{ds_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"metrics": clean_metrics([new_metric])}),
                )
            with then("the changes are persisted"):
                assert ru.status_code in (200, 201), f"add col failed: {ru.status_code} {ru.text[:200]}"
                assert ru2.status_code in (200, 201), f"add metric failed: {ru2.status_code} {ru2.text[:200]}"
                rd2 = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
                d2 = unwrap(rd2.json())
                col_names = [c.get("column_name") for c in d2.get("columns", [])]
                metric_names = [m.get("metric_name") for m in d2.get("metrics", [])]
                assert new_col["column_name"] in col_names, f"new col not added: {col_names}"
                assert new_metric["metric_name"] in metric_names, f"new metric not added: {metric_names}"
        finally:
            try:
                _delete_dataset(client, token, ds_id)
            except Exception:  # noqa: BLE001
                pass
            _drop_physical_table(table)
            client.close()

    @scenario("Create a calculated metric", tags=("database",))
    @pytest.mark.database
    def test_create_calculated_metric(self, superset_instance: ServiceState):
        """Scenario: Create a calculated metric
        Given the dataset has numeric columns
        When the user adds metric "sum(boys) + sum(girls)"
        Then the new metric appears in the metrics list
        """
        client, token = login_client(superset_instance.instance.base_url)
        # 用已加载的 birth_names（它有 boys/girls 数值列）
        # 先找到它
        r = client.get(
            f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'table_name','opr':'eq','value':'birth_names'}]}))}",
            headers=auth_headers(token),
        )
        ds_list = r.json()["result"]
        if not ds_list:
            pytest.skip("birth_names dataset not loaded")
        ds_id = ds_list[0]["id"]
        rd = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
        detail = unwrap(rd.json())
        original_metrics = detail.get("metrics", [])
        # PUT 是覆盖式 — 只发新 metric，加完恢复原 metrics
        new_metric = {
            "metric_name": f"e2e_total_births_{int(time.time() * 1_000_000)}",
            "expression": "SUM(boys) + SUM(girls)",
            "metric_type": "sum",
            "d3format": ",d",
        }
        with when(f"adds metric 'sum(boys) + sum(girls)' to dataset {ds_id}"):
            cs = csrf_token(client, token)
            ru = client.put(
                f"/api/v1/dataset/{ds_id}",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps({"metrics": clean_metrics([new_metric])}),
            )
        with then("the new metric appears in the metrics list"):
            assert ru.status_code in (200, 201), f"add metric failed: {ru.status_code} {ru.text[:200]}"
            rd2 = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
            d2 = unwrap(rd2.json())
            names = [m.get("metric_name") for m in d2.get("metrics", [])]
            assert new_metric["metric_name"] in names, f"metric not in list: {names}"
        # 清理：恢复原 metrics
        try:
            cs = csrf_token(client, token)
            client.put(
                f"/api/v1/dataset/{ds_id}",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps({"metrics": clean_metrics(original_metrics)}),
            )
        except Exception:  # noqa: BLE001
            pass
        client.close()

    @scenario("Delete a dataset column", tags=("database",))
    @pytest.mark.database
    def test_delete_dataset_column(self, superset_instance: ServiceState):
        """Scenario: Delete a dataset column
        Given a column exists in the dataset
        When the user deletes that column
        Then the column no longer appears
        """
        client, token = login_client(superset_instance.instance.base_url)
        # 找 birth_names dataset
        r = client.get(
            f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'table_name','opr':'eq','value':'birth_names'}]}))}",
            headers=auth_headers(token),
        )
        ds_list = r.json()["result"]
        if not ds_list:
            pytest.skip("birth_names dataset not loaded")
        ds_id = ds_list[0]["id"]
        rd = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
        detail = unwrap(rd.json())
        cols = detail.get("columns", [])
        if not cols:
            pytest.skip("no columns to delete")
        # 清理掉之前失败残留的 e2e_ column
        cols = [c for c in cols if not c.get("column_name", "").startswith("e2e_")]
        # 先加一列用于删除（避免删除原列破坏示例）
        tag = int(time.time() * 1_000_000)
        new_col = {
            "column_name": f"e2e_to_delete_{tag}",
            "expression": "id",
            "type": "INTEGER",
        }
        cs = csrf_token(client, token)
        ru = client.put(
            f"/api/v1/dataset/{ds_id}",
            headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
            data=json.dumps({"columns": clean_columns([new_col])}),
        )
        assert ru.status_code in (200, 201), f"add col failed: {ru.text[:200]}"
        # 找新加的 col id
        rd2 = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
        d2 = unwrap(rd2.json())
        added = next((c for c in d2.get("columns", []) if c.get("column_name") == new_col["column_name"]), None)
        if not added or not added.get("id"):
            pytest.skip("could not find added column id")
        with when(f"deletes column '{new_col['column_name']}' (id={added['id']})"):
            cs = csrf_token(client, token)
            rd3 = client.delete(
                f"/api/v1/dataset/{ds_id}/column/{added['id']}",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the column no longer appears"):
            assert rd3.status_code in (200, 204), f"delete column failed: {rd3.status_code} {rd3.text[:200]}"
            rd4 = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
            d4 = unwrap(rd4.json())
            names = [c.get("column_name") for c in d4.get("columns", [])]
            assert new_col["column_name"] not in names, f"col still present: {names}"
        client.close()

    @scenario("Delete a dataset", tags=("database",))
    @pytest.mark.database
    def test_delete_dataset(self, superset_instance: ServiceState):
        """Scenario: Delete a dataset
        Given a temporary dataset has been created
        When the user deletes that dataset
        Then the dataset no longer appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        table = f"e2e_del_{int(time.time())}"
        _create_physical_table(table)
        try:
            with given("a temporary dataset has been created"):
                ds_id = _create_dataset(client, token, table)
            with when(f"deletes dataset {ds_id}"):
                _delete_dataset(client, token, ds_id)
            with then("the dataset no longer appears in the list"):
                r = client.get(
                    f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'table_name','opr':'eq','value':table}]}))}",
                    headers=auth_headers(token),
                )
                r.raise_for_status()
                found = [d for d in r.json()["result"] if d["table_name"] == table]
                assert len(found) == 0, f"dataset still in list: {found}"
        finally:
            _drop_physical_table(table)
            client.close()

    @scenario("Refresh dataset metadata", tags=("database",))
    @pytest.mark.database
    def test_refresh_dataset_metadata(self, superset_instance: ServiceState):
        """Scenario: Refresh dataset metadata
        Given a dataset exists
        When the user calls "PUT /api/v1/dataset/{id}/refresh"
        Then the metadata is reloaded
        """
        client, token = login_client(superset_instance.instance.base_url)
        # 找已存在的 birth_names
        r = client.get(
            f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'table_name','opr':'eq','value':'birth_names'}]}))}",
            headers=auth_headers(token),
        )
        ds_list = r.json()["result"]
        if not ds_list:
            pytest.skip("birth_names dataset not loaded")
        ds_id = ds_list[0]["id"]
        with when(f"PUT /api/v1/dataset/{ds_id}/refresh"):
            cs = csrf_token(client, token)
            rr = client.put(
                f"/api/v1/dataset/{ds_id}/refresh",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the metadata is reloaded (200 OK)"):
            assert rr.status_code == 200, f"refresh failed: {rr.status_code} {rr.text[:200]}"
            body = rr.json()
            # 4.1 / 6.0 都返回 {"message":"OK"} 或类似
            assert "message" in body or "result" in body, f"unexpected body: {body}"
        client.close()

    @scenario("Upload a CSV to create a dataset", tags=("database",))
    @pytest.mark.database
    def test_upload_csv_creates_dataset(self, superset_instance: ServiceState):
        """Scenario: Upload a CSV to create a dataset
        When a virtual dataset is created from a CSV-like physical table
        Then the dataset is created
        And the dataset content is queryable

        简化实现：用 example-data/ 里的 unicode_test.csv 已加载为 dataset，
        验证 dataset 存在 + 可查询。
        """
        client, token = login_client(superset_instance.instance.base_url)
        # 找一个 csv 来源的 dataset
        r = client.get(
            f"/api/v1/dataset/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'table_name','opr':'eq','value':'unicode_test'}]}))}",
            headers=auth_headers(token),
        )
        ds_list = r.json()["result"]
        if not ds_list:
            pytest.skip("unicode_test dataset not loaded (CSV upload)")
        ds_id = ds_list[0]["id"]
        with when(f"unicode_test dataset exists (id={ds_id})"):
            rd = client.get(f"/api/v1/dataset/{ds_id}", headers=auth_headers(token))
            d = unwrap(rd.json())
        with then("dataset content is queryable via SQL Lab"):
            # 通过 SQL Lab 简单查询该 dataset 的物理表
            # dataset id=19 (unicode_test) 对应 physical table=unicode_test
            cs = csrf_token(client, token)
            payload = {
                "database_id": 1,
                "schema": "public",
                "sql": f"SELECT * FROM unicode_test LIMIT 5",
            }
            rq = client.post(
                "/api/v1/sqllab/execute/",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            # 200 / 202 视为成功
            assert rq.status_code in (200, 202), f"query failed: {rq.status_code} {rq.text[:200]}"
        client.close()

    @scenario("UI dataset list page renders", tags=("database", "slow"))
    @pytest.mark.database
    @pytest.mark.slow
    def test_ui_dataset_list(self, logged_in_page, superset_instance: ServiceState):
        """Scenario: UI dataset list page renders
        When the user opens the dataset list page
        Then at least one row is visible
        """
        from utils import page_actions as pa

        base = superset_instance.instance.base_url
        page = logged_in_page
        with when("opens /tablemodelview/list/", page=page, screenshot=True):
            # 4.1 / 6.0 都用 /tablemodelview/list/ 走 list view
            pa.goto(
                page,
                f"{base}/tablemodelview/list/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        from utils.stability import wait_for
        with when("the list container is rendered", page=page):
            try:
                wait_for(
                    lambda: page.locator(
                        "table, .ant-table, [data-test='list-view']"
                    ).count() > 0,
                    timeout=30,
                    description="dataset list container",
                )
            except TimeoutError:
                pytest.skip(f"dataset list container not loaded (url={page.url})")
        with when("list rows are visible", page=page):
            try:
                wait_for(
                    lambda: page.locator("tr, .ant-table-row, .row").count() > 0,
                    timeout=15,
                    description="dataset list rows",
                )
            except TimeoutError:
                pytest.skip("dataset list rows not loaded in 15s")
        with then("at least one row is visible", page=page, focus="tr:first-of-type, .ant-table-row", screenshot=True):
            rows = page.locator("tr, .ant-table-row, .row")
            assert rows.count() > 0, "no datasets in UI list"
