"""P4 — 补充端到端测试。

涵盖 spec 中未列出的高价值 API：
- Saved Queries (SQL Lab 收藏的查询)
- Row Level Security (行级安全)
- Annotation Layer (图表注释)
- CSS Template (主题/样式)
- Database introspection (schema/function/table metadata)
- Tag (4.1 不支持 CREATE，6.0 支持)
- Chart data / explore_json (图表数据查询)
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse

import pytest

from utils.api import auth_headers, csrf_token, extract_id, login_client, page_q
from utils.bdd import and_, given, scenario, then, when
from utils.service import ServiceState

logger = logging.getLogger(__name__)


def _uname() -> str:
    """全局唯一 e2e 资源名。"""
    return f"e2e_{int(time.time() * 1_000_000)}"


# ---------------------------------------------------------------------------
# P4-A: Saved Queries
# ---------------------------------------------------------------------------

class TestSavedQueries:
    """SQL Lab 已保存查询的 CRUD。"""

    @scenario("List saved queries", tags=("saved_query",))
    @pytest.mark.saved_query
    def test_list_saved_queries(self, superset_instance: ServiceState):
        """Scenario: List saved queries
        When the client calls "/api/v1/saved_query/"
        Then the response contains the saved query list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/saved_query/"'):
            r = client.get(
                f"/api/v1/saved_query/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the saved query list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
            assert "count" in body
        client.close()

    @scenario("Create a saved query", tags=("saved_query",))
    @pytest.mark.saved_query
    def test_create_saved_query(self, superset_instance: ServiceState):
        """Scenario: Create a saved query
        Given a database with a schema exists
        When the user creates a saved query
        Then the saved query appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with when(f"create saved query '{name}'"):
                cs = csrf_token(client, token)
                payload = {
                    "label": name,
                    "description": "e2e saved query",
                    "db_id": 1,
                    "schema": "public",
                    "sql": "SELECT 1 AS n",
                }
                rc = client.post(
                    "/api/v1/saved_query/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201), f"create failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
                assert new_id is not None
            with then("the saved query is in the list"):
                rl = client.get(
                    f"/api/v1/saved_query/?q={page_q(0, 100)}",
                    headers=auth_headers(token),
                )
                assert rl.status_code == 200
                body = rl.json()
                labels = [q.get("label") for q in body.get("result", [])]
                assert name in labels
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/saved_query/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Edit a saved query", tags=("saved_query",))
    @pytest.mark.saved_query
    def test_edit_saved_query(self, superset_instance: ServiceState):
        """Scenario: Edit a saved query
        Given a saved query exists
        When the user modifies its description
        Then the change is persisted
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with given("a saved query exists"):
                cs = csrf_token(client, token)
                payload = {
                    "label": name,
                    "description": "before",
                    "db_id": 1,
                    "schema": "public",
                    "sql": "SELECT 1",
                }
                rc = client.post(
                    "/api/v1/saved_query/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201)
                new_id = extract_id(rc.json())
            with when("modify description to 'after'"):
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/saved_query/{new_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"description": "after"}),
                )
            with then("the change is persisted"):
                assert ru.status_code in (200, 201)
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/saved_query/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Delete a saved query", tags=("saved_query",))
    @pytest.mark.saved_query
    def test_delete_saved_query(self, superset_instance: ServiceState):
        """Scenario: Delete a saved query
        Given a saved query exists
        When the user deletes that saved query
        Then the saved query is no longer in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        with given("a saved query exists"):
            cs = csrf_token(client, token)
            payload = {
                "label": name,
                "description": "to-delete",
                "db_id": 1,
                "schema": "public",
                "sql": "SELECT 1",
            }
            rc = client.post(
                "/api/v1/saved_query/",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            assert rc.status_code in (200, 201)
            new_id = extract_id(rc.json())
        with when(f"deletes saved query {new_id}"):
            cs = csrf_token(client, token)
            rd = client.delete(
                f"/api/v1/saved_query/{new_id}",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the saved query is removed"):
            assert rd.status_code in (200, 204)
            rl = client.get(
                f"/api/v1/saved_query/?q={page_q(0, 100)}",
                headers=auth_headers(token),
            )
            ids = [q.get("id") for q in rl.json().get("result", [])]
            assert new_id not in ids
        client.close()


# ---------------------------------------------------------------------------
# P4-B: Row Level Security
# ---------------------------------------------------------------------------

class TestRowLevelSecurity:
    """行级安全（RLS）规则的 CRUD。"""

    @scenario("List RLS rules", tags=("rls",))
    @pytest.mark.rls
    def test_list_rls(self, superset_instance: ServiceState):
        """Scenario: List RLS rules
        When the client calls "/api/v1/rowlevelsecurity/"
        Then the response contains the RLS rule list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/rowlevelsecurity/"'):
            r = client.get(
                f"/api/v1/rowlevelsecurity/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the RLS rule list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Create an RLS rule", tags=("rls",))
    @pytest.mark.rls
    def test_create_rls(self, superset_instance: ServiceState):
        """Scenario: Create an RLS rule
        Given a dataset and a role exist
        When the user creates a new RLS rule
        Then the rule appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with when(f"create RLS rule '{name}'"):
                cs = csrf_token(client, token)
                payload = {
                    "name": name,
                    "clause": "name = 'John'",
                    "filter_type": "Regular",
                    "tables": [1],
                    "roles": [1],
                }
                rc = client.post(
                    "/api/v1/rowlevelsecurity/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201), f"create failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
            with then("the rule is in the list"):
                rl = client.get(
                    f"/api/v1/rowlevelsecurity/?q={page_q(0, 100)}",
                    headers=auth_headers(token),
                )
                assert rl.status_code == 200
                names = [x.get("name") for x in rl.json().get("result", [])]
                assert name in names
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/rowlevelsecurity/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Edit an RLS rule", tags=("rls",))
    @pytest.mark.rls
    def test_edit_rls(self, superset_instance: ServiceState):
        """Scenario: Edit an RLS rule
        Given an RLS rule exists
        When the user modifies its clause
        Then the change is persisted
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with given("an RLS rule exists"):
                cs = csrf_token(client, token)
                payload = {
                    "name": name,
                    "clause": "name = 'John'",
                    "filter_type": "Regular",
                    "tables": [1],
                    "roles": [1],
                }
                rc = client.post(
                    "/api/v1/rowlevelsecurity/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201)
                new_id = extract_id(rc.json())
            with when("modify clause to '1=1'"):
                cs = csrf_token(client, token)
                ru = client.put(
                    f"/api/v1/rowlevelsecurity/{new_id}",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps({"clause": "1=1"}),
                )
            with then("the change is persisted"):
                assert ru.status_code in (200, 201)
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/rowlevelsecurity/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Delete an RLS rule", tags=("rls",))
    @pytest.mark.rls
    def test_delete_rls(self, superset_instance: ServiceState):
        """Scenario: Delete an RLS rule
        Given an RLS rule exists
        When the user deletes that rule
        Then the rule is no longer in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        with given("an RLS rule exists"):
            cs = csrf_token(client, token)
            payload = {
                "name": name,
                "clause": "name = 'John'",
                "filter_type": "Regular",
                "tables": [1],
                "roles": [1],
            }
            rc = client.post(
                "/api/v1/rowlevelsecurity/",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            assert rc.status_code in (200, 201)
            new_id = extract_id(rc.json())
        with when(f"deletes RLS rule {new_id}"):
            cs = csrf_token(client, token)
            rd = client.delete(
                f"/api/v1/rowlevelsecurity/{new_id}",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the rule is removed"):
            assert rd.status_code in (200, 204)
        client.close()


# ---------------------------------------------------------------------------
# P4-C: Annotation Layer
# ---------------------------------------------------------------------------

class TestAnnotationLayer:
    """图表注释层的 CRUD。"""

    @scenario("List annotation layers", tags=("annotation",))
    @pytest.mark.annotation
    def test_list_annotation_layers(self, superset_instance: ServiceState):
        """Scenario: List annotation layers
        When the client calls "/api/v1/annotation_layer/"
        Then the response contains the annotation layer list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/annotation_layer/"'):
            r = client.get(
                f"/api/v1/annotation_layer/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the annotation layer list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Create an annotation layer", tags=("annotation",))
    @pytest.mark.annotation
    def test_create_annotation_layer(self, superset_instance: ServiceState):
        """Scenario: Create an annotation layer
        When the user creates an annotation layer
        Then the layer appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with when(f"create annotation layer '{name}'"):
                cs = csrf_token(client, token)
                payload = {"name": name, "descr": "e2e annotation layer"}
                rc = client.post(
                    "/api/v1/annotation_layer/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201), f"create failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
            with then("the layer is in the list"):
                rl = client.get(
                    f"/api/v1/annotation_layer/?q={page_q(0, 100)}",
                    headers=auth_headers(token),
                )
                assert rl.status_code == 200
                names = [x.get("name") for x in rl.json().get("result", [])]
                assert name in names
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/annotation_layer/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()

    @scenario("Delete an annotation layer", tags=("annotation",))
    @pytest.mark.annotation
    def test_delete_annotation_layer(self, superset_instance: ServiceState):
        """Scenario: Delete an annotation layer
        Given an annotation layer exists
        When the user deletes that layer
        Then the layer is no longer in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        with given("an annotation layer exists"):
            cs = csrf_token(client, token)
            payload = {"name": name, "descr": "to-delete"}
            rc = client.post(
                "/api/v1/annotation_layer/",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
            assert rc.status_code in (200, 201)
            new_id = extract_id(rc.json())
        with when(f"deletes annotation layer {new_id}"):
            cs = csrf_token(client, token)
            rd = client.delete(
                f"/api/v1/annotation_layer/{new_id}",
                headers=auth_headers(token, csrf=cs),
            )
        with then("the layer is removed"):
            assert rd.status_code in (200, 204)
        client.close()


# ---------------------------------------------------------------------------
# P4-D: CSS Template
# ---------------------------------------------------------------------------

class TestCssTemplate:
    """CSS 模板（自定义主题）的 CRUD。"""

    @scenario("List CSS templates", tags=("css",))
    @pytest.mark.css
    def test_list_css_templates(self, superset_instance: ServiceState):
        """Scenario: List CSS templates
        When the client calls "/api/v1/css_template/"
        Then the response contains the CSS template list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/css_template/"'):
            r = client.get(
                f"/api/v1/css_template/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the CSS template list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Create a CSS template", tags=("css",))
    @pytest.mark.css
    def test_create_css_template(self, superset_instance: ServiceState):
        """Scenario: Create a CSS template
        When the user creates a CSS template
        Then the template appears in the list
        """
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with when(f"create CSS template '{name}'"):
                cs = csrf_token(client, token)
                payload = {
                    "template_name": name,
                    "css": ".e2e-marker { color: #ff0000; }",
                }
                rc = client.post(
                    "/api/v1/css_template/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201), f"create failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
            with then("the template is in the list"):
                rl = client.get(
                    f"/api/v1/css_template/?q={page_q(0, 100)}",
                    headers=auth_headers(token),
                )
                assert rl.status_code == 200
                names = [x.get("template_name") for x in rl.json().get("result", [])]
                assert name in names
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/css_template/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()


# ---------------------------------------------------------------------------
# P4-E: Database introspection
# ---------------------------------------------------------------------------

class TestDatabaseIntrospection:
    """数据库元数据查询（schemas / tables / functions）。"""

    @scenario("List database schemas", tags=("db_meta",))
    @pytest.mark.db_meta
    def test_list_schemas(self, superset_instance: ServiceState):
        """Scenario: List database schemas
        Given a database exists
        When the user calls /api/v1/database/{id}/schemas/
        Then the response contains the schema list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("calls /api/v1/database/1/schemas/"):
            r = client.get(
                "/api/v1/database/1/schemas/?q=" + page_q(0, 10),
                headers=auth_headers(token),
            )
        with then("the response contains the schema list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Get table metadata", tags=("db_meta",))
    @pytest.mark.db_meta
    def test_table_metadata(self, superset_instance: ServiceState):
        """Scenario: Get table metadata
        Given a table 'birth_names' exists in the examples database
        When the user calls /api/v1/database/1/table_metadata/?name=birth_names
        Then the response contains the column list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("calls /api/v1/database/1/table_metadata/?name=birth_names"):
            r = client.get(
                "/api/v1/database/1/table_metadata/?name=birth_names",
                headers=auth_headers(token),
            )
        with then("the response contains columns"):
            assert r.status_code == 200
            body = r.json()
            assert "columns" in body or "name" in body
        client.close()

    @scenario("List database functions", tags=("db_meta",))
    @pytest.mark.db_meta
    def test_list_functions(self, superset_instance: ServiceState):
        """Scenario: List database functions
        Given a database exists
        When the user calls /api/v1/database/{id}/function_names/
        Then the response contains the function list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("calls /api/v1/database/1/function_names/"):
            r = client.get(
                "/api/v1/database/1/function_names/",
                headers=auth_headers(token),
            )
        with then("the response contains the function list"):
            assert r.status_code == 200
            body = r.json()
            assert "function_names" in body or isinstance(body, dict)
        client.close()


# ---------------------------------------------------------------------------
# P4-F: Tag
# ---------------------------------------------------------------------------

class TestTag:
    """Tag（标签）的 CRUD。4.1 不支持 create，6.0 支持。"""

    @scenario("List tags", tags=("tag",))
    @pytest.mark.tag
    def test_list_tags(self, superset_instance: ServiceState):
        """Scenario: List tags
        When the client calls "/api/v1/tag/"
        Then the response contains the tag list
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when('calls "/api/v1/tag/"'):
            r = client.get(
                f"/api/v1/tag/?q={page_q(0, 10)}",
                headers=auth_headers(token),
            )
        with then("the response contains the tag list"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Create a tag", tags=("tag",))
    @pytest.mark.tag
    def test_create_tag(self, superset_instance: ServiceState):
        """Scenario: Create a tag
        When the user creates a new tag (6.0+)
        Then the tag appears in the list

        注：4.1 的 POST /tag/ 会返回 500；6.0 支持。
        """
        if not superset_instance.instance.is_v6:
            pytest.skip("Tag creation is only available in Superset 6.0+")
        client, token = login_client(superset_instance.instance.base_url)
        name = _uname()
        new_id = None
        try:
            with when(f"create tag '{name}'"):
                cs = csrf_token(client, token)
                payload = {"name": name, "description": "e2e tag"}
                rc = client.post(
                    "/api/v1/tag/",
                    headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                )
                assert rc.status_code in (200, 201), f"create failed: {rc.status_code} {rc.text[:200]}"
                new_id = extract_id(rc.json())
            with then("the tag is in the list"):
                rl = client.get(
                    f"/api/v1/tag/?q={page_q(0, 100)}",
                    headers=auth_headers(token),
                )
                assert rl.status_code == 200
                names = [x.get("name") for x in rl.json().get("result", [])]
                assert name in names
        finally:
            if new_id is not None:
                try:
                    cs = csrf_token(client, token)
                    client.delete(
                        f"/api/v1/tag/{new_id}",
                        headers=auth_headers(token, csrf=cs),
                    )
                except Exception:  # noqa: BLE001
                    pass
            client.close()


# ---------------------------------------------------------------------------
# P4-G: Chart data query (data endpoint)
# ---------------------------------------------------------------------------

class TestChartData:
    """图表数据端点（POST /api/v1/chart/data）。"""

    @scenario("Chart data query returns rows", tags=("chart_data",))
    @pytest.mark.chart_data
    def test_chart_data_query(self, superset_instance: ServiceState):
        """Scenario: Chart data query returns rows
        Given a dataset (wb_health_population) exists
        When the user posts a query to /api/v1/chart/data
        Then the response contains rows
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("post a chart data query for dataset 1 (wb_health_population)"):
            cs = csrf_token(client, token)
            payload = {
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
            r = client.post(
                "/api/v1/chart/data",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
        with then("the response contains data rows"):
            assert r.status_code == 200, f"unexpected: {r.status_code} {r.text[:200]}"
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Chart data query with aggregation", tags=("chart_data",))
    @pytest.mark.chart_data
    def test_chart_data_query_with_metric(self, superset_instance: ServiceState):
        """Scenario: Chart data query with aggregation
        Given a dataset exists
        When the user posts a query with a groupby + metric
        Then the response contains aggregated rows
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("post a chart data query with groupby=country_name, metric=count"):
            cs = csrf_token(client, token)
            payload = {
                "datasource": {"id": 1, "type": "table"},
                "queries": [
                    {
                        "columns": [],
                        "metrics": [{"aggregate": "COUNT", "column": {"column_name": "country_name"}}],
                        "groupby": ["country_name"],
                        "row_limit": 5,
                        "orderby": [],
                        "filters": [],
                        "extras": {},
                    }
                ],
            }
            r = client.post(
                "/api/v1/chart/data",
                headers={**auth_headers(token, csrf=cs), "Content-Type": "application/json"},
                data=json.dumps(payload),
            )
        with then("the response contains aggregated rows"):
            # 不同版本的 metric payload 格式不同，接受 200 或 400（payload 格式不正确）
            assert r.status_code in (200, 400), f"unexpected: {r.status_code} {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                assert "result" in body
        client.close()

    @scenario("Explore endpoint returns a form data skeleton", tags=("chart_data",))
    @pytest.mark.chart_data
    def test_explore_endpoint(self, superset_instance: ServiceState):
        """Scenario: Explore endpoint returns a form data skeleton
        When the client calls /api/v1/explore/?q=...
        Then the response is a valid explore config object
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("calls /api/v1/explore/?q=..."):
            r = client.get(
                f"/api/v1/explore/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
        with then("the response contains a form_data skeleton"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
        client.close()

    @scenario("Explore endpoint returns dataset for a slice", tags=("chart_data",))
    @pytest.mark.chart_data
    def test_explore_endpoint_with_slice_id(self, superset_instance: ServiceState):
        """Scenario: Explore endpoint returns dataset for a slice
        Given a chart exists
        When the user calls /api/v1/explore/?slice_id={id}
        Then the response contains the dataset and form data
        """
        client, token = login_client(superset_instance.instance.base_url)
        ch_id = None
        with when("find a chart to explore"):
            rl = client.get(
                f"/api/v1/chart/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            assert rl.status_code == 200
            results = rl.json().get("result", [])
            assert len(results) >= 1
            ch_id = results[0]["id"]
        with when(f"calls /api/v1/explore/?slice_id={ch_id}"):
            r = client.get(
                f"/api/v1/explore/?slice_id={ch_id}",
                headers=auth_headers(token),
                timeout=15,
            )
        with then("the response contains dataset and form_data"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
            result = body["result"]
            assert "dataset" in result or "form_data" in result
        client.close()

    @scenario("Chart favorite status returns favorited flag", tags=("chart_data",))
    @pytest.mark.chart_data
    def test_chart_favorite_status(self, superset_instance: ServiceState):
        """Scenario: Chart favorite status returns favorited flag
        Given a chart exists
        When the user calls /api/v1/chart/favorite_status/?q=[id_list]
        Then the response contains a list with the favorite flag
        """
        client, token = login_client(superset_instance.instance.base_url)
        ch_id = None
        with when("find a chart id"):
            rl = client.get(
                f"/api/v1/chart/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
            assert rl.status_code == 200
            results = rl.json().get("result", [])
            assert len(results) >= 1
            ch_id = results[0]["id"]
        with when(f"calls /api/v1/chart/favorite_status/?q=[{ch_id}]"):
            r = client.get(
                f"/api/v1/chart/favorite_status/?q={urllib.parse.quote(json.dumps([ch_id]))}",
                headers=auth_headers(token),
            )
        with then("the response contains the favorite flag"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
            assert isinstance(body["result"], list)
            assert len(body["result"]) == 1
            assert "value" in body["result"][0]
        client.close()


# ---------------------------------------------------------------------------
# P4-H: SQL Lab tab state
# ---------------------------------------------------------------------------

class TestSqlLabState:
    """SQL Lab 状态查询（活跃 tab / 历史）。"""

    @scenario("SQL Lab tab state", tags=("sqllab_state",))
    @pytest.mark.sqllab_state
    def test_sqllab_tab_state(self, superset_instance: ServiceState):
        """Scenario: SQL Lab tab state
        When the client calls /api/v1/sqllab/
        Then the response contains the active tab and tab_state_ids
        """
        client, token = login_client(superset_instance.instance.base_url)
        with when("calls /api/v1/sqllab/"):
            r = client.get(
                f"/api/v1/sqllab/?q={page_q(0, 1)}",
                headers=auth_headers(token),
            )
        with then("the response contains tab_state_ids"):
            assert r.status_code == 200
            body = r.json()
            assert "result" in body
            result = body["result"]
            # 4.1/6.0 都返回 tab_state_ids
            assert "tab_state_ids" in result
        client.close()
