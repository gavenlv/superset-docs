# Superset E2E 自动化测试

针对 Superset 4.1 与 6.0 的端到端自动化测试框架。支持 UI（Playwright）+ API（httpx）+ 数据库多层验证；参数化双版本；冷启动 / 复用服务两种模式；Allure 报告 + 自动重试 + 失败截图。

## 目录

- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [运行模式](#运行模式)
- [CLI 工具（run.py）](#cli-工具runpy)
- [标记 (markers)](#标记-markers)
- [编写新测试](#编写新测试)
- [配置与环境变量](#配置与环境变量)
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

## 目录结构

```
e2e/
├── conftest.py                  # 顶层 fixture 入口（聚合 fixtures/）
├── run.py                       # CLI 入口
├── pyproject.toml               # pytest 配置 + 依赖
├── requirements.txt             # 显式依赖列表
├── pytest.ini 或 pyproject.toml
│
├── config/
│   ├── settings.py              # 配置加载（yaml + env）
│   └── config.yaml              # 默认配置（端口、超时、实例列表）
│
├── fixtures/
│   ├── conftest.py              # 服务生命周期 fixture（cold/reuse）
│   ├── playwright_fixtures.py   # 浏览器、context、登录 page
│   └── allure_config.py         # Allure 环境/分类 hook
│
├── pages/                       # Page Object Model
│   ├── login_page.py            # 登录（兼容 4.1 SSR / 6.0 SPA）
│   ├── dashboard_page.py        # 仪表盘列表 + 详情
│   ├── explore_page.py          # Explore 图表编辑
│   └── sqllab_page.py           # SQL Lab（兼容 ant-table 与 sql-result-table）
│
├── utils/
│   ├── process.py               # 子进程 + HTTP 等待工具
│   ├── service.py               # docker compose 编排（cold/reuse）
│   ├── stability.py             # 健壮选择器、轮询等待、健壮点击
│   └── logging.py               # 日志初始化
│
├── tests/                       # 测试用例
│   ├── conftest.py              # 测试级别 fixture 补充
│   ├── health/                  # 健康检查（/health、登录、CSRF）
│   ├── auth/                    # 登录 / 登出 / 权限
│   ├── dashboards/              # 仪表盘列表 / 详情 / 交互
│   ├── charts/                  # 单图表
│   ├── sqllab/                  # SQL Lab（页面、查询）
│   └── databases/               # 数据库 / 数据集
│
└── reports/                     # 运行时产物（已 gitignore）
    ├── allure-results/          # Allure 原始数据
    ├── allure-report/           # Allure HTML
    └── screenshots/             # 失败截图
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
```

## 标记 (markers)

| Marker      | 说明                  | 用例示例                          |
| ----------- | --------------------- | --------------------------------- |
| `smoke`     | 冒烟测试，必跑        | `test_health`、`test_login`       |
| `auth`      | 认证                  | `test_login.py`                   |
| `dashboard` | 仪表盘                | `test_dashboards.py`              |
| `chart`     | 图表                  | `test_charts.py`                  |
| `sqllab`    | SQL Lab               | `test_sqllab.py`                  |
| `database`  | 数据库 / 数据集       | `test_databases.py`               |
| `health`    | 健康检查              | `test_health.py`                  |
| `slow`      | 耗时较长，可能跳过    | `test_run_simple_query`           |

`smoke` 应保持稳定并 ≤ 5 分钟；`slow` 可在 CI 中按需运行。

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
