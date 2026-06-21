"""Analyst 角色：Explore 编辑、chart 写、SQL Lab、saved_query。"""
from __future__ import annotations

from locust import task, between

from perf.locust.tasks.base import SupersetUser, BaseBehavior


# chart/data payload（Superset 6.0 格式）
_CHART_DATA_PAYLOAD = {
    "datasource": {"id": 1, "type": "table"},
    "queries": [
        {
            "columns": ["country_name"],
            "metrics": [],
            "row_limit": 5,
            "orderby": [],
            "filters": [],
            "extras": {},
        }
    ],
}


class AnalystBehavior(BaseBehavior):
    """Analyst 行为集合（TaskSet）。"""

    # ---- 重点：chart 列表 / 详情（高频读）----
    @task(10)
    def list_charts(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/chart/",
            params={"q": '{"page":0,"page_size":50}'},
            name="GET /api/v1/chart/  (analyst)",
        )

    @task(8)
    def list_dashboards(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dashboard/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dashboard/  (analyst)",
        )

    @task(6)
    def chart_detail(self) -> None:
        cid = self._get_chart_id()
        if not cid:
            return
        self._timed_request(
            "GET",
            f"/api/v1/chart/{cid}",
            name="GET /api/v1/chart/{id}  (analyst)",
        )

    @task(4)
    def dashboard_detail(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/api/v1/dashboard/{did}",
            name="GET /api/v1/dashboard/{id}  (analyst)",
        )

    # ---- 重点：explore 加载 ----
    @task(5)
    def explore(self) -> None:
        cid = self._get_chart_id()
        if not cid:
            return
        self._timed_request(
            "GET",
            f"/api/v1/explore/?slice_id={cid}",
            name="GET /api/v1/explore/?slice_id=",
        )

    @task(3)
    def explore_html(self) -> None:
        cid = self._get_chart_id()
        if not cid:
            return
        self._timed_request(
            "GET",
            f"/explore/?slice_id={cid}",
            name="GET /explore/?slice_id=  (html)",
        )

    # ---- chart_data（最重，权重仍高）----
    @task(8)
    def chart_data(self) -> None:
        """Superset 6.0 用 datasource + queries（不再支持 slice_id）。"""
        self._timed_request(
            "POST",
            "/api/v1/chart/data",
            json=_CHART_DATA_PAYLOAD,
            name="POST /api/v1/chart/data  (analyst)",
        )

    # ---- 普通 ----
    @task(2)
    def sqllab(self) -> None:
        self._timed_request("GET", "/api/v1/sqllab/", name="GET /api/v1/sqllab/")

    @task(1)
    def list_saved_queries(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/saved_query/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/saved_query/",
        )

    @task(1)
    def list_datasets(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dataset/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dataset/  (analyst)",
        )

    @task(1)
    def db_schemas(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/database/1/schemas/",
            name="GET /api/v1/database/1/schemas/",
        )


class AnalystUser(SupersetUser):
    weight = 10
    tasks = [AnalystBehavior]
    wait_time = between(0.5, 2.0)
