"""AdminOps 角色：写路径 CRUD（dataset / chart / dashboard / RLS / tag）。"""
from __future__ import annotations

from locust import task, between

from perf.locust.tasks.base import SupersetUser, BaseBehavior


class AdminOpsBehavior(BaseBehavior):
    """AdminOps 行为集合（TaskSet）。"""

    @task(2)
    def list_dashboards(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dashboard/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dashboard/  (admin)",
        )

    @task(1)
    def list_datasets(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/dataset/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/dataset/  (admin)",
        )

    @task(1)
    def list_rls(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/rowlevelsecurity/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/rowlevelsecurity/",
        )

    @task(1)
    def list_css_templates(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/css_template/",
            name="GET /api/v1/css_template/",
        )

    @task(1)
    def copy_dashboard(self) -> None:
        did = self._get_dashboard_id()
        if not did:
            return
        self._timed_request(
            "POST",
            f"/api/v1/dashboard/{did}/copy/",
            name="POST /api/v1/dashboard/{id}/copy/",
        )

    @task(1)
    def list_tags(self) -> None:
        self._timed_request(
            "GET",
            "/api/v1/tag/",
            params={"q": '{"page":0,"page_size":25}'},
            name="GET /api/v1/tag/",
        )


class AdminOpsUser(SupersetUser):
    weight = 1
    tasks = [AdminOpsBehavior]
    wait_time = between(1.0, 3.0)
    role = "admin"
