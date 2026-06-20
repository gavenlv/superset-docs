# BDD Spec & Test Mapping

> BDD 风格的测试规范，对应 `../COVERAGE.md` 中的用例。
> 业务/产品/QA 阅读 `*.feature`；工程师从 `.feature` 标题找对应 pytest 实现。

## 文件清单

| Feature 文件 | 标记 | 用例数 | pytest 模块 |
| --- | --- | --- | --- |
| [auth.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/auth.feature) | @auth | 7 | `tests/auth/test_auth.py`, `tests/health/test_health.py` |
| [database.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/database.feature) | @database | 8 | `tests/databases/test_database_crud.py` |
| [dataset.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/dataset.feature) | @dataset | 9 | `tests/databases/test_dataset_crud.py` |
| [chart.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/chart.feature) | @chart | 8 | `tests/charts/test_chart_crud.py` |
| [dashboard.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/dashboard.feature) | @dashboard | 9 | `tests/dashboards/test_dashboard_crud.py` |
| [viz_matrix.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/viz_matrix.feature) | @viz | 34 | `tests/charts/test_viz_matrix.py` |
| [filter.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/filter.feature) | @filter | 10 | `tests/dashboards/test_filters.py` |
| [sqllab.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/sqllab.feature) | @sqllab | 8 | `tests/sqllab/test_sqllab_adv.py` |
| [explore.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/explore.feature) | @explore | 7 | `tests/charts/test_explore.py` |
| [import_export.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/import_export.feature) | @import_export | 5 | `tests/databases/test_import_export.py` |
| [alert.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/alert.feature) | @alert / @report | 6 | `tests/alerts/test_alerts.py`, `tests/alerts/test_reports.py` |
| [rbac.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/rbac.feature) | @rbac | 7 | `tests/auth/test_rbac.py` |
| [embed.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/embed.feature) | @embed / @api | 5 | `tests/dashboards/test_embed.py`, `tests/health/test_health.py` |
| [misc.feature](file:///d:/workspace/superset-space/superset-docs/e2e/spec/misc.feature) | @misc | 4 | `tests/health/test_health.py` |

**总计**：120 个 Scenario。

## 标签语义

| 标签 | 含义 | pytest marker |
| --- | --- | --- |
| `@auth` | 认证 / 鉴权 | `auth` |
| `@database` | 数据库 | `database` |
| `@dataset` | 数据集 | `database` |
| `@chart` | 图表 CRUD | `chart` |
| `@dashboard` | 仪表盘 CRUD | `dashboard` |
| `@viz` | 图表类型矩阵 | `viz` |
| `@filter` | 仪表盘过滤器 | `filter` |
| `@sqllab` | SQL Lab | `sqllab` |
| `@explore` | Explore 编辑器 | `explore` |
| `@import_export` | 导入 / 导出 | `import_export` |
| `@alert` | 告警 | `alert` |
| `@report` | 报告调度 | `report` |
| `@rbac` | 角色 / 用户 | `rbac` |
| `@embed` | 嵌入 | `embed` |
| `@api` | 公共 API | `api` |
| `@misc` | 系统设置 | `misc` |

`@v4.1` / `@v6.0` 限制单版本。

## 阅读建议

- **业务 / 产品 / QA**：直接看 `*.feature` 文件，按业务语言理解测试覆盖范围
- **工程师**：把 spec 看作需求文档，从 `Scenario` 标题找对应 pytest 实现

## Python 端的 BDD 工具

[`../utils/bdd.py`](../utils/bdd.py) 提供：

| 工具 | 作用 |
| --- | --- |
| `scenario(title, tags)` | 装饰器，自动注册 marker + Allure title/feature/tag |
| `given(text, page=, focus=, screenshot=)` | 前置条件 context manager |
| `when(text, page=, focus=, screenshot=)` | 动作 context manager |
| `then(text, page=, focus=, screenshot=)` | 验证 context manager |
| `and_(text, page=, focus=, screenshot=)` | 补充步骤 context manager |
| `highlight(page, selector)` | 在页面上给指定元素加红框 |
| `_attach_screenshot(page, name)` | 截图并附加到 Allure |

`page=`, `focus=`, `screenshot=` 是可选参数；只在有页面操作的步骤传。

### 报告高亮

执行 UI 用例时：

- `focus="selector"`：注入 JS 给指定元素加红色 outline
- `screenshot=True`：在 step 内自动截图并附加到 Allure
- 失败时自动截 `*_failure.png`，并 attach 动作链 (`action_log`)

打开 Allure 报告时，每个 Scenario 展开为多个 step；每步都附带高亮截图。

## 如何按 spec 重跑

按标签筛选（与 spec 标签一一对应）：

```bash
# auth 全部
python run.py -m auth

# auth + database
python run.py -m auth,database

# viz 矩阵
python run.py -m viz
```

按 Scenario 标题（关键字）：

```bash
# 所有 "create" 类
python run.py -k "create"

# 渲染相关
python run.py -k "render"

# 过滤器
python run.py -k "filter"
```

按 spec 文件名（特定模块）：

```bash
# 仅 sqllab
python -m pytest -m sqllab -v
```

## 维护规则

1. **新增测试**：先在对应 `*.feature` 写 Scenario，再写 pytest 实现
2. **修改测试**：保持 `Scenario` 标题与 `scenario()` 装饰器 title 一致
3. **删除测试**：先删 `*.feature` 场景，再删 pytest
4. **状态同步**：改完测试后更新 [`../COVERAGE.md`](../COVERAGE.md) 对应行
