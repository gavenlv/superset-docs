"""
Superset 6.0 example data loader:
- 修复 examples 数据库的 sqlalchemy_uri
- 重新加载示例数据
- 6.0 helpers.py 已支持 SUPERSET_EXAMPLES_BASE_URL

用法：在容器内通过 flask app context 运行
  python /app/pythonpath/load_examples_init.py
"""

import os
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial


EXAMPLES_DB_NAME = "examples"
EXAMPLES_DB_URI = os.environ.get(
    "EXAMPLES_DB_URI",
    "postgresql+psycopg2://superset:superset@postgres:5432/superset",
)
LOCAL_SAMPLES_DIR = os.environ.get("SUPERSET_LOCAL_SAMPLES_DIR")
# 本地 HTTP 服务端口，用于让 marshmallow URL 校验通过
LOCAL_HTTP_PORT = int(os.environ.get("LOCAL_HTTP_PORT", "18099"))


def _start_http_server(directory: str, port: int) -> None:
    """启动一个后台 HTTP 服务来提供本地示例数据文件。

    6.0 的 YAML 配置里 data 字段使用 examples:// 协议，
    normalize_example_data_url 会调用 get_example_url 转成真实 URL，
    然后 marshmallow 的 fields.URL() 会校验（只接受 http/https）。
    所以不能直接用 file:// URL，需要通过 HTTP 服务提供文件。
    """
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    httpd = HTTPServer(("0.0.0.0", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"[http] serving {directory} on port {port}")


def main() -> int:
    # 6.0 中 `from superset import app` 同样是 current_app 的 LocalProxy
    from superset.app import create_app

    app = create_app()

    with app.app_context():
        from superset import db
        from superset.models.core import Database
        from superset.cli.examples import load_examples_run

        # 如果设置了本地目录，启动 HTTP 服务并设置 BASE_URL
        if LOCAL_SAMPLES_DIR:
            _start_http_server(LOCAL_SAMPLES_DIR, LOCAL_HTTP_PORT)
            # 覆盖 helpers 里的 BASE_URL，让 get_example_url 返回本地 HTTP URL
            import superset.examples.helpers as _ex_helpers
            _ex_helpers.BASE_URL = f"http://localhost:{LOCAL_HTTP_PORT}/"
            print(
                f"[patch] superset.examples.helpers.BASE_URL -> "
                f"http://localhost:{LOCAL_HTTP_PORT}/"
            )

        examples_db = (
            db.session.query(Database)
            .filter_by(database_name=EXAMPLES_DB_NAME)
            .one_or_none()
        )
        if examples_db is None:
            print(f"[db] examples database missing, creating")
            examples_db = Database(
                database_name=EXAMPLES_DB_NAME,
                sqlalchemy_uri=EXAMPLES_DB_URI,
                expose_in_sqllab=True,
            )
            db.session.add(examples_db)
            db.session.commit()

        # 强制把 examples database URI 改成本地 postgres
        if examples_db.sqlalchemy_uri != EXAMPLES_DB_URI:
            print(f"[db] update sqlalchemy_uri: {examples_db.sqlalchemy_uri} -> {EXAMPLES_DB_URI}")
            examples_db.sqlalchemy_uri = EXAMPLES_DB_URI
            examples_db.expose_in_sqllab = True
            db.session.commit()
        else:
            print(f"[db] examples sqlalchemy_uri already set: {examples_db.sqlalchemy_uri}")

        # 清理过期的 example 表元数据：
        # 之前如果 examples 库是 sqlite，所有 SqlaTable 的 schema 字段会被写成 "main"
        # （sqlite 默认 schema）。当我们把 URI 切到 postgres 后，物理表会落在
        # "public"，但元数据表里的 schema 仍然是 "main"，导致 fetch_metadata 报错
        # `NoSuchTableError: main.wb_health_population`。
        # 这里强制把所有 examples db 下 schema != 物理默认的 SqlaTable 的 schema
        # 改成物理默认 schema，保证 load_examples_run 的 fetch_metadata 能找到表。
        from superset.connectors.sqla.models import SqlaTable
        from sqlalchemy import inspect

        with examples_db.get_sqla_engine() as engine:
            physical_default_schema = inspect(engine).default_schema_name
        print(f"[db] physical default schema: {physical_default_schema!r}")

        stale = (
            db.session.query(SqlaTable)
            .filter(SqlaTable.database_id == examples_db.id)
            .filter(SqlaTable.schema != physical_default_schema)
            .all()
        )
        if stale:
            print(
                f"[db] fixing {len(stale)} stale example table metadata "
                f"(schema -> {physical_default_schema!r})"
            )
            for t in stale:
                print(f"  - {t.table_name}: {t.schema!r} -> {physical_default_schema!r}")
                t.schema = physical_default_schema
            db.session.commit()
            db.session.expire_all()

        try:
            print("[load] start load_examples_run")
            load_examples_run(
                load_test_data=False,
                load_big_data=False,
                only_metadata=False,
                force=False,
            )
        except Exception as e:  # noqa: BLE001
            import traceback
            print(f"[load] error: {e}", file=sys.stderr)
            traceback.print_exc()
            return 1

        # 修复图表 query_context 中数据源 ID 不匹配的问题：
        # 部分 sales 图表的 query_context 引用了 new_members_daily (id=21)
        # 而非 cleaned_sales_data (id=11)，导致查询时报 "Columns missing"。
        # 这里在加载完成后统一修复所有 datasource_id 与 query_context 不一致的图表。
        from superset.models.slice import Slice
        import json as _json

        mismatched = (
            db.session.query(Slice)
            .filter(Slice.query_context.isnot(None))
            .filter(Slice.query_context != "")
            .all()
        )
        fixed = 0
        for slc in mismatched:
            try:
                qc = _json.loads(slc.query_context)
                ctx_ds_id = qc.get("datasource", {}).get("id")
                if ctx_ds_id is not None and ctx_ds_id != slc.datasource_id:
                    print(
                        f"[fix] chart {slc.id} '{slc.slice_name}': "
                        f"datasource {ctx_ds_id} -> {slc.datasource_id}"
                    )
                    qc["datasource"]["id"] = slc.datasource_id
                    slc.query_context = _json.dumps(qc)
                    fixed += 1
            except Exception:  # noqa: BLE001
                pass
        if fixed:
            db.session.commit()
            print(f"[fix] fixed {fixed} chart datasource ID mismatches")

    print("[done] example data loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
