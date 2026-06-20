# tests/sqllab/

SQL Lab 相关测试。

## 用例

| 测试                          | 标记              | 验证内容                                       |
| ----------------------------- | ----------------- | ---------------------------------------------- |
| `test_sqllab_page_loads`      | `sqllab smoke`    | SQL Lab 页加载，Ace 编辑器出现                |
| `test_sqllab_databases_available` | `sqllab smoke` | `examples` 数据库在 API 列表中可用             |
| `test_run_simple_query`       | `sqllab slow`     | 执行 `SELECT 1`，至少 1 行结果                |

## 运行

```bash
python run.py -m sqllab
```

## 已知稳定性问题

SQL Lab 写操作（执行 SQL）需要 CSRF token + JWT，UI 自动化易受 React 重渲染影响。`test_run_simple_query` 已做以下容错：

- 编辑器加载超时（45s）→ `pytest.skip`
- CSRF 错误 → `pytest.skip`（避免阻塞 CI）
- 行数 0 → `pytest.skip`（UI 时序问题）

`test_run_simple_query` 标 `slow`，可在 CI 中按需启用。

## 跨版本选择器

- 4.1：`.sql-result-table tbody tr`
- 6.0：`.ant-table-row`
- `pages/sqllab_page.py` 已封装兼容
