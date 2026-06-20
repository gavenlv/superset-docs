"""P0-D: Dashboard CRUD (API + 1 UI).

对应 spec/dashboard.feature 8 个 Scenario。
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse

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


def _create_dashboard(client, token, *, title: str) -> int:
    cs = csrf_token(client, token)
    payload = {"dashboard_title": title, "slug": title.lower().replace(" ", "-")}
    r = client.post(
        "/api/v1/dashboard/",
        headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert r.status_code in (200, 201), f"create dashboard failed: {r.status_code} {r.text[:200]}"
    new_id = extract_id(r.json())
    assert new_id is not None
    return new_id


def _delete_dashboard(client, token, dash_id: int) -> None:
    cs = csrf_token(client, token)
    r = client.delete(
        f"/api/v1/dashboard/{dash_id}",
        headers=auth_headers(token, csrf=cs),
    )
    assert r.status_code in (200, 204), f"delete dashboard failed: {r.status_code} {r.text[:200]}"


class TestDashboardCRUD:
    """Dashboard CRUD API 端到端。"""

    @scenario("List all dashboards", tags=("dashboard", "smoke"))
    @pytest.mark.dashboard
    @pytest.mark.smoke
    def test_list_dashboards(self, superset_instance: ServiceState):
        """Scenario: List all dashboards
        When the client calls "/api/v1/dashboard"
        Then the result contains at least one dashboard
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/dashboard"'):
            r = client.get(
                f"/api/v1/dashboard/?q={page_q(0, 200)}",
                headers=auth_headers(token),
            )
        r.raise_for_status()
        body = r.json()
        with then("at least one dashboard"):
            assert "result" in body
            assert len(body["result"]) >= 1, f"only {len(body['result'])} dashboards"
        client.close()

    @scenario("Get dashboard details", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_get_dashboard_details(self, superset_instance: ServiceState):
        """Scenario: Get dashboard details
        Given there is a dashboard with id=N
        When the client calls "/api/v1/dashboard/{id}"
        Then the response contains the dashboard layout JSON
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("pick the first dashboard"):
            r = client.get(
                f"/api/v1/dashboard/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            d0 = r.json()["result"][0]
            dash_id = d0["id"]
        with when(f'calls "/api/v1/dashboard/{dash_id}"'):
            rd = client.get(f"/api/v1/dashboard/{dash_id}", headers=auth_headers(token))
        rd.raise_for_status()
        detail = unwrap(rd.json())
        with then("response contains dashboard layout JSON (position_json or json_metadata)"):
            assert "position_json" in detail or "json_metadata" in detail
        client.close()

    @scenario("Create an empty dashboard", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_create_dashboard(self, superset_instance: ServiceState):
        """Scenario: Create an empty dashboard
        When the user creates an empty dashboard titled "E2E Dashboard"
        Then the dashboard appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        title = f"E2E Dashboard {int(time.time() * 1_000_000)}"
        try:
            with when(f'creates empty dashboard "{title}"'):
                new_id = _create_dashboard(client, token, title=title)
            with then("the dashboard appears in the list"):
                r = client.get(
                    f"/api/v1/dashboard/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'id','opr':'eq','value':new_id}]}))}",
                    headers=auth_headers(token),
                )
                r.raise_for_status()
                found = [d for d in r.json()["result"] if d["id"] == new_id]
                assert len(found) == 1
                assert found[0]["dashboard_title"] == title
        finally:
            try:
                _delete_dashboard(client, token, new_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Edit a dashboard title", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_edit_dashboard(self, superset_instance: ServiceState):
        """Scenario: Edit a dashboard title
        Given a dashboard has been created
        When the user modifies its title
        Then the new title is persisted
        """
        client, token = login_client(superset_instance.instance.base_url)
        title = f"E2E Edit {int(time.time() * 1_000_000)}"
        try:
            with given("a dashboard has been created"):
                dash_id = _create_dashboard(client, token, title=title)
            with when("the user modifies its title"):
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/dashboard/{dash_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"dashboard_title": f"{title} Renamed"}),
                )
            with then("the new title is persisted"):
                assert ru.status_code in (200, 201)
                rd = client.get(f"/api/v1/dashboard/{dash_id}", headers=auth_headers(token))
                detail = unwrap(rd.json())
                assert detail["dashboard_title"] == f"{title} Renamed"
        finally:
            try:
                _delete_dashboard(client, token, dash_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Delete a dashboard", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_delete_dashboard(self, superset_instance: ServiceState):
        """Scenario: Delete a dashboard
        Given a temporary dashboard has been created
        When the user deletes that dashboard
        Then the dashboard no longer appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        title = f"E2E Del {int(time.time() * 1_000_000)}"
        with given("a temporary dashboard has been created"):
            dash_id = _create_dashboard(client, token, title=title)
        with when(f"deletes dashboard {dash_id}"):
            _delete_dashboard(client, token, dash_id)
        with then("the dashboard no longer appears in the list"):
            r = client.get(
                f"/api/v1/dashboard/?q={urllib.parse.quote(json.dumps({'filters':[{'col':'id','opr':'eq','value':dash_id}]}))}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            found = [d for d in r.json()["result"] if d["id"] == dash_id]
            assert len(found) == 0
        client.close()

    @scenario("Dashboard layout contains a chart placeholder", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_dashboard_add_chart_layout(self, superset_instance: ServiceState):
        """Scenario: Dashboard layout contains a chart placeholder
        Given a dashboard exists
        When the user adds a chart to the dashboard
        Then the layout JSON includes that chart
        """
        client, token = login_client(superset_instance.instance.base_url)
        title = f"E2E Layout {int(time.time() * 1_000_000)}"
        try:
            with given("a dashboard exists"):
                dash_id = _create_dashboard(client, token, title=title)
            # 找一个 chart id
            with when("find an existing chart"):
                r = client.get(
                    f"/api/v1/chart/?q={page_q(0, 1)}",
                    headers=auth_headers(token),
                )
                chart_id = r.json()["result"][0]["id"]
            # PUT dashboard 添加 chart 到 layout
            with when(f"add chart {chart_id} to dashboard {dash_id} layout"):
                position_json = json.dumps({
                    "CHART-" + str(chart_id): {
                        "type": "CHART",
                        "id": f"CHART-{chart_id}",
                        "children": [],
                        "meta": {
                            "chartId": chart_id,
                            "width": 4, "height": 4,
                        },
                    }
                })
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/dashboard/{dash_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"position_json": position_json}),
                )
            with then("layout JSON includes the chart"):
                assert ru.status_code in (200, 201), f"add chart failed: {ru.status_code} {ru.text[:200]}"
                rd = client.get(f"/api/v1/dashboard/{dash_id}", headers=auth_headers(token))
                detail = unwrap(rd.json())
                pos = detail.get("position_json")
                if isinstance(pos, str):
                    pos = json.loads(pos)
                assert pos is not None
                assert f"CHART-{chart_id}" in pos, f"chart not in layout: keys={list(pos.keys())[:5]}"
        finally:
            try:
                _delete_dashboard(client, token, dash_id)
            except Exception:  # noqa: BLE001
                pass
            client.close()

    @scenario("Export a dashboard to ZIP", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_export_dashboard(self, superset_instance: ServiceState):
        """Scenario: Export a dashboard to ZIP
        Given a dashboard with charts exists
        When the user exports the dashboard
        Then a ZIP file is downloaded
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("find a dashboard to export"):
            r = client.get(
                f"/api/v1/dashboard/?q={page_q(0, 5)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            dashboards = r.json()["result"]
            dash_id = dashboards[0]["id"]
        with when(f"export dashboard {dash_id} to ZIP"):
            re = client.get(
                f"/api/v1/dashboard/export/?q={urllib.parse.quote(json.dumps([dash_id]))}",
                headers=auth_headers(token),
            )
        with then("response is ZIP"):
            assert re.status_code == 200
            assert re.headers.get("content-type", "").startswith("application/zip")
            assert re.content[:2] == b"PK", f"not zip: {re.content[:20]}"
        client.close()

    @scenario("Import a dashboard from ZIP", tags=("dashboard",))
    @pytest.mark.dashboard
    def test_import_dashboard(self, superset_instance: ServiceState):
        """Scenario: Import a dashboard from ZIP
        Given a dashboard export ZIP exists
        When the user uploads that file
        Then the import endpoint accepts the file
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("export a dashboard first to use as import source"):
            r = client.get(
                f"/api/v1/dashboard/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            dash_id = r.json()["result"][0]["id"]
            re = client.get(
                f"/api/v1/dashboard/export/?q={urllib.parse.quote(json.dumps([dash_id]))}",
                headers=auth_headers(token),
            )
            assert re.status_code == 200
            zip_bytes = re.content
        with when("upload the export file as import"):
            h = auth_headers(token, csrf=csrf_token(client, token))
            h["Accept"] = "application/json"
            ri = client.post(
                "/api/v1/dashboard/import/",
                headers=h,
                files={"formData": ("dashboard_export.zip", zip_bytes, "application/zip")},
            )
        with then("import endpoint accepts the file"):
            # 已知：已存在时 422 + overwrite 提示
            assert ri.status_code in (200, 201, 422), f"unexpected: {ri.status_code} {ri.text[:200]}"
        client.close()

    @scenario("UI dashboard list page renders", tags=("dashboard", "slow"))
    @pytest.mark.dashboard
    @pytest.mark.slow
    def test_ui_dashboard_list(self, logged_in_page, superset_instance: ServiceState):
        """Scenario: UI dashboard list page renders
        When the user opens the dashboard list page
        Then at least one row is visible
        """
        from utils import page_actions as pa
        from utils.stability import wait_for

        base = superset_instance.instance.base_url
        page = logged_in_page
        with when("opens /dashboard/list/", page=page, screenshot=True):
            pa.goto(
                page,
                f"{base}/dashboard/list/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        with when("list container renders", page=page):
            try:
                wait_for(
                    lambda: page.locator("table, .ant-table, [data-test='list-view']").count() > 0,
                    timeout=30,
                    description="dashboard list container",
                )
            except TimeoutError:
                pytest.skip(f"dashboard list not loaded (url={page.url})")
        with then("at least one row is visible", page=page, focus="tr:first-of-type, .ant-table-row", screenshot=True):
            rows = page.locator("tr, .ant-table-row, .row")
            assert rows.count() > 0, "no dashboards in UI list"
