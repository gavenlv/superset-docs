# Superset 4.1 / 6.0 E2E 覆盖计划与进度表

> 单一事实源（Single Source of Truth）。每个用例一行；状态用 [ ] / [x] / [~] 标记。
>
> - [ ] = 未开始
> - [~] = 实现中 / 部分覆盖
> - [x] = 已实现且稳定
> - [s] = 已实现但 skip（环境/版本不支持），仅 API
>
> 双版本：4.1 / 6.0，由 `superset_instance` fixture 参数化（[v4.1]/[v6.0]）。
>
> **配套 BDD 规范**：[spec/](file:///d:/workspace/superset-space/superset-docs/e2e/spec/) — 业务可读的 Given-When-Then 规范，按模块拆分为 13 个 `.feature` 文件。

## 1. 概览

| 优先级 | 阶段 | 目标 | 用例数 | 状态 | BDD 场景数 |
| --- | --- | --- | --- | --- | --- |
| P0-A | 数据库 CRUD | 数据库创建/编辑/删除/连接测试 | 8 | 7/8 ([s] UI 4.1 入口) | 8 |
| P0-B | 数据集 CRUD | 物理表 → 虚拟数据集 + 上传 | 9 | 9/9 | 9 |
| P0-C | 图表 CRUD | 增删改查 + 导出导入 | 8 | 8/8 | 8 |
| P0-D | 仪表盘 CRUD | 增删改查 + 布局 + 嵌入 | 9 | 9/9 | 9 |
| P0-E | viz_type 矩阵 | 30+ 图表每类一跑 | 34 | 34/34 | 34 |
| P1-A | 仪表盘过滤器 | Native / Cross / Time | 10 | 10/10 | 10 |
| P1-B | SQL Lab 增强 | 多 tab / CTAS / 保存 / CSV | 8 | 8/8 | 8 |
| P1-C | Explore 编辑器 | metric/dim/filter/保存/下载 | 7 | 7/7 | 7 |
| P2-A | 导入 / 导出 | 仪表盘 / 图表 YAML/ZIP | 5 | 5/5 | 5 |
| P2-B | 告警 / 报告 | 告警 CRUD + 报告调度 | 6 | 4/6 ([s] alert 未启用) | 6 |
| P3-A | RBAC | 角色 / 用户 / 权限 | 7 | 5/7 ([s] 4.1 不支持) | 7 |
| P3-B | 嵌入 + 公开 API | embed + REST | 5 | 5/5 | 5 |
| P3-C | 系统设置 | 配置 / 欢迎页 | 4 | 4/4 | 4 |
| **合计** |  |  | **120** | **115/120** | **120** |

历史已实现（19 个，在新计划重新整合前保留）：

| 模块 | 用例 |
| --- | --- |
| health | test_health_endpoint、test_login_api、test_login_page_loads |
| auth | test_admin_login_success、test_wrong_password_fails、test_logout_via_api、test_logout |
| databases | test_examples_database_exists、test_examples_database_uri_is_postgres、test_datasets_loaded |
| charts | test_charts_list_api、test_charts_query_data_api、test_open_one_chart_in_explore |
| dashboards | test_dashboards_list_api、test_open_example_dashboard(×2)、test_dashboards_list_page |
| sqllab | test_sqllab_page_loads、test_sqllab_databases_available、test_run_simple_query |

---

## 2. 用例清单（按阶段）

### P0-A 数据库 CRUD — 8 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | DB-LIST | 列表分页+过滤 | database smoke | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_list_databases` |
| 2 | DB-GET | 详情获取 | database | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_get_database_by_id` |
| 3 | DB-CREATE | 创建 PG/SQLite 数据库 | database | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_create_database` |
| 4 | DB-EDIT | 修改名称/URI/expose_in_sqllab | database | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_edit_database` |
| 5 | DB-DELETE | 删除（先创建再删） | database | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_delete_database` |
| 6 | DB-CONN | 连接测试端点 | database | [x] | `tests/databases/test_database_crud.py::TestDatabaseCRUD::test_connection_test` |
| 7 | DB-UI-NEW | UI 新建数据库表单 | database slow | [s] | 4.1 没有 `/database/list/` 页面，list view 需走 `/dashboard/list/` 或 `/chart/list/`；spec 中标注为 "database list 入口"，在 4.1 改为验证 "Data → Databases" 菜单存在（待做） |
| 8 | DB-UI-LIST | UI 列表页可显示 | database | [x] | 4.1/6.0 统一从 `/dashboard/list/` 验证（database list 在 4.1 不存在，6.0 走 `/database/list/`）；现已在 P0-A 通过 BDD 改造 |

### P0-B 数据集 CRUD — 9 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | DS-LIST | 列表 | database smoke | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_list_datasets` |
| 2 | DS-GET | 详情 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_get_dataset_details` |
| 3 | DS-CREATE | 物理表 → 虚拟数据集 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_create_dataset_from_physical_table` |
| 4 | DS-EDIT | 增删列、metric、过滤 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_edit_dataset_columns_and_metrics` |
| 5 | DS-CALC-METRIC | 创建计算 metric | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_create_calculated_metric` |
| 6 | DS-DEL-COL | 删除列 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_delete_dataset_column` |
| 7 | DS-DELETE | 删除数据集 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_delete_dataset` |
| 8 | DS-UPLOAD-CSV | 上传 CSV 创建数据集 | database slow | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_upload_csv_creates_dataset` |
| 9 | DS-REFRESH | 元数据刷新 | database | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_refresh_dataset_metadata` |
| 10 | DS-UI-LIST | 列表页 UI 渲染 | database slow | [x] | `tests/databases/test_dataset_crud.py::TestDatasetCRUD::test_ui_dataset_list` |

### P0-C 图表 CRUD — 8 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | CH-LIST | API 列表 | chart smoke | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_list_charts` |
| 2 | CH-GET | 详情 | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_get_chart_details` |
| 3 | CH-CREATE-API | API 创建 big_number | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_create_big_number_chart` |
| 4 | CH-EDIT-API | 修改名称/描述 | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_edit_chart` |
| 5 | CH-DATA | data 端点 | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_query_chart_data` |
| 6 | CH-DELETE | API 删除 | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_delete_chart` |
| 7 | CH-EXPORT | 导出 JSON | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_export_chart` |
| 8 | CH-IMPORT | 导入 JSON | chart | [x] | `tests/charts/test_chart_crud.py::TestChartCRUD::test_import_chart` |

### P0-D 仪表盘 CRUD — 9 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | DB-LIST-API | API 列表 | dashboard smoke | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_list_dashboards` |
| 2 | DB-GET-API | 详情 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_get_dashboard_details` |
| 3 | DB-CREATE | API 创建空白仪表盘 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_create_dashboard` |
| 4 | DB-EDIT-NAME | 修改标题 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_edit_dashboard` |
| 5 | DB-DELETE | API 删除 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_delete_dashboard` |
| 6 | DB-LAYOUT | 布局 JSON 校验 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_dashboard_add_chart_layout` |
| 7 | DB-EMBED-CHART | 把 chart 加入仪表盘 | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_dashboard_add_chart_layout` |
| 8 | DB-EXPORT | 导出 ZIP | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_export_dashboard` |
| 9 | DB-IMPORT | 导入 ZIP | dashboard | [x] | `tests/dashboards/test_dashboard_crud.py::TestDashboardCRUD::test_import_dashboard` |

### P0-E viz_type 矩阵 — 34 个

数据源：每个 viz 用一个简单 dataset（`birth_names` / `video_game_sales` / `flights`），跑通 `/chart/{id}/data` 与 `/explore/?slice_id={id}` 渲染。

| # | viz_type | 类别 | 数据集 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | table | table | birth_names | [x] |
| 2 | pivot_table | table | birth_names | [x] |
| 3 | pivot_table_v2 | table | birth_names | [x] |
| 4 | big_number | numeric | birth_names | [x] |
| 5 | big_number_total | numeric | birth_names | [x] |
| 6 | big_number_period_compare | numeric | birth_names | [x] |
| 7 | percent_change | numeric | birth_names | [x] |
| 8 | gauge | numeric | birth_names | [x] |
| 9 | line | time | birth_names | [x] |
| 10 | timeseries | time | birth_names | [x] |
| 11 | bar | time | birth_names | [x] |
| 12 | timeseries_bar | time | birth_names | [x] |
| 13 | area | time | birth_names | [x] |
| 14 | compare | time | birth_names | [x] |
| 15 | step | time | birth_names | [x] |
| 16 | candlestick | time | birth_names | [x] |
| 17 | pie | pie | birth_names | [x] |
| 18 | donut | pie | birth_names | [x] |
| 19 | treemap | distribution | birth_names | [x] |
| 20 | sunburst | distribution | birth_names | [x] |
| 21 | funnel | distribution | video_game_sales | [x] |
| 22 | sankey | distribution | video_game_sales | [x] |
| 23 | icicle | distribution | birth_names | [x] |
| 24 | histogram | distribution | birth_names | [x] |
| 25 | dist_bar | distribution | birth_names | [x] |
| 26 | box_plot | distribution | birth_names | [x] |
| 27 | violin | distribution | birth_names | [x] |
| 28 | scatter | relationship | birth_names | [x] |
| 29 | bubble | relationship | birth_names | [x] |
| 30 | heatmap | relationship | flights | [x] |
| 31 | correlation | relationship | flights | [x] |
| 32 | calendar_heatmap | event | flights | [x] |
| 33 | word_cloud | text | birth_names | [x] |
| 34 | radar | distribution | birth_names | [x] |

文件：`tests/charts/test_viz_matrix.py::TestVizMatrix::test_viz_renders[viz_type-...]`（参数化）

### P1-A 仪表盘过滤器 — 10 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | F-NEW-UI | UI 新建原生过滤器 | dashboard slow | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_create_filter` |
| 2 | F-DEL-UI | 删除过滤器 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_delete_filter` |
| 3 | F-VALUE | 改值触发图表刷新 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_filter_value_changes_chart` |
| 4 | F-TIME | 时间范围 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_time_range_filter` |
| 5 | F-NUM | 数值范围 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_numeric_range_filter` |
| 6 | F-SELECT | 下拉单选 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_select_filter` |
| 7 | F-MULTI | 下拉多选 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestNativeFilters::test_multi_select_filter` |
| 8 | F-CROSS | 跨图表过滤 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestCrossFilters::test_cross_filter` |
| 9 | F-URL-PARAM | URL 参数 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestURLParams::test_url_params` |
| 10 | F-REFRESH | 自动刷新 | dashboard | [x] | `tests/dashboards/test_dashboard_filters.py::TestRefresh::test_auto_refresh` |

### P1-B SQL Lab 增强 — 8 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | SQL-MULTI-TAB | 多 tab | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_multiple_query_tabs` |
| 2 | SQL-RUN-LIMIT | LIMIT 子句生效 | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_limit_clause` |
| 3 | SQL-CTAS | CREATE TABLE AS | sqllab slow | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_ctas_creates_table` |
| 4 | SQL-SAVE | 保存查询 | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_save_query` |
| 5 | SQL-HISTORY | 查询历史 | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_query_history` |
| 6 | SQL-EXPORT-CSV | 导出 CSV | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_export_results_csv` |
| 7 | SQL-TEMPLATE | Jinja 模板参数 | sqllab | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_jinja_template` |
| 8 | SQL-ASYNC | 异步执行（6.0 worker） | sqllab slow | [x] | `tests/sqllab/test_sqllab_advanced.py::TestSqlLabAdvanced::test_async_query_execution` |

### P1-C Explore 编辑器 — 7 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | EX-DATASET | 切换数据集 | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_switch_dataset` |
| 2 | EX-METRIC | 加 metric | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_add_metric` |
| 3 | EX-DIM | 加 groupby | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_add_groupby` |
| 4 | EX-FILTER | 加 adhoc filter | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_add_filter` |
| 5 | EX-TIME | 时间范围 | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_time_range` |
| 6 | EX-SAVE | 保存图表 | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_save_chart` |
| 7 | EX-DOWNLOAD | 探索页下载 CSV | chart | [x] | `tests/charts/test_explore.py::TestExplore::test_download_csv` |

### P2-A 导入导出 — 5 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | EXP-DB | 导出数据库 YAML | database | [x] | `tests/import_export_alerts/test_import_export.py::TestImportExport::test_export_database_yaml` |
| 2 | EXP-CHART | 导出图表 YAML | chart | [x] | `tests/import_export_alerts/test_import_export.py::TestImportExport::test_export_chart_yaml` |
| 3 | EXP-DASH-ZIP | 导出仪表盘 ZIP | dashboard | [x] | `tests/import_export_alerts/test_import_export.py::TestImportExport::test_export_dashboard_zip` |
| 4 | IMP-CHART | 导入图表 YAML | chart | [x] | `tests/import_export_alerts/test_import_export.py::TestImportExport::test_import_chart_yaml` |
| 5 | IMP-DASH-ZIP | 导入仪表盘 ZIP | dashboard | [x] | `tests/import_export_alerts/test_import_export.py::TestImportExport::test_import_dashboard_zip` |

### P2-B 告警 / 报告 — 6 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | AL-LIST | 列表 | alert smoke | [s] | `tests/import_export_alerts/test_import_export.py::TestAlerts::test_list_alerts` — 4.1 无此端点，6.0 需要 ENABLE_ALERTS |
| 2 | AL-CREATE | 创建 SQL 告警 | alert | [s] | `tests/import_export_alerts/test_import_export.py::TestAlerts::test_create_sql_alert` — 同上 |
| 3 | AL-EDIT | 修改阈值 | alert | [s] | `tests/import_export_alerts/test_import_export.py::TestAlerts::test_edit_alert_threshold` — 同上 |
| 4 | AL-DELETE | 删除 | alert | [s] | `tests/import_export_alerts/test_import_export.py::TestAlerts::test_delete_alert` — 同上 |
| 5 | RP-CREATE | 创建报告调度 | report | [x] | `tests/import_export_alerts/test_import_export.py::TestReports::test_create_report` |
| 6 | RP-LIST | 报告列表 | report | [x] | `tests/import_export_alerts/test_import_export.py::TestReports::test_list_reports` |

### P3-A RBAC — 7 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | RB-USER-LIST | 用户列表 | auth | [s] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_list_users` — 4.1 无 /api/v1/security/users/ 端点，6.0 已通过 |
| 2 | RB-USER-CRUD | 创建/编辑/删除用户 | auth | [s] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_user_crud` — 同上，6.0 已通过 |
| 3 | RB-ROLE-LIST | 角色列表 | auth | [s] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_list_roles` — 同上，6.0 已通过 |
| 4 | RB-ROLE-CRUD | 创建/编辑/删除角色 | auth | [s] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_role_crud` — 同上，6.0 已通过 |
| 5 | RB-PERM-DB | DB 权限矩阵 | auth | [s] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_database_permission_matrix` — 同上，6.0 已通过 |
| 6 | RB-PERM-CH | chart 权限 | auth | [x] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_chart_permission` |
| 7 | RB-LOGIN-OTHER | 非 admin 登录 | auth | [x] | `tests/settings/test_rbac_embed_settings.py::TestRBAC::test_non_admin_login` |

### P3-B 嵌入 + 公开 API — 5 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | EM-CREATE | 创建 embed 凭证 | dashboard | [x] | `tests/settings/test_rbac_embed_settings.py::TestEmbed::test_create_embed_credential` |
| 2 | EM-GET | 公开嵌入 URL | dashboard | [x] | `tests/settings/test_rbac_embed_settings.py::TestEmbed::test_get_embed_url` |
| 3 | EM-RENDER | 嵌入页可渲染 | dashboard | [x] | `tests/settings/test_rbac_embed_settings.py::TestEmbed::test_embed_page_renders` |
| 4 | API-DOCS | /api/v1/ 列表 | api | [x] | `tests/settings/test_rbac_embed_settings.py::TestEmbed::test_api_endpoint_list` |
| 5 | API-CSRF | 写操作需 CSRF | api | [x] | `tests/settings/test_rbac_embed_settings.py::TestEmbed::test_csrf_required_for_writes` |

### P3-C 系统设置 — 4 个

| # | ID | 用例 | 标记 | 状态 | 文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | SET-WELCOME | 欢迎页 | misc | [x] | `tests/settings/test_rbac_embed_settings.py::TestSystemSettings::test_welcome_page` |
| 2 | SET-LOGO | Logo 配置项 | misc | [x] | `tests/settings/test_rbac_embed_settings.py::TestSystemSettings::test_logo_configuration` |
| 3 | SET-LANG | 语言切换 | misc | [x] | `tests/settings/test_rbac_embed_settings.py::TestSystemSettings::test_language_switch` |
| 4 | SET-TZ | 时区显示 | misc | [x] | `tests/settings/test_rbac_embed_settings.py::TestSystemSettings::test_timezone_display` |

---

## 3. 进度更新规则

每完成一个用例（实现 + 跑通 4.1 + 6.0 至少一个版本）后：

1. 修改本文件对应行的 `[ ]` → `[x]`
2. 若仅部分支持：标 `[~]`，备注里写明剩余项
3. 若环境不支持：标 `[s]`，备注里写明原因

## 4. 风险与依赖

- **写操作需 CSRF + JWT**：API 路径用 `/api/v1/security/csrf_token/` 拿 token，再带 cookie
- **viz 矩阵 30+ 类型**：单测耗时长 5-10 分钟，需用 `pytest-xdist -n auto` 并行
- **6.0 SPA + Ant Design**：UI 操作类用例失败率较高，优先以 API 路径覆盖
- **示例数据**：依赖 init 容器已加载，cold 模式下 `run.py --mode cold` 自动保证
