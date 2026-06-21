# Superset 性能测试 — 变更日志

按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 风格记录。

## [Unreleased]

### 文档整理（2026-06-21）

#### Added
- `CHANGELOG.md`（本文件）：perf 模块独立变更记录
- `.github/workflows/perf.yml`：GitHub Actions 工作流
  - PR gate：k6 `dashboard_list` (300 VU) + `chart_list` (200 VU)
  - nightly：Locust 10 min × {4.1, 6.0} + 重点 k6 全部
  - workflow_dispatch：手动触发，duration / version 可调
- `Jenkinsfile`（项目根）：Jenkins Pipeline as Code
  - 4 档参数化：`pr-gate` / `nightly` / `release` / `smoke`
  - 与 GHA 镜像：元测试 + Locust + 重点 k6 + 基线对比 + docker stats
  - `disableConcurrentBuilds()` / `archiveArtifacts` / `cleanup`
- `e2e/perf/docs/JENKINS.md`：Jenkins 部署详细指南
  - 架构总览、agent 节点要求、凭据配置
  - 4 种触发方式（手动 / 定时 / GitHub webhook / GitLab webhook）
  - 4 档详解、报告产物、失败判定
  - 与 GHA 对照表、10 项快速检查清单
- `PLAN.md` §10.1 实施进度表：标明 P5-1~P5-7 各自状态
- `PLAN.md` §10.2 已落地文件清单
- `PLAN.md` §9.4 Jenkins 集成：档位表 + 与 GHA 差异
- `README.md` 实施状态表 + 跨版本差异说明 + Jenkins 链接

#### Changed
- `PLAN.md` 状态从"草案 v1.1"更新为"v1.0 已实现"
- `README.md` 状态从"v1.1 实施版"更新为"v1.0 已实现"
- 重点端点 `/api/v1/dashboard/{id}/charts/`（带尾斜杠）→ `/api/v1/dashboard/{id}/charts`（6.0 实际路径）：
  - `PLAN.md` §5.2 / §6.1
  - `README.md` 重点查询表
  - `e2e/config/config.yaml` `perf.critical_endpoints`
- `k6/scripts/lib.js`：增加每 VU token 缓存（10 min TTL），避免每轮都登录
- `k6/scripts/chart_data.js`：增加 `SUPERSET_VERSION` 环境变量，自动切换 4.1 `slice_id` / 6.0 `datasource+queries` payload
- `k6/scripts/dashboard_detail.js`：去除 `/charts/` 尾斜杠（6.0 兼容）

---

## [1.0.0] - 2026-06-21

首版交付。P5-1 ~ P5-6 全部完成，P5-7 报告/文档部分完成。

### Added
- 目录结构 `e2e/perf/{common,locust,k6,baselines,reports,tools,tests}/`
- `e2e/config/config.yaml` `perf:` 段（重点查询白名单、阈值、角色权重）
- `common/` 6 个模块：
  - `config_loader.py`：deep-merge defaults + `get_perf_config` / `get_target_instance`
  - `auth.py`：复用 `utils.api.login_client`，线程级 10 min token 缓存
  - `metrics.py`：`EndpointStats` / `MetricsCollector` / Apdex / Stability
  - `thresholds.py`：`load_baseline` / `save_baseline` / `is_critical_endpoint` / `compare`（critical vs normal 分级）
  - `docker_stats.py`：daemon 线程采 docker stats → CSV
  - `report.py`：`render_summary` / `write_json_snapshot`
- `locust/` 4 角色 + LoginStorm（共 28 个 task）：
  - `base.py`：`SupersetUser` / `BaseBehavior` / `GLOBAL_METRICS`
  - `admin_ops.py`：CRUD 写路径
  - `analyst.py`：Explore / chart 写 / SQL Lab
  - `viewer.py`：⭐ 重点 dashboard / chart 读路径
  - `embed.py`：嵌入式访问
  - `login_storm.py`：独立登录风暴
- `k6/scripts/` 9 个脚本：
  - `lib.js`：共享登录 + auth headers
  - `smoke.js` (30 VU / 1 min)
  - `login_storm.js` (200 VU / 30s)
  - `dashboard_list.js` (300 VU / 3 min) **PR 必跑**
  - `dashboard_detail.js` (200 VU / 3 min)
  - `dashboard_render.js` (150 VU / 3 min)
  - `chart_list.js` (200 VU / 2 min) **PR 必跑**
  - `chart_data.js` (100 VU / 5 min) ⭐⭐
  - `explore_stress.js` (100 VU / 2 min)
  - `endurance.js` (50 VU / 30 min)
- `baselines/v6_0.json`：10 VU / 2 min cold-start 实测基线（16 端点，0 错误）
- `baselines/v4_1.json`：占位（待 P5-1 跑出正式基线）
- `tools/` 5 个工具：
  - `wait_healthy.py`：等待 Superset `/health` 200
  - `run_locust.sh`：默认 200 VU / 10 min，支持 `--web` UI
  - `run_k6.sh`：按脚本名自动选 VU/duration
  - `compare_baseline.py`：`--strict --exit-on-fail` PR 门禁
  - `save_baseline.py`：角色变体聚合（viewer/analyst/embed/html → method+path）
  - `collect_docker_stats.py`：压测期间后台采容器
- `tests/` 3 个元测试（共 13 用例）：
  - `test_config.py` (4)：配置加载 / 角色权重 / 阈值分级 / 实例查找
  - `test_thresholds.py` (4)：critical 端点匹配 / p95 / error rate
  - `test_baseline_schema.py` (5)：基线文件存在 / schema / 重点端点覆盖

### Changed
- 重点端点白名单（7 条）：
  - `GET:/api/v1/dashboard/`
  - `GET:/api/v1/dashboard/{id}`
  - `GET:/api/v1/dashboard/{id}/charts`
  - `GET:/superset/dashboard/{id}/`
  - `GET:/api/v1/chart/`
  - `GET:/api/v1/chart/{id}`
  - `POST:/api/v1/chart/data`

### Notes
- **跨版本差异**（必看）：
  - 6.0 路径：去掉 `/api/v1/dashboard/{id}/charts/` 的尾斜杠
  - 6.0 payload：`POST /api/v1/chart/data` 改用 `datasource{id,type}+queries[]`
- **环境受限**：当前 6.0 基线用 10 VU / 2 min（cold-start 容器资源限制），目标 200 VU / 10 min 待 CI 跑出后覆盖

---

## 版本号规则

- 主版本：破坏性重构（schema 不兼容）
- 次版本：新功能（新脚本、新角色、新维度）
- 修订号：bug 修复、文档更新

发布 tag：`perf-vX.Y.Z`
