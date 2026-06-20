# tests/charts/

单图表相关测试，覆盖图表 API 与 Explore 页面。

## 用例

| 测试                          | 标记                | 验证内容                                       |
| ----------------------------- | ------------------- | ---------------------------------------------- |
| `test_charts_list_api`        | `chart smoke`       | `/api/v1/chart/` 至少返回 1 个图表            |
| `test_charts_query_data_api`  | `chart`             | 至少 1 个图表能通过 `/data/` 端点返回结果      |
| `test_open_one_chart_in_explore` | `chart slow`     | 在 Explore 页打开图表，渲染无 5xx 错误        |

## 运行

```bash
python run.py -m chart
```

## 跨版本说明

- `pivot_table` / `table` / `pivot_table_v2` 在 4.1 与 6.0 查询参数格式略不同，`test_charts_query_data_api` 自动跳过这些类型
- Explore 页在 6.0 是 SPA，首屏渲染需要等待 30-45 秒
- 偶发 Mapbox / 429 错误视为通过（限流已知问题）
