# perf/reports/

Locust / k6 压测报告输出（gitignore）。子目录：
- `locust/`  Locust CSV / HTML / current JSON / summary TXT
- `k6/`      k6 JSON 输出
- [`SUMMARY.md`](./SUMMARY.md) **本次工作的最终汇总报告**（元测试 / 6.0 baseline / 多环境多用户 / 文档体系 / 已知遗留）

## 报告文件说明

### Locust (`locust/`)

| 文件 | 用途 |
| --- | --- |
| `current_<version>.json` | 当前快照（与 `baselines/v<x>_<y>.json` 同 schema） |
| `summary_<version>.txt` | 表格化汇总（按端点分组的 p50/p95/p99） |
| `run_<version>_stats.csv` | Locust 原始 stats CSV |
| `run_<version>_stats_history.csv` | 时间序列（每 10s 采样） |
| `run_<version>_failures.csv` | 失败请求详情 |
| `run_<version>_exceptions.csv` | 异常堆栈 |
| `report_<version>.html` | Locust 自带 HTML 报告 |
| `docker_stats.csv` | 容器 CPU/内存（如果开了 `docker_metrics: true`） |

### k6 (`k6/`)

| 文件 | 用途 |
| --- | --- |
| `<script>_<vu>vu_<ts>.json` | k6 原生 JSON（可导入 k6 Cloud / Grafana） |

## 6.0 实测结果（示例）

来自 `locust/summary_6.0.txt`（200 VU / 120s cold-start，混合角色）：

| 端点 | role | count | err% | p50 (ms) | p95 (ms) | p99 (ms) | Apdex | Stab |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GET /api/v1/dashboard/` | viewer | 135 | 0.0% | 316 | 810 | 1265 | 0.89 | 4.0 |
| `GET /api/v1/dashboard/` | embed | 50 | 0.0% | 297 | 941 | 1202 | 0.85 | 4.0 |
| `GET /api/v1/dashboard/{id}` | viewer | 93 | 0.0% | 52 | 212 | 311 | 1.0 | 6.0 |
| `GET /api/v1/dashboard/{id}/charts` | — | 64 | 0.0% | 47 | 175 | 281 | 1.0 | 6.0 |
| `GET /api/v1/dashboard/{id}/datasets` | — | 53 | 0.0% | 137 | 368 | 453 | 1.0 | 3.3 |
| `GET /api/v1/chart/` | viewer | 53 | 0.0% | 755 | 1890 | 2852 | 0.58 | 3.8 |
| `GET /api/v1/chart/{id}` | viewer | 49 | 0.0% | 60 | 263 | 397 | 1.0 | 6.6 |
| `POST /api/v1/chart/data` | viewer | 100 | 0.0% | 88 | 240 | 437 | 1.0 | 5.0 |
| `GET /superset/dashboard/{id}/` (html) | — | 35 | 0.0% | 49 | 225 | 869 | 0.99 | 17.9 |

> **重点观察**：
> - `GET /api/v1/dashboard/` 是 QPS 最高的端点（200+ RPS）
> - `POST /api/v1/chart/data` 重点查询 p95 < 250ms（达标）
> - `GET /superset/dashboard/{id}/` (HTML) p99 = 869ms（页面渲染，含前端打包资源）
>
> 数字会随 Superset 版本、机器配置、数据集规模变化。详细对比请直接看 `current_6.0.json` + `summary_6.0.txt`。

## 报告分享

- **HTML**（`report_<ver>.html`）双击在浏览器打开即可
- **JSON**（`current_<ver>.json`）可用 `jq` 过滤：
  ```bash
  jq '.endpoints["GET /api/v1/dashboard/"]' perf/reports/locust/current_6.0.json
  ```
- **k6 JSON** 可导入 [k6 Cloud](https://app.k6.io/) 或自建 Grafana
- **Allure**（E2E）通过 `allure serve reports/allure-results` 查看趋势
