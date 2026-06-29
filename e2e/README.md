# Superset E2E 自动化测试

针对 Superset 4.1 与 6.0 的端到端自动化测试框架。支持 UI（Playwright）+ API（httpx）+ 数据库多层验证；参数化双版本；冷启动 / 复用服务两种模式；Allure 报告 + 自动重试 + 失败截图。

## 📚 学习路径

| 角色 | 推荐文档 | 目标 |
|-----|---------|------|
| **新手入门** | [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md) | 从零开始，跑第一个测试 |
| **快速上手** | [docs/QUICKSTART.md](./docs/QUICKSTART.md) | 5 分钟跑通所有测试 |
| **离线 Examples** | [docs/OFFLINE_EXAMPLES.md](./docs/OFFLINE_EXAMPLES.md) | 在无外网环境下导入示例数据 |
| **理解设计** | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 知道「为什么」这么设计 |
| **查看报告** | [docs/REPORTS.md](./docs/REPORTS.md) | E2E / 性能测试报告查看 |
| **多环境配置** | [config/README.md](./config/README.md) | 配置 dev/sit/uat/prod |

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        测试用例层 (tests/)                          │
│  test_login.py  │  test_dashboard.py  │  test_charts.py            │
│  业务场景描述，用 BDD 风格（Given/When/Then）                       │
├─────────────────────────────────────────────────────────────────────┤
│                      Page Object 层 (pages/)                        │
│  LoginPage  │  DashboardPage  │  ExplorePage  │  SqlLabPage        │
│  封装页面交互，屏蔽 4.1/6.0 DOM 差异                                │
├─────────────────────────────────────────────────────────────────────┤
│                    Page Actions 层 (utils/page_actions.py)          │
│  pa.click() │  pa.fill() │  pa.goto() │  pa.hover()               │
│  增强 Playwright 操作：高亮 + Allure step + 延迟观察                 │
├─────────────────────────────────────────────────────────────────────┤
│                      基础设施层                                     │
│  config/       → 多环境配置（yaml + env 变量）                       │
│  fixtures/     → pytest 夹具（浏览器、登录、多用户）                  │
│  utils/        → 工具（BDD、稳定性、日志、用户池）                   │
├─────────────────────────────────────────────────────────────────────┤
│                    性能测试层 (perf/)                               │
│  Locust 多角色压测 │  k6 单端点高压 │  基线对比 │  Docker 资源统计   │
│  与 E2E 共享配置和用户池                                            │
└─────────────────────────────────────────────────────────────────────┘
```

## 目录

- [技术栈](#技术栈)
- [核心特性](#核心特性)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [运行模式](#运行模式)
- [CLI 工具（run.py）](#cli-工具runpy)
- [标记 (markers)](#标记-markers)
- [编写新测试](#编写新测试)
- [配置与环境变量](#配置与环境变量)
- [多环境与多用户](#多环境与多用户)
- [性能测试入口](#性能测试入口)
- [稳定性策略](#稳定性策略)
- [Allure 报告](#allure-报告)
- [CI 集成](#ci-集成)
- [故障排查](#故障排查)
- [清理临时文件](#清理临时文件)

## 技术栈

| 关注点         | 选型                          |
| -------------- | ----------------------------- |
| 核心框架       | pytest 8.3                    |
| 浏览器自动化   | Playwright 1.48               |
| HTTP 客户端    | httpx                         |
| 报告           | Allure + pytest-allure        |
| 重试           | pytest-rerunfailures + tenacity |
| 容器编排       | docker compose CLI            |
| 配置           | PyYAML + python-dotenv        |
| Page Object    | 自研封装 + utils/stability.py |

## 核心特性

| 维度 | 覆盖 |
| --- | --- |
| 多版本 | Superset 4.1.1 + 6.0.0，参数化自动遍历 |
| 多环境 | dev / sit / uat / prod 4 档，配置独立 |
| 多用户 | per-role 用户池（admin/analyst/viewer/embed），支持 200+ VU |
| E2E UI | Playwright 自动化（4.1 SSR / 6.0 SPA 兼容） |
| E2E API | httpx 调用，含 CSRF + JWT |
| 多用户 fixture | `login_as_role` / `multi_user_pages` 工厂 |
| 性能压测 | Locust（4 角色 28 task）+ k6（9 脚本 重点查询） |
| 基线对比 | p50/p95/p99 + error rate，critical 端点严格阈值 |
| 报告 | Allure HTML + Locust 原生 + k6 JSON + docker stats CSV |

## 目录结构

```
e2e/
├── conftest.py                  # 顶层 fixture 入口（聚合 fixtures/）
├── run.py                       # CLI 入口（支持 --env / --list-users）
├── pyproject.toml               # pytest 配置 + 依赖
├── requirements.txt             # 显式依赖列表
├── docs/
│   ├── QUICKSTART.md            # 一页式快速开始
│   ├── REPORTS.md               # 报告查看指南（E2E / Locust / k6 / 基线对比）
│   ├── OFFLINE_EXAMPLES.md      # 离线示例数据导入指南
│   ├── ARCHITECTURE.md          # 架构设计
│   └── GETTING_STARTED.md       # 新手入门教程
├── config/                      # 多环境分层配置
│   ├── settings.py              # 加载逻辑（yaml + env + user_pool 解析）
│   ├── config.yaml              # base（dev）
│   ├── config.sit.yaml          # SIT 覆盖
│   ├── config.uat.yaml          # UAT 覆盖
│   └── config.prod.yaml         # PROD 覆盖
│
├── fixtures/                    # pytest fixtures
│   ├── conftest.py              # 服务生命周期 fixture（cold/reuse）
│   ├── playwright_fixtures.py   # 浏览器、context、login_as_role、multi_user_pages
│   └── allure_config.py         # Allure 环境/分类 hook
│
├── pages/                       # Page Object Model
│   ├── login_page.py            # 登录（兼容 4.1 SSR / 6.0 SPA）
│   ├── dashboard_page.py        # 仪表盘列表 + 详情
│   ├── explore_page.py          # Explore 图表编辑
│   └── sqllab_page.py           # SQL Lab（兼容 ant-table 与 sql-result-table）
│
├── utils/                       # 工具
│   ├── process.py               # 子进程 + HTTP 等待工具
│   ├── service.py               # docker compose 编排（cold/reuse）
│   ├── stability.py             # 健壮选择器、轮询等待、健壮点击
│   ├── logging.py               # 日志初始化
│   ├── bdd.py                   # Given/When/Then 上下文管理器
│   ├── page_actions.py          # 高亮 Playwright 包装
│   └── user_pool.py             # 多用户池（多环境 / 多用户并发）
│
├── tests/                       # 测试用例
│   ├── conftest.py              # 测试级别 fixture 补充
│   ├── health/                  # 健康检查（/health、登录、CSRF）
│   ├── auth/                    # 登录 / 登出 / 权限
│   ├── dashboards/              # 仪表盘列表 / 详情 / 交互
│   ├── charts/                  # 单图表
│   ├── sqllab/                  # SQL Lab（页面、查询）
│   ├── databases/               # 数据库 / 数据集
│   ├── import_export_alerts/    # 导入导出 / 告警
│   ├── extras/                  # 补充
│   ├── settings/                # RBAC / embed settings
│   └── multi_user/              # 多用户并发 E2E
│
├── spec/                        # BDD feature 文件（English）
│
├── reports/                     # 运行时产物
│
└── perf/                        # 性能测试套件（详见 e2e/perf/README.md）
    ├── README.md
    ├── PLAN.md
    ├── CHANGELOG.md
    ├── docs/
    │   ├── JENKINS.md
    │   └── MULTI_ENV_USER.md
    ├── common/                  # 6 个共享模块
    ├── locust/                  # Locust 4 角色 + LoginStorm
    ├── k6/scripts/              # 9 个 k6 脚本
    ├── baselines/               # 基线 JSON
    ├── reports/                 # 压测报告
    ├── tools/                   # 辅助脚本
    └── tests/                   # 元测试
```

## 快速开始

### 1. 前置要求

- Python 3.10+（推荐 3.12）
- 已启动 Superset 4.1 + 6.0（参见仓库根 [README.md](../README.md)）
- 至少 4 GB 可用内存（浏览器 + Superset）

### 2. 安装依赖

```bash
cd e2e

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（chromium）
playwright install chromium
```

> Windows 上如遇 `playwright install` 失败，先手动下载 [浏览器](https://playwright.dev/python/docs/browsers#chromium-on-windows) 放到 `%USERPROFILE%\AppData\Local\ms-playwright\`；不要加 `--with-deps`（仅 Linux 有效）。

### 3. 确认 Superset 已运行

```bash
curl http://localhost:18088/health   # 4.1
curl http://localhost:18089/health   # 6.0
```

两个都应返回 `OK`。

### 4. 运行测试

```bash
# 复用现有服务跑 smoke（推荐首次跑）
python run.py -m smoke

# 完整冷启动：从零开始（先 down -v 再 up -d）
python run.py --mode cold -m smoke

# 只跑 4.1
python run.py --instance 4.1

# 只跑 6.0
python run.py --instance 6.0

# 关键字过滤
python run.py -k dashboard

# 跑全部并生成 Allure
python run.py --allure
```

### 5. 查看报告

```bash
# 推荐：启动 allure 服务（带历史趋势）
allure serve reports/allure-results

# 或生成静态 HTML
allure generate reports/allure-results -o reports/allure-report --clean
```

## 运行模式

通过 `mode`（配置项 `E2E_MODE` 或 `--mode`）控制。

### reuse（默认）

复用已启动的 Superset 服务。**只做健康检查 + 登录验证**。

适用场景：
- 本地已有 Superset 跑着
- 快速迭代测试代码
- CI 默认行为（前置 Job 已启动服务）

### cold

测试运行前执行 `docker compose down -v && up -d`，**完全清空数据并重新加载示例**。

适用场景：
- 验证清理后能否正常加载数据
- 复现“从零启动”问题
- 冒烟测试（smoke）

测试结束后会 `docker compose down`（保留数据卷），可通过 `--no-cleanup` 或 `E2E_CLEANUP=0` 改为保留容器。

## CLI 工具（run.py）

`python run.py` 是推荐的统一入口，封装了「装依赖 → 装浏览器 → 跑 pytest → 生成 Allure」全流程。

| 参数                    | 说明                                       | 默认值     |
| ----------------------- | ------------------------------------------ | ---------- |
| `--mode {cold,reuse}`   | 服务启动模式                               | `reuse`    |
| `--env {dev,sit,uat,prod}` | 切换环境（加载 `config.<env>.yaml` 覆盖） | `dev`      |
| `--instance {4.1,6.0,all}` | 限定版本                                  | `all`      |
| `-m, --marker`          | pytest marker 过滤（如 `smoke`、`auth`）   |            |
| `-k, --keyword`         | pytest 关键字过滤                          |            |
| `--browser {chromium,firefox,webkit}` | 浏览器类型                    | `chromium` |
| `--headed`              | 有头模式（默认 headless）                  | `false`    |
| `--reruns N`            | 失败重试次数                               | `2`        |
| `--timeout N`           | 单用例超时（秒）                           | `120`      |
| `--no-cleanup`          | cold 模式下测试结束后不清理容器            | `false`    |
| `--allure`              | 跑完后生成 Allure HTML 报告                | `false`    |
| `--install-browsers`    | 先 `playwright install` 再跑               | `false`    |
| `--no-deps`             | 跳过 `pip install -r requirements.txt`     | `false`    |
| `--list-users`          | 打印当前 env 的 user_pool（诊断用）        | `false`    |
| `--pytest-args`         | 透传给 pytest 的额外参数                   |            |

示例：

```bash
# 冷启动跑 smoke，headless，3 次重试
python run.py --mode cold -m smoke --reruns 3

# 跑某个文件
python run.py tests/sqllab/test_sqllab.py

# 透传 -x（首次失败就停）
python run.py --pytest-args -x -v

# 在 6.0 上跑 health marker，并生成报告
python run.py --instance 6.0 -m health --allure

# 在 SIT 环境上跑 multi_user
python run.py --env sit -m multi_user

# 列出 SIT 环境的 user_pool
python run.py --env sit --list-users
```

## 标记 (markers)

| Marker        | 说明                  | 用例示例                          |
| ------------- | --------------------- | --------------------------------- |
| `smoke`       | 冒烟测试，必跑        | `test_health`、`test_login`       |
| `auth`        | 认证                  | `test_login.py`                   |
| `dashboard`   | 仪表盘                | `test_dashboards.py`              |
| `chart`       | 图表                  | `test_charts.py`                  |
| `sqllab`      | SQL Lab               | `test_sqllab.py`                  |
| `database`    | 数据库 / 数据集       | `test_databases.py`               |
| `health`      | 健康检查              | `test_health.py`                  |
| `slow`        | 耗时较长，可能跳过    | `test_run_simple_query`           |
| `multi_user`  | 多用户并发 E2E        | `tests/multi_user/test_multi_user_e2e.py` |

`smoke` 应保持稳定并 ≤ 5 分钟；`slow` 可在 CI 中按需运行；`multi_user` 需要 user_pool 有足够用户（viewer ≥ 5）。

## 编写新测试

### 基本模板

```python
import pytest


@pytest.mark.dashboard
@pytest.mark.smoke
def test_dashboard_list_loads(superset_instance, logged_in_page):
    """仪表盘列表能正常打开。"""
    page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    page.goto()
    page.wait_loaded()
    assert page.dashboard_count() > 0
```

要点：
1. **必须**使用参数化 fixture `superset_instance`（自动遍历 4.1 / 6.0）
2. **必须**使用 `logged_in_page`（已登录）或自己登录
3. **优先**通过 `pages/` 下的 Page Object 访问 UI，不要直接 `page.locator(...)`
4. **避免**硬编码等待时间，使用 `utils.stability.wait_for`
5. **失败时**自动附加截图到 Allure

### 跨版本兼容

4.1 是服务端渲染，6.0 是 SPA + Ant Design。Page Object 已封装兼容层，新测试只需调用高层 API。

```python
# 错误：硬编码选择器
page.locator(".css-xxx").click()  # 仅 4.1

# 正确：使用稳定选择器
robust_click(page, [".ant-btn", "button[type='submit']"])
```

### 跳过 vs 失败

`SQL Lab` 写操作需要 CSRF + JWT，UI 自动化易受 React 重渲染影响。对已知不稳定场景优先用 `pytest.skip` 而不是 `pytest.fail`，避免阻塞 CI。

```python
try:
    sl.run_query(timeout=60000)
except Exception as e:
    pytest.skip(f"SQL Lab UI flow failed: {e}")
```

## 配置与环境变量

### 配置文件 `config/config.yaml`

```yaml
mode: reuse                 # cold / reuse
cleanup_on_exit: true       # cold 模式结束后清理容器
admin_username: admin
admin_password: admin
browser: chromium
headless: true
page_timeout_ms: 30000
navigation_timeout_ms: 60000
reruns: 2
reruns_delay: 3
instances:
  - name: 4.1
    version: 4.1.1
    base_url: "http://localhost:18088"
    compose_dir: ../superset-4.1
    postgres_container: superset-4.1-postgres
    redis_container: superset-4.1-redis
  - name: 6.0
    version: 6.0.0
    base_url: "http://localhost:18089"
    compose_dir: ../superset-6.0
    postgres_container: superset-6.0-postgres
    redis_container: superset-6.0-redis
```

### 环境变量（优先级最高）

仓库根目录可放 `.env` 文件。

| 变量                     | 说明                          | 默认                            |
| ------------------------ | ----------------------------- | ------------------------------- |
| `E2E_MODE`               | cold / reuse                  | `reuse`                         |
| `E2E_BROWSER`            | chromium / firefox / webkit   | `chromium`                      |
| `E2E_HEADLESS`           | 1 / 0                         | `1`                             |
| `E2E_CLEANUP`            | cold 模式结束是否清理容器     | `1`                             |
| `E2E_RERUNS`             | 失败重试次数                  | `2`                             |
| `E2E_RERUNS_DELAY`       | 重试间隔（秒）                | `3`                             |
| `E2E_PAGE_TIMEOUT_MS`    | 页面操作超时                  | `30000`                         |
| `E2E_NAV_TIMEOUT_MS`     | 导航超时                      | `60000`                         |
| `E2E_ADMIN_USER`         | admin 用户名                  | `admin`                         |
| `E2E_ADMIN_PASSWORD`     | admin 密码                    | `admin`                         |
| `E2E_BASE_URL_4_1`       | 4.1 base URL                  | `http://localhost:18088`        |
| `E2E_BASE_URL_6_0`       | 6.0 base URL                  | `http://localhost:18089`        |
| `E2E_LOG_LEVEL`          | 日志级别                      | `INFO`                          |
| `E2E_ENV`                | dev / sit / uat / prod        | `dev`                           |
| `E2E_BASE_URL_<ENV>_<VER>` | env 维度 base URL 覆盖        | （与 yaml 一致）                |

## 多环境与多用户

E2E 与性能测试共用一套配置和用户池，支持 4 套环境（dev/sit/uat/prod）和 per-role 多用户池。

### 多环境分层配置

`config/` 下放 base + 各 env 覆盖：

```
config/
├── config.yaml          # base（dev）
├── config.sit.yaml      # SIT 覆盖
├── config.uat.yaml      # UAT 覆盖
└── config.prod.yaml     # PROD 覆盖
```

加载规则：`config.<env>.yaml` 深度合并到 `config.yaml` 之上，env 层优先级最高。env 段字段（`instances`、`user_pool`、`perf.thresholds` 等）按需覆盖。

切换环境：

```bash
# dev（默认）
python run.py -m smoke

# SIT
python run.py --env sit -m smoke
E2E_ENV=uat python run.py -m multi_user

# 打印当前 env 的 user_pool
python run.py --env sit --list-users
```

SIT/UAT/PROD 典型差异：

| 维度 | dev | sit | uat | prod |
| --- | --- | --- | --- | --- |
| `base_url` | localhost:18089 | sit.example.com | uat.example.com | prod.example.com |
| `user_pool.viewer` | 5 | 20 | 50 | 200+ |
| `perf.users` | 200 | 500 | 1000 | 2000 |
| `cleanup_on_exit` | true | false | false | false |

### 多用户池（per-role）

`config/config.yaml` 顶层 `user_pool` 段：

```yaml
user_pool:
  admin:
    - admin/admin
    - admin_ops_1/Admin#1234
  analyst:
    - alpha/Alpha#1234
    - beta/Beta#1234
  viewer:                          # 至少 5 个（支持 100+ VU 压测）
    - viewer1/Viewer#1234
    - viewer2/Viewer#1234
    - viewer3/Viewer#1234
    - viewer4/Viewer#1234
    - viewer5/Viewer#1234
  embed:
    - guest/Guest#1234
    - guest2/Guest#1234
```

支持两种格式：紧凑 `user/pass` 或详细 `{username, password, label}`。详细文档见 [config/README.md](./config/README.md)。

### 多用户 E2E fixture

`fixtures/playwright_fixtures.py` 提供两个工厂：

```python
from utils import page_actions as pa


def test_two_viewers_concurrent(login_as_role, superset_instance):
    """工厂 fixture：按角色拿不同 user，登录到独立 page。"""
    p1 = login_as_role("viewer", index=0)   # 固定 viewer[0]
    p2 = login_as_role("viewer", index=1)   # 固定 viewer[1]
    # 或 p3 = login_as_role("viewer")        # 随机 viewer


@pytest.mark.multi_user(3)
@pytest.mark.scenario("Multi-user", tags=("multi_user",))
def test_three_users(multi_user_pages, superset_instance):
    """参数化多用户 fixture：拿 N 个不同 user，每个一个 page。"""
    p1, p2, p3 = multi_user_pages
    # 验证 3 个 page 完全隔离
    for p in (p1, p2, p3):
        assert "/login/" not in p.url
```

`utils/user_pool.py::user_pool` 是单例，提供：

```python
from utils.user_pool import user_pool

viewer = user_pool.pick("viewer")                    # 随机
v1     = user_pool.pick("viewer", index=1)           # 索引
v2     = user_pool.pick("viewer", strategy="round_robin")  # 轮询
token  = user_pool.token_for(viewer, base_url)       # 线程安全 token 缓存
```

详细使用：[fixtures/README.md](./fixtures/README.md)、[utils/README.md](./utils/README.md)。

## 性能测试入口

`perf/` 子模块提供 Locust + k6 双框架性能测试，**与 E2E 共享配置和 user_pool**。

```bash
# 装依赖
pip install -r perf/requirements.txt
sudo apt-get install k6   # Linux；macOS: brew install k6

# Locust 200 VU / 10 min（默认 dev 6.0）
bash perf/tools/run_locust.sh

# Locust 在 SIT 环境跑（自动用 SIT 的 user_pool）
E2E_ENV=sit bash perf/tools/run_locust.sh

# k6 重点查询
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js   # 300 VU
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js       # 100 VU / 5 min

# 对比基线（strict 模式）
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail
```

完整文档：[perf/README.md](./perf/README.md)、[perf/PLAN.md](./perf/PLAN.md)、[perf/docs/MULTI_ENV_USER.md](./perf/docs/MULTI_ENV_USER.md)、[perf/docs/JENKINS.md](./perf/docs/JENKINS.md)。

## 稳定性策略

测试在 CI / 本地反复跑，框架已内置以下防护：

1. **失败重试**：`pytest-rerunfailures` 失败后默认重试 2 次，每次间隔 3 秒
2. **用例超时**：单用例 120s，防止挂死
3. **健壮选择器**：`utils/stability.py::robust_click` 尝试多个 selector
4. **轮询等待**：`wait_for` 函数代替 `page.wait_for_selector`，更可控
5. **自动等待**：Playwright locator 隐式等待
6. **失败截图**：失败时自动附加全屏截图 + HTML 到 Allure
7. **偶发错误容忍**：429 / Mapbox rate limit / 已知不稳定 SQL Lab 场景自动 skip
8. **跨版本 SPA / SSR 兼容**：Page Object 封装

## Allure 报告

### 自动分类（`reports/allure-results/categories.json`）

| 分类                              | 匹配规则                                              |
| --------------------------------- | ----------------------------------------------------- |
| Superset internal errors          | `query error / sqlalchemy / IntegrityError / NoSuchTable` |
| Network / Mapbox rate limit       | `429 / Mapbox / rate limit`                           |
| Service unavailable               | `Connection refused / Timeout / not running`          |
| Other failures                    | 兜底                                                  |
| Broken tests                      | 异常 / setup / teardown 失败                          |

### 自动标签

- `instance: 4.1` / `6.0` — 根据 `superset_instance` fixture 推断
- `version: 4.1.1` / `6.0.0`
- 全部 marker（`smoke` / `auth` / `dashboard` 等）

### 启动服务

```bash
# 实时查看（推荐）
allure serve reports/allure-results

# 生成 HTML（适合 CI 产物）
allure generate reports/allure-results -o reports/allure-report --clean
```

> 详细的报告查看方法（Allure / Locust HTML / k6 / 基线对比 / 容器 metrics）见
> [docs/REPORTS.md](./docs/REPORTS.md)。

## CI 集成

`.github/workflows/e2e.yml` 示例：

```yaml
name: E2E

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: Start Superset
        run: |
          cd superset-4.1 && docker compose up -d
          cd ../superset-6.0 && docker compose up -d
          # 等待 init 完成
          for d in superset-4.1 superset-6.0; do
            docker compose -f $d/docker-compose.yml wait superset-init || true
          done

      - name: Run E2E
        run: |
          cd e2e
          pip install -r requirements.txt
          playwright install --with-deps chromium
          python run.py --mode cold -m smoke --allure

      - name: Upload Allure
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: allure-results
          path: e2e/reports/allure-results
```

## 故障排查

| 症状                                          | 解决                                                                                 |
| --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `playwright install` 失败                     | Windows 不要加 `--with-deps`；手动下载浏览器到 `ms-playwright` 目录                   |
| `No module named 'config'`                    | 必须在 `e2e/` 目录下运行 `python run.py`                                             |
| 冷启动超时                                    | `init` 容器首次加载示例 4-5 分钟属正常；调整 `cold_start_instance` 中 `timeout=1800` |
| 测试 fail / 找不到元素                        | 查看 `reports/screenshots/` 全屏截图 + `reports/allure-results/` HTML 快照           |
| `Mapbox 429`                                  | 已知限流，框架已自动 skip；如需彻底解决请配置 `MAPBOX_API_KEY`                       |
| `CSRF token is missing`                       | 写操作（执行 SQL、保存仪表盘）需要 CSRF；当前 SQL Lab 写测试已 skip，需走 API 调用   |
| `Connection refused`                          | Superset 未启动或端口不对；先 `curl http://localhost:18088/health` 验证              |
| 浏览器下载慢                                  | 设置 `PLAYWRIGHT_DOWNLOAD_HOST` 镜像；或复用 `~/.cache/ms-playwright/` 已下载的浏览器 |
| Allure 命令找不到                             | `npm i -g allure-commandline` 或 `scoop install allure`                             |
| `unsupported E2E_ENV`                         | 只支持 dev / sit / uat / prod；写错时 `settings.current_env` 抛错                   |
| `user_pool empty` for role                    | `python run.py --list-users` 检查；SIT/UAT 需在 `config.<env>.yaml` 里写 user_pool |
| `login failed: 401` in multi_user             | 池里的用户名/密码与 env 不匹配；用 `--list-users` 校对                               |
| Locust/k6 找不到 user                         | 性能脚本会自动 fallback 到 admin；多用户需设 `E2E_ENV` 触发对应 env 配置             |

## 清理临时文件

测试运行会在 `reports/` 下生成临时产物（allure-results、截图、HTML 报告），这些文件已通过 `.gitignore` 忽略，不会进入版本控制。

手动清理：

```bash
# 清理测试产物（保留目录结构）
cd e2e
rm -rf reports/allure-results/* reports/allure-report/* reports/screenshots/*.png
touch reports/allure-results/.gitkeep reports/screenshots/.gitkeep

# 清理 Python 缓存
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .ruff_cache .mypy_cache

# 清理 Playwright 缓存（可选）
rm -rf .playwright
```

仓库中不应残留调试脚本（如 `debug_*.py`、`verify_*.py`），如需临时调试请放到 `e2e/` 之外或用完即删。

## 测试模块索引

| 模块                | 说明                                                     |
| ------------------- | -------------------------------------------------------- |
| `tests/health/`     | `/health`、登录页、CSRF endpoint 可用性                  |
| `tests/auth/`       | 登录、登出、admin 鉴权                                   |
| `tests/databases/`  | 数据库列表、SQL Alchemy URI、连接测试                    |
| `tests/charts/`     | 图表列表、单图表加载、Explore 编辑器                     |
| `tests/dashboards/` | 仪表盘列表、详情、图表嵌入、过滤器                       |
| `tests/sqllab/`     | SQL Lab 页面加载、数据库下拉、查询执行（CSRF 受限场景 skip） |
| `tests/import_export_alerts/` | 导入导出 / 告警                                |
| `tests/extras/`     | 补充测试（extras）                                       |
| `tests/settings/`   | RBAC / embed settings                                    |
| `tests/multi_user/` | 多用户并发 E2E（session 隔离 / 权限差异）                 |

## 性能测试索引

| 入口 | 说明 |
| --- | --- |
| `perf/README.md` | 总览 |
| `perf/PLAN.md` | 详细规划 |
| `perf/CHANGELOG.md` | 变更日志 |
| `perf/docs/MULTI_ENV_USER.md` | 多环境 / 多用户 |
| `perf/docs/JENKINS.md` | Jenkins 部署 |
