"""
Superset example data loader:
- 修复 examples 数据库的 sqlalchemy_uri
- 重新加载示例数据 (含真实表数据)
- 通过环境变量自定义 example data base URL

用法：在容器内通过 flask app context 运行
  python /app/pythonpath/load_examples_init.py
"""

import os
import sys


WORKING_BASE = os.environ.get(
    "SUPERSET_EXAMPLES_BASE_URL",
    "https://raw.githubusercontent.com/apache-superset/examples-data/master/",
)
LOCAL_SAMPLES_DIR = os.environ.get("SUPERSET_LOCAL_SAMPLES_DIR")
EXAMPLES_DB_NAME = "examples"
EXAMPLES_DB_URI = os.environ.get(
    "EXAMPLES_DB_URI",
    "postgresql+psycopg2://superset:superset@postgres:5432/superset",
)


def main() -> int:
    # 4.1 中 `from superset import app` 返回的是 current_app 的 LocalProxy，
    # 必须在 app context 内才能使用。所以我们自己创建一次。
    from superset.app import create_app

    app = create_app()

    with app.app_context():
        # 4.1 把 BASE_URL 写死在 helpers.py；6.0 会读 env var；两种情况下都强制覆盖一次
        try:
            import superset.examples.helpers as _ex_helpers

            _ex_helpers.BASE_URL = WORKING_BASE
            print(f"[patch] superset.examples.helpers.BASE_URL -> {WORKING_BASE}")

            if LOCAL_SAMPLES_DIR:
                # 把 get_example_url 整个换成读本地文件，避免 ?raw=true 这种
                # GitHub 专用查询串干扰 file:// URL。
                _local_dir = LOCAL_SAMPLES_DIR

                def _local_example_url(filepath: str) -> str:
                    import os as _os
                    return f"file://{_os.path.join(_local_dir, filepath)}"

                _ex_helpers.get_example_url = _local_example_url
                print(
                    f"[patch] superset.examples.helpers.get_example_url -> "
                    f"local dir {_local_dir}"
                )
        except Exception as e:  # noqa: BLE001
            print(f"[patch] skip 4.1 BASE_URL patch: {e}")

        from superset import db
        from superset.models.core import Database

        # 直接用 update/commit 强制把 examples URI 改成 postgres
        # (superset init 默认会创建 sqlite:////app/superset_home/examples.db,
        # 但 init 容器与 web 容器的 superset_home 目录不同, 写入的数据会丢)
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

        print(f"[db] set sqlalchemy_uri = {EXAMPLES_DB_URI}")
        examples_db.sqlalchemy_uri = EXAMPLES_DB_URI
        examples_db.expose_in_sqllab = True
        db.session.commit()

        # 重新查询确认持久化
        db.session.expire_all()
        check = (
            db.session.query(Database)
            .filter_by(database_name=EXAMPLES_DB_NAME)
            .one_or_none()
        )
        print(f"[db] verified sqlalchemy_uri: {check.sqlalchemy_uri if check else 'NONE'}")

        # 清理过期的 example 表元数据：
        # 之前如果 examples 库是 sqlite，所有 SqlaTable 的 schema 字段会被写成 "main"
        # （sqlite 默认 schema）。当我们把 URI 切到 postgres 后，物理表会落在
        # "public"，但元数据表里的 schema 仍然是 "main"，导致 fetch_metadata 报错
        # `NoSuchTableError: main.wb_health_population`。
        # 这里强制把所有 examples db 下 schema != 物理默认的 SqlaTable 的 schema
        # 改成 "public"，保证 load_examples_run 的 fetch_metadata 能找到表。
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

        # import 在 commit 之后, 避免循环依赖
        from superset.cli.examples import load_examples_run

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

    print("[done] example data loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
