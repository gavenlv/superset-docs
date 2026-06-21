"""Viewer 角色：**重点** dashboard / chart 读路径。"""
from __future__ import annotations

import json

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


class ViewerBehavior(BaseBehavior):
    """Viewer 行为集合（TaskSet）：业务用户读路径。"""

    # ---- 重点：dashboard 列表（最高频）----
    @task(20)
    def list_dashboards(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dashboard/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dashboard/  (viewer)",
        )

    @task(10)
    def list_charts(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/chart/",
            params={"q": '{"page":0,"page_size":50}'},
            name="GET /api/v1/chart/  (viewer)",
        )

    @task(15)
    def dashboard_detail(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/api/v1/dashboard/{did}",
            name="GET /api/v1/dashboard/{id}  (viewer)",
        )

    @task(10)
    def dashboard_charts(self) -> None:
        """6.0: /api/v1/dashboard/{id}/charts （无尾斜杠）。"""
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/api/v1/dashboard/{did}/charts",
            name="GET /api/v1/dashboard/{id}/charts",
        )

    @task(8)
    def dashboard_datasets(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/api/v1/dashboard/{did}/datasets",
            name="GET /api/v1/dashboard/{id}/datasets",
        )

    @task(6)
    def dashboard_html(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/superset/dashboard/{did}/",
            name="GET /superset/dashboard/{id}/  (html)",
        )

    # ---- 重点：chart_data（最重）----
    @task(15)
    def chart_data(self) -> None:
        """Superset 6.0 用 datasource + queries（不再支持 slice_id）。"""
        self._timed_request(
            "POST",
            "/api/v1/chart/data",
            json=_CHART_DATA_PAYLOAD,
            name="POST /api/v1/chart/data  (viewer)",
        )

    @task(6)
    def chart_detail(self) -> None:
        cid = self._get_chart_id()
        if not cid:
            return
        self._timed_request(
            "GET",
            f"/api/v1/chart/{cid}",
            name="GET /api/v1/chart/{id}  (viewer)",
        )

    # ---- 周边 ----
    @task(1)
    def favorite_status(self) -> None:
        ids = getattr(self.user, "_chart_ids", []) or []
        if not ids:
            return
        picked = ids[: min(5, len(ids))]
        # 6.0 格式：q=[1,2,3] (rison)
        self._timed_request(
            "GET",
            "/api/v1/chart/favorite_status/",
            params={"q": json.dumps(picked)},
            name="GET /api/v1/chart/favorite_status/",
        )

    @task(1)
    def welcome(self) -> None:
        self._timed_request("GET", "/superset/welcome/", name="GET /superset/welcome/")


class ViewerUser(SupersetUser):
    weight = 30
    tasks = [ViewerBehavior]
    wait_time = between(0.3, 1.5)  # Viewer 节奏更密集
