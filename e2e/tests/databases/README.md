# tests/databases/

数据库与数据集相关测试，覆盖示例数据加载链路。

## 用例

| 测试                                | 标记                | 验证内容                                       |
| ----------------------------------- | ------------------- | ---------------------------------------------- |
| `test_examples_database_exists`     | `database smoke`    | `examples` 数据库在 API 列表中                  |
| `test_examples_database_uri_is_postgres` | `database`     | examples `sqlalchemy_uri` 指向 PostgreSQL（直查 DB） |
| `test_datasets_loaded`              | `database`          | 已加载 ≥10 个 datasets，schema 仅 `None/public` |

## 运行

```bash
python run.py -m database
```

## 关键点

- `test_examples_database_uri_is_postgres` 通过 `docker exec psql` 直接查 `dbs` 表，绕开 API 缓存，验证持久化是否真的写入 PostgreSQL
- `test_datasets_loaded` 校验 `schema` 必须是 `None` 或 `public`，如果出现 `main` 说明 init 脚本的 schema 修复逻辑未生效
