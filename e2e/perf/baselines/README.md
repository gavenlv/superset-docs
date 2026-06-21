# perf/baselines/

性能基线 JSON（git 跟踪），按 Superset 版本分文件：

| 文件 | 状态 | 说明 |
| --- | --- | --- |
| `v4_1.json` | ⚠️ PLACEHOLDER | 暂为占位（`note` 字段已标注），值取自 [PLAN.md §5.2](file:///d:/workspace/superset-space/superset-docs/e2e/perf/PLAN.md#52-阈值基线草拟cold-启动示例数据下并发提高后) 草拟阈值。**正式基线待 P5-1 在 Superset 4.1 容器上跑 Locust 200 VU / 10 min 后覆盖**。 |
| `v6_0.json` | ✅ 实测 | 2026-06-21 在 6.0 容器上跑 Locust 10 VU / 2 min cold-start，16 端点 0 错误。后续 CI 跑 200 VU / 10 min 会再覆盖一次。 |

## 字段格式

每个端点包含：

```json
{
  "count": 156,           // 总请求数
  "failures": 0,          // 失败次数
  "error_rate_pct": 0.0,  // 失败率百分比
  "p50_ms": 85.6,         // 中位响应时间
  "p95_ms": 245.4,        // 95 分位响应时间（阈值对比用）
  "p99_ms": 419.3,        // 99 分位响应时间
  "apdex": 0.99,          // 用户满意度指数（0~1）
  "stability": 4.97       // p99/p50 比值（越小越稳定）
}
```

`apdex` 和 `stability` 是可选字段（占位基线可不带）。

## 角色变体聚合

Locust 跑时会按角色（viewer / analyst / embed / admin）各产生一个端点变体，例如：

```
GET /api/v1/dashboard/  (viewer)    135 req
GET /api/v1/dashboard/  (analyst)     19 req
GET /api/v1/dashboard/  (embed)       50 req
```

`perf/tools/save_baseline.py` 会按 `method+path` 聚合，**加权平均** p50/p95/p99，合并成单条：

```
GET /api/v1/dashboard/  204 req  p50=313.5ms p95=831.8ms p99=1243.7ms
```

## 覆盖工作流

1. 跑 Locust：`bash perf/tools/run_locust.sh`（默认 6.0）
2. 生成快照：`perf/reports/locust/current_6.0.json`
3. 存为基线：`python perf/tools/save_baseline.py --version 6.0 --current perf/reports/locust/current_6.0.json --note "200 VU / 10 min cold-start"`
4. 写回 `perf/baselines/v6_0.json`，git 提交
5. 下次 PR：`python perf/tools/compare_baseline.py --version 6.0 --current <new> --strict --exit-on-fail` 校验不超阈值

## 跨版本差异

`v4_1.json` 与 `v6_0.json` 在端点路径上略有不同：

- 4.1：`/api/v1/dashboard/{id}/charts/`（带尾斜杠）
- 6.0：`/api/v1/dashboard/{id}/charts`（不带尾斜杠）

`compare_baseline.py` 的 `is_critical_endpoint` 通过模板匹配兼容两者。
