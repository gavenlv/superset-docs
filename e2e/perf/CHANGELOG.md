# Superset 性能测试 — 变更日志

按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 风格记录。

## [Unreleased]

### 多环境 / 多用户（2026-06-21）

#### Added
- `e2e/config/config.{dev,sit,uat,prod}.yaml`：环境分层配置
  - `config.yaml` base + `<env>.yaml` deep-merge 覆盖
  - 每个 env 独立 `user_pool` / `instances.base_url` / `perf.users/duration`
- `e2e/utils/user_pool.py`：线程安全的 user_pool 单例
  - `pick(role, index=None, strategy="random|round_robin")`
  - `acquire(role)` 压测 VU 分配
  - `token_for(user, base_url)` per-user 缓存（10 min TTL）
  - `csrf_for(user, base_url)` 同缓存
  - `invalidate / clear_cache` 强制重登
- `e2e/config/settings.py` 重构：
  - `SUPPORTED_ENVS = ("dev", "sit", "uat", "prod")`
  - `current_env()` 从 `E2E_ENV` 读
  - `reload_config(env)` 切换 env
  - `User` dataclass + `user_pool: dict[role, tuple[User, ...]]`
  - `perf: dict` 段透传
- `e2e/fixtures/playwright_fixtures.py` 多用户 fixture：
  - `user_pool` 暴露单例
  - `login_as_role(role, index=None)` 工厂 fixture（独立 context）
  - `multi_user_pages[N]` 参数化拿 N 个用户
- `e2e/run.py` `--env` + `--list-users`：
  - `python run.py --env sit -m smoke`
  - `python run.py --list-users` 打印当前 env 的 user_pool
- `e2e/perf/common/auth.py` 多用户接入：
  - `acquire_user(role)` 给 VU 分配用户 + 绑 thread-local
  - `get_cached_token(base_url)` per-user 拿 token
  - 保留旧 `get_cached_token` admin 单用户路径
- `e2e/perf/locust/tasks/base.py`：
  - `SupersetUser.role` 类属性标注
  - `on_start` 调 `acquire_user(self.role)`
  - endpoint name 追加 `  (username)` 后缀，便于按用户统计
- `e2e/perf/locust/tasks/{viewer,analyst,admin_ops,embed}.py`：
  - `role = "..."` 类属性
- `e2e/perf/k6/scripts/lib.js` 多用户：
  - `K6_USERS_JSON` 环境变量传入用户池
  - 每 VU 用 `(VU-1) % pool_size` 选用户（round-robin）
  - `pickUser(vuId)` / `currentUsername()` 导出
- `e2e/perf/tools/run_k6.sh` `--multi-user <role>`：
  - 自动从 `user_pool.<role>` 拉凭据，构造 K6_USERS_JSON
- `e2e/perf/tools/run_locust.sh`：
  - `E2E_ENV` 切环境
  - 启动时打印 user_pool 概览
  - `USERS` / `SPAWN_RATE` / `RUN_TIME` 可调
- `e2e/perf/tools/wait_healthy.py`：
  - `--env <env>` 参数 + 切换 config
- `e2e/tests/multi_user/test_multi_user_e2e.py`（示例）：
  - `test_concurrent_login`：3 个 viewer 同时登录
  - `test_admin_vs_viewer_visibility`：admin vs viewer 权限差异
  - `test_user_pool_size`：池大小约束
  - `test_env_specific_pool`：3 个 env 各自加载
- `e2e/perf/tests/test_config.py` +5 元测试：
  - `test_user_pool_has_four_roles`
  - `test_user_pool_viewer_size_supports_load`
  - `test_user_pool_pick_by_role`
  - `test_user_pool_pick_by_index_is_deterministic`
  - `test_supported_envs`
- `e2e/perf/docs/MULTI_ENV_USER.md`：完整使用文档
- `e2e/pyproject.toml` 新增 marker：`perf` / `multi_user` / `env_specific`

#### Changed
- `config/settings.py` 增加 `env` / `user_pool` / `perf` 段
- 旧 `login_client()` 仍可用（admin 单用户），向后兼容
- k6 lib.js 每 VU 绑定一个用户（之前是共享 token 池）
- Locust endpoint name 追加 `  (username)` 后缀（旧基线聚合需 strip_role）

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
