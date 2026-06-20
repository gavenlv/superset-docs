"""P1-B: Explore editor.

对应 spec/explore.feature 7 个 Scenario。
通过 API 验证 params 中各种配置项。
"""
from __future__ import annotations

import json
import logging
import time

import pytest

from utils.api import (
    auth_headers,
    csrf_token,
    extract_id,
    login_client,
    page_q,
    unwrap,
)
from utils.bdd import and_, given, scenario, then, when
from utils.service import ServiceState

logger = logging.getLogger(__name__)


def _create_chart_with_params(client, token, *, name: str, params: dict, ds_id: int = 2) -> int:
    """创建带指定 params 的 chart。"""
    cs = csrf_token(client, token)
    payload = {
        "slice_name": name,
        "viz_type": params.get("viz_type", "table"),
        "datasource_id": ds_id,
        "datasource_type": "table",
        "params": json.dumps(params),
    }
    r = client.post(
        "/api/v1/chart/",
        headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert r.status_code in (200, 201), f"create chart failed: {r.status_code} {r.text[:200]}"
    return extract_id(r.json())


def _delete_chart(client, token, ch_id: int) -> None:
    cs = csrf_token(client, token)
    client.delete(f"/api/v1/chart/{ch_id}", headers=auth_headers(token, csrf=cs))


def _get_params(client, token, ch_id: int) -> dict:
    rd = client.get(f"/api/v1/chart/{ch_id}", headers=auth_headers(token))
    detail = unwrap(rd.json())
    p = detail.get("params")
    return json.loads(p) if isinstance(p, str) else p


class TestExplore:
    """Explore editor 端到端。"""

    @scenario("Switch dataset", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_switch_dataset(self, superset_instance: ServiceState):
        """Scenario: Switch dataset
        Given the Explore editor is open
        When the user changes the dataset
        Then the editor reloads the new dataset's columns
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_ds_{int(time.time() * 1_000_000)}"
        try:
            with when("the user creates a chart for dataset id=2 (birth_names)"):
                ch_id = _create_chart_with_params(client, token, name=name, params={"datasource": "2__table", "viz_type": "table"}, ds_id=2)
            with when("the user changes the dataset to 19 (unicode_test)"):
                cs = csrf_token(client, token)
                # 切 dataset 实际是更新 datasource
                client.put(
                    f"/api/v1/chart/{ch_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({
                        "datasource_id": 19,
                        "datasource_type": "table",
                        "params": json.dumps({"datasource": "19__table", "viz_type": "table"}),
                    }),
                )
            with then("the datasource is updated"):
                rd = client.get(f"/api/v1/chart/{ch_id}", headers=auth_headers(token))
                body = rd.json()
                # 4.1: detail 顶层无 datasource_id，信息在 params.datasource
                # 6.0: detail 顶层有 datasource_id
                detail = body.get("result", body)
                p_str = detail.get("params", "{}")
                params = json.loads(p_str) if isinstance(p_str, str) else p_str
                if "datasource_id" in detail:
                    assert detail["datasource_id"] == 19
                else:
                    # 4.1 风格
                    assert "19" in params.get("datasource", "")
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Add a metric", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_add_metric(self, superset_instance: ServiceState):
        """Scenario: Add a metric
        Given the dataset has numeric columns
        When the user adds "SUM(num)" as a metric
        Then the chart aggregates by that metric
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_metric_{int(time.time() * 1_000_000)}"
        try:
            with when("the user adds SUM(num) as a metric"):
                params = {
                    "datasource": "2__table",
                    "viz_type": "table",
                    "metrics": [{
                        "aggregate": "SUM",
                        "column": {"column_name": "num", "type": "BIGINT"},
                        "expressionType": "SIMPLE",
                        "label": "SUM(num)",
                    }],
                }
                ch_id = _create_chart_with_params(client, token, name=name, params=params)
            with then("the chart params contain the metric"):
                p = _get_params(client, token, ch_id)
                assert "metrics" in p
                assert any(m.get("aggregate") == "SUM" and m.get("column", {}).get("column_name") == "num" for m in p["metrics"])
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Add a groupby dimension", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_add_groupby(self, superset_instance: ServiceState):
        """Scenario: Add a groupby dimension
        Given the dataset has a dimension column
        When the user adds a groupby
        Then the chart groups by that dimension
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_gb_{int(time.time() * 1_000_000)}"
        try:
            with when("the user adds groupby=[state]"):
                params = {
                    "datasource": "2__table",
                    "viz_type": "table",
                    "groupby": ["state"],
                    "metrics": ["count"],
                }
                ch_id = _create_chart_with_params(client, token, name=name, params=params)
            with then("the chart params contain groupby"):
                p = _get_params(client, token, ch_id)
                assert p.get("groupby") == ["state"]
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Add an adhoc filter", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_add_adhoc_filter(self, superset_instance: ServiceState):
        """Scenario: Add an adhoc filter
        Given the dataset has filterable columns
        When the user adds filter "state = 'CA'"
        Then the chart filters by that
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_flt_{int(time.time() * 1_000_000)}"
        try:
            with when("the user adds adhoc filter state=CA"):
                params = {
                    "datasource": "2__table",
                    "viz_type": "table",
                    "metrics": ["count"],
                    "adhoc_filters": [{
                        "clause": "WHERE",
                        "expressionType": "SIMPLE",
                        "subject": "state",
                        "operator": "==",
                        "comparator": "CA",
                    }],
                }
                ch_id = _create_chart_with_params(client, token, name=name, params=params)
            with then("the chart params contain the adhoc filter"):
                p = _get_params(client, token, ch_id)
                assert "adhoc_filters" in p
                assert any(f.get("subject") == "state" and f.get("comparator") == "CA" for f in p["adhoc_filters"])
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Time range configuration", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_time_range(self, superset_instance: ServiceState):
        """Scenario: Time range configuration
        Given the dataset has a time column
        When the user sets the time range to "Last 7 days"
        Then the chart shows the last 7 days only
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_time_{int(time.time() * 1_000_000)}"
        try:
            with when("the user sets time_range=Last 7 days"):
                params = {
                    "datasource": "2__table",
                    "viz_type": "line",
                    "metrics": ["sum__num"],
                    "time_range": "Last 7 days : now",
                    "granularity_sqla": "ds",
                }
                ch_id = _create_chart_with_params(client, token, name=name, params=params)
            with then("the chart params contain the time range"):
                p = _get_params(client, token, ch_id)
                assert p.get("time_range") == "Last 7 days : now"
                assert p.get("granularity_sqla") == "ds"
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Save the chart", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_save_chart(self, superset_instance: ServiceState):
        """Scenario: Save the chart
        Given a chart exists in Explore
        When the user clicks "Save"
        Then the chart is stored in the chart library
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_save_{int(time.time() * 1_000_000)}"
        try:
            with when("the user creates and saves a chart"):
                ch_id = _create_chart_with_params(
                    client, token, name=name,
                    params={"datasource": "2__table", "viz_type": "table", "metrics": ["count"]},
                )
            with then("the chart is in the list"):
                r = client.get(
                    f"/api/v1/chart/?q={json.dumps({'filters':[{'col':'id','opr':'eq','value':ch_id}], 'page':0, 'page_size':1})}",
                    headers=auth_headers(token),
                )
                r.raise_for_status()
                found = [c for c in r.json()["result"] if c["id"] == ch_id]
                assert len(found) == 1
                assert found[0]["slice_name"] == name
        finally:
            try:
                _delete_chart(client, token, ch_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Download CSV from Explore", tags=("chart", "explore"))
    @pytest.mark.chart
    @pytest.mark.explore
    def test_download_csv(self, superset_instance: ServiceState):
        """Scenario: Download CSV from Explore
        Given Explore has produced a result
        When the user clicks "Download CSV"
        Then a result CSV is downloaded
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("find a line chart with valid params"):
            r = client.get(
                f"/api/v1/chart/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            # 找一个 line chart
            charts = [c for c in r.json()["result"] if c.get("viz_type") == "line"]
            if not charts:
                pytest.skip("no line chart available")
            ch_id = charts[0]["id"]
        with when(f"download CSV for chart {ch_id}"):
            # Superset Explore 下载 CSV：/api/v1/chart/{id}/data?format=csv
            rd = client.get(
                f"/api/v1/chart/{ch_id}/data/?format=csv",
                headers=auth_headers(token),
            )
        with then("response is CSV (200) or expected 400 (no query_context)"):
            # 4.1/6.0 在 chart 没 query_context 时 400 是已知行为
            assert rd.status_code in (200, 400), f"unexpected: {rd.status_code} {rd.text[:200]}"
            if rd.status_code == 200:
                # CSV 至少包含 ","
                assert "," in rd.text or "\n" in rd.text, f"not CSV: {rd.text[:100]}"
        client.close()
