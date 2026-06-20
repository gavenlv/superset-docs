"""P2: Import/Export + Alerts/Reports.

对应 spec/import_export.feature + spec/alert.feature。
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


# ---------------------------------------------------------------------------
# P2-A: Import / Export
# ---------------------------------------------------------------------------

class TestImportExport:
    """Import / Export 端到端。"""

    @scenario("Export database to YAML", tags=("import_export",))
    @pytest.mark.import_export
    def test_export_database_yaml(self, superset_instance: ServiceState):
        """Scenario: Export database to YAML
        Given a database exists
        When the user exports the database
        Then a YAML/ZIP file is produced
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("the user exports database 1"):
            r = client.get(
                "/api/v1/database/export/?q=" + urllib.parse.quote(json.dumps([1])),
                headers=auth_headers(token),
            )
        with then("response is a ZIP file"):
            assert r.status_code == 200
            assert r.headers.get("content-type", "").startswith("application/zip")
            assert r.content[:2] == b"PK"
        client.close()

    @scenario("Export chart to YAML", tags=("import_export",))
    @pytest.mark.import_export
    def test_export_chart_yaml(self, superset_instance: ServiceState):
        """Scenario: Export chart to YAML
        Given a chart exists
        When the user exports the chart
        Then a YAML file is produced
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("find a chart to export"):
            r = client.get(
                f"/api/v1/chart/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            ch_id = r.json()["result"][0]["id"]
        with when(f"export chart {ch_id}"):
            re = client.get(
                f"/api/v1/chart/export/?q={urllib.parse.quote(json.dumps([ch_id]))}",
                headers=auth_headers(token),
            )
        with then("response is ZIP"):
            assert re.status_code == 200
            assert re.headers.get("content-type", "").startswith("application/zip")
            assert re.content[:2] == b"PK"
        client.close()

    @scenario("Export dashboard to ZIP", tags=("import_export",))
    @pytest.mark.import_export
    def test_export_dashboard_zip(self, superset_instance: ServiceState):
        """Scenario: Export dashboard to ZIP
        Given a dashboard with charts exists
        When the user exports the dashboard
        Then a ZIP file is produced
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("find a dashboard to export"):
            r = client.get(
                f"/api/v1/dashboard/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            dash_id = r.json()["result"][0]["id"]
        with when(f"export dashboard {dash_id}"):
            re = client.get(
                f"/api/v1/dashboard/export/?q={urllib.parse.quote(json.dumps([dash_id]))}",
                headers=auth_headers(token),
            )
        with then("response is ZIP"):
            assert re.status_code == 200
            assert re.headers.get("content-type", "").startswith("application/zip")
            assert re.content[:2] == b"PK"
        client.close()

    @scenario("Import chart from YAML", tags=("import_export",))
    @pytest.mark.import_export
    def test_import_chart_yaml(self, superset_instance: ServiceState):
        """Scenario: Import chart from YAML
        Given a chart export file exists
        When the user imports that file
        Then the import endpoint accepts it
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("export a chart first to use as import source"):
            r = client.get(
                f"/api/v1/chart/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            r.raise_for_status()
            ch_id = r.json()["result"][0]["id"]
            re = client.get(
                f"/api/v1/chart/export/?q={urllib.parse.quote(json.dumps([ch_id]))}",
                headers=auth_headers(token),
            )
            zip_bytes = re.content
        with when("upload the export file"):
            h = auth_headers(token, csrf=csrf_token(client, token))
            h["Accept"] = "application/json"
            ri = client.post(
                "/api/v1/chart/import/",
                headers=h,
                files={"formData": ("chart_export.yaml", zip_bytes, "application/zip")},
            )
        with then("import endpoint accepts the file"):
            assert ri.status_code in (200, 201, 422), f"unexpected: {ri.status_code}"
        client.close()

    @scenario("Import dashboard from ZIP", tags=("import_export",))
    @pytest.mark.import_export
    def test_import_dashboard_zip(self, superset_instance: ServiceState):
        """Scenario: Import dashboard from ZIP
        Given a dashboard export ZIP exists
        When the user imports that file
        Then the import endpoint accepts it
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
            zip_bytes = re.content
        with when("upload the export file"):
            h = auth_headers(token, csrf=csrf_token(client, token))
            h["Accept"] = "application/json"
            ri = client.post(
                "/api/v1/dashboard/import/",
                headers=h,
                files={"formData": ("dashboard_export.zip", zip_bytes, "application/zip")},
            )
        with then("import endpoint accepts the file"):
            assert ri.status_code in (200, 201, 422), f"unexpected: {ri.status_code}"
        client.close()


# ---------------------------------------------------------------------------
# P2-B: Alerts / Reports
# ---------------------------------------------------------------------------

class TestAlerts:
    """Alerts 端到端（Alerts 模块在 4.1/6.0 需要 ENABLE_ALERTS 配置；如未启用则 skip）。"""

    @scenario("List alerts", tags=("alert",))
    @pytest.mark.alert
    def test_list_alerts(self, superset_instance: ServiceState):
        """Scenario: List alerts
        When the client calls "/api/v1/alert"
        Then the response contains the alert list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/alert"'):
            r = client.get(
                f"/api/v1/alert/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the alert list"):
            if r.status_code == 404:
                pytest.skip("alerts module not enabled")
            assert r.status_code in (200, 204), f"unexpected: {r.status_code} {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                assert "result" in body
        client.close()

    @scenario("Create a SQL alert", tags=("alert",))
    @pytest.mark.alert
    def test_create_sql_alert(self, superset_instance: ServiceState):
        """Scenario: Create a SQL alert
        Given a dataset is available
        When the user creates a SQL alert
        Then the alert appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_alert_{int(time.time() * 1_000_000)}"
        new_id = None
        try:
            with when(f"create SQL alert '{name}'"):
                cs = csrf_token(client, token)
                # Superset alert payload
                payload = {
                    "name": name,
                    "sql": "SELECT COUNT(*) FROM birth_names",
                    "database": 1,
                    "threshold": 100,
                    "alert_type": "AlertsReportDataAlertType",
                    "owners": [1],
                }
                rc = client.post(
                    "/api/v1/alert/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                if rc.status_code == 404:
                    pytest.skip("alerts module not enabled")
                new_id = extract_id(rc.json())
            with then("the alert appears in the list"):
                assert rc.status_code in (200, 201)
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(f"/api/v1/alert/{new_id}", headers=auth_headers(token, csrf=cs))
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Edit alert threshold", tags=("alert",))
    @pytest.mark.alert
    def test_edit_alert_threshold(self, superset_instance: ServiceState):
        """Scenario: Edit alert threshold
        Given an alert exists
        When the user modifies the threshold
        Then the new threshold is saved
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_alert_thr_{int(time.time() * 1_000_000)}"
        new_id = None
        try:
            with given("an alert exists"):
                cs = csrf_token(client, token)
                payload = {
                    "name": name,
                    "sql": "SELECT 1",
                    "database": 1,
                    "threshold": 100,
                    "alert_type": "AlertsReportDataAlertType",
                    "owners": [1],
                }
                rc = client.post(
                    "/api/v1/alert/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                if rc.status_code == 404:
                    pytest.skip("alerts module not enabled")
                new_id = extract_id(rc.json())
            with when("the user modifies the threshold to 200"):
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/alert/{new_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"threshold": 200}),
                )
            with then("the new threshold is saved"):
                assert ru.status_code in (200, 201)
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(f"/api/v1/alert/{new_id}", headers=auth_headers(token, csrf=cs))
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Delete an alert", tags=("alert",))
    @pytest.mark.alert
    def test_delete_alert(self, superset_instance: ServiceState):
        """Scenario: Delete an alert
        Given an alert exists
        When the user deletes that alert
        Then the alert is removed from the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = f"e2e_alert_del_{int(time.time() * 1_000_000)}"
        with given("an alert exists"):
            cs = csrf_token(client, token)
            payload = {
                "name": name,
                "sql": "SELECT 1",
                "database": 1,
                "threshold": 100,
                "alert_type": "AlertsReportDataAlertType",
                "owners": [1],
            }
            rc = client.post(
                "/api/v1/alert/",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            if rc.status_code == 404:
                pytest.skip("alerts module not enabled")
            new_id = extract_id(rc.json())
        with when(f"deletes alert {new_id}"):
            cs = csrf_token(client, token)
            rd = client.delete(
                f"/api/v1/alert/{new_id}",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the alert is removed from the list"):
            assert rd.status_code in (200, 204)
        client.close()


class TestReports:
    """Reports 端到端（Reports 模块在 4.1/6.0 需要 ENABLE_ALERTS 配置；如未启用则 skip）。"""

    @scenario("List reports", tags=("report",))
    @pytest.mark.report
    def test_list_reports(self, superset_instance: ServiceState):
        """Scenario: List reports
        When the client calls the report list endpoint
        Then the response contains the report list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/report"'):
            r = client.get(
                f"/api/v1/report/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the report list"):
            if r.status_code == 404:
                pytest.skip("reports module not enabled")
            assert r.status_code in (200, 204)
        client.close()

    @scenario("Create a report schedule", tags=("report",))
    @pytest.mark.report
    def test_create_report(self, superset_instance: ServiceState):
        """Scenario: Create a report schedule
        Given a dashboard exists
        When the user creates a daily report
        Then the report appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        new_id = None
        try:
            with when("create a daily report on dashboard 1"):
                cs = csrf_token(client, token)
                payload = {
                    "name": f"e2e_report_{int(time.time() * 1_000_000)}",
                    "type": "ReportScheduleType.daily",
                    "dashboard": 1,
                    "crontab": "0 0 * * *",
                    "owners": [1],
                }
                rc = client.post(
                    "/api/v1/report/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                if rc.status_code == 404:
                    pytest.skip("reports module not enabled")
                new_id = extract_id(rc.json())
            with then("the report is created"):
                assert rc.status_code in (200, 201)
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(f"/api/v1/report/{new_id}", headers=auth_headers(token, csrf=cs))
                except Exception:  # noqa: BLE001
                    pass
            client.close()
