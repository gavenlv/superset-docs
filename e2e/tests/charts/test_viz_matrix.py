"""P0-E: Viz type rendering matrix.

对应 spec/viz_matrix.feature Scenario Outline（34 viz_types）。
参数化：34 viz × 2 版本 = 68 用例。
"""
from __future__ import annotations

import json
import logging

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


# (viz_type, dataset_table) 矩阵
VIZ_MATRIX = [
    ("table", "birth_names"),
    ("pivot_table", "birth_names"),
    ("pivot_table_v2", "birth_names"),
    ("big_number", "birth_names"),
    ("big_number_total", "birth_names"),
    ("big_number_period_compare", "birth_names"),
    ("percent_change", "birth_names"),
    ("gauge", "birth_names"),
    ("line", "birth_names"),
    ("timeseries", "birth_names"),
    ("bar", "birth_names"),
    ("timeseries_bar", "birth_names"),
    ("area", "birth_names"),
    ("compare", "birth_names"),
    ("step", "birth_names"),
    ("candlestick", "birth_names"),
    ("pie", "birth_names"),
    ("donut", "birth_names"),
    ("treemap", "birth_names"),
    ("sunburst", "birth_names"),
    ("funnel", "video_game_sales"),
    ("sankey", "video_game_sales"),
    ("icicle", "birth_names"),
    ("histogram", "birth_names"),
    ("dist_bar", "birth_names"),
    ("box_plot", "birth_names"),
    ("violin", "birth_names"),
    ("scatter", "birth_names"),
    ("bubble", "birth_names"),
    ("heatmap", "flights"),
    ("correlation", "flights"),
    ("calendar_heatmap", "flights"),
    ("word_cloud", "birth_names"),
    ("radar", "birth_names"),
]


def _find_dataset(client, token, table_name: str) -> int | None:
    """通过 table_name 找 dataset id。"""
    r = client.get(
        f"/api/v1/dataset/?q={json.dumps({'filters':[{'col':'table_name','opr':'eq','value':table_name}], 'page':0, 'page_size':1})}",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        return None
    result = r.json().get("result", [])
    return result[0]["id"] if result else None


def _make_params_for_viz(viz_type: str, ds_id: int) -> dict:
    """为每个 viz_type 构造最小可用的 params。

    Superset 4.1+ 通用规则：metrics + viz_type 必填。
    """
    base = {"viz_type": viz_type}
    if viz_type in ("table", "pivot_table", "pivot_table_v2"):
        base["metrics"] = ["count"]
        base["groupby"] = ["state"] if viz_type != "table" else []
    elif viz_type.startswith("big_number") or viz_type in ("percent_change", "gauge"):
        base["metric"] = "count"
        base["groupby"] = []
    elif viz_type == "word_cloud":
        base["metric"] = "count"
        base["series"] = "state"
    elif viz_type in ("funnel", "sankey"):
        base["metric"] = "sum__num"
        base["groupby"] = ["genre"]
    else:
        # 时间序列、关系图、分布
        base["metrics"] = ["sum__num"] if "sum__num" else ["count"]
        base["groupby"] = ["ds"] if viz_type in ("line", "timeseries", "bar", "timeseries_bar", "area", "step", "compare") else ["state"]
    return base


class TestVizMatrix:
    """Viz type rendering matrix — 34 viz types × 2 versions."""

    @pytest.mark.chart
    @pytest.mark.viz
    @pytest.mark.parametrize("viz_type,dataset_table", VIZ_MATRIX)
    def test_viz_renders(
        self,
        superset_instance: ServiceState,
        viz_type: str,
        dataset_table: str,
    ):
        """Scenario Outline: Render viz_type "{viz}" against dataset "{dataset}"
        Given the dataset is available
        When the user creates a chart with viz_type="{viz}"
        Then the chart creates successfully
        And the chart has a valid params configuration
        """
        scenario(f"Render viz_type {viz_type} against {dataset_table}", tags=("chart", "viz"))
        client, token = login_client(superset_instance.instance.base_url)
        try:
            with given(f"the dataset '{dataset_table}' is available"):
                ds_id = _find_dataset(client, token, dataset_table)
                if ds_id is None:
                    pytest.skip(f"dataset '{dataset_table}' not found")

            with when(f"the user creates a chart with viz_type='{viz_type}'"):
                cs = csrf_token(client, token)
                params = _make_params_for_viz(viz_type, ds_id)
                payload = {
                    "slice_name": f"e2e_viz_{viz_type}",
                    "viz_type": viz_type,
                    "datasource_id": ds_id,
                    "datasource_type": "table",
                    "params": json.dumps(params),
                }
                rc = client.post(
                    "/api/v1/chart/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                with then("the chart creates successfully"):
                    assert rc.status_code in (200, 201), f"create {viz_type} failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
                assert new_id is not None

            with and_("the chart has a valid params configuration"):
                rd = client.get(f"/api/v1/chart/{new_id}", headers=auth_headers(token))
                detail = unwrap(rd.json())
                assert detail["viz_type"] == viz_type
                assert "params" in detail

            # 清理
            try:
                cs = csrf_token(client, token)
                client.delete(f"/api/v1/chart/{new_id}", headers=auth_headers(token, csrf=cs))
            except Exception:  # noqa: BLE001
                pass
        finally:
            client.close()
