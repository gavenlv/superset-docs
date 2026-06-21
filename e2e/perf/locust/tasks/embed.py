"""Embed 角色：嵌入式访问（dashboard UUID 链接）。"""
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


class EmbedBehavior(BaseBehavior):
    """Embed 行为集合（TaskSet）。"""

    @task(4)
    def list_dashboards_for_embed(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dashboard/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dashboard/  (embed)",
        )

    @task(3)
    def dashboard_detail(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/api/v1/dashboard/{did}",
            name="GET /api/v1/dashboard/{id}  (embed)",
        )

    @task(2)
    def dashboard_html(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "GET",
            f"/superset/dashboard/{did}/",
            name="GET /superset/dashboard/{id}/  (embed html)",
        )

    @task(2)
    def chart_data(self) -> None:
        """Superset 6.0 用 datasource + queries。"""
        self._timed_request(
            "POST",
            "/api/v1/chart/data",
            json=_CHART_DATA_PAYLOAD,
            name="POST /api/v1/chart/data  (embed)",
        )


class EmbedUser(SupersetUser):
    weight = 8
    tasks = [EmbedBehavior]
    wait_time = between(0.5, 2.0)
    role = "embed"
