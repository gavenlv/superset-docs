# superset-docs

Superset 4.1 与 6.0 双版本本地环境 + 端到端自动化测试 + 多环境多用户性能压测。

```
                ┌─────────────────────────────────────────────┐
                │           superset-docs (本仓库)            │
                │                                             │
                │   ┌───────────┐  ┌────────────┐  ┌───────┐  │
                │   │superset-4.1│  │superset-6.0│  │example│  │
                │   │  (Docker)  │  │  (Docker)  │  │ -data │  │
                │   └─────┬─────┘  └──────┬─────┘  └───┬───┘  │
                │         │               │            │      │
                │         └───────┬───────┘            │      │
                │                 ▼                    │      │
                │   ┌─────────────────────────────┐     │      │
                │   │   e2e/ (测试 + 性能)        │     │      │
                │   │  ┌──────┐ ┌──────┐ ┌──────┐ │     │      │
                │   │  │E2E UI│ │API   │ │Perf  │ │     │      │
                │   │  └──────┘ └──────┘ └──────┘ │     │      │
                │   └─────────────────────────────┘     │      │
                │                                     │      │
                │   dev / sit / uat / prod  (4 envs)   │      │
                │   multi-user pool  (10+ users/role)  │      │
                └─────────────────────────────────────────────┘
```

## 目录

- [核心特性](#核心特性)
- [目录结构](#目录结构)
- [端口分配](#端口分配)
- [快速开始](#快速开始)
- [E2E 自动化测试](#e2e-自动化测试)
- [性能测试 (P5)](#性能测试-p5)
- [多环境与多用户](#多环境与多用户)
- [CI/CD](#cicd)
- [子模块文档](#子模块文档)
- [常见问题](#常见问题)
- [变更记录](#变更记录)

## 核心特性

| 维度 | 覆盖 |
| --- | --- |
| **多版本** | Superset 4.1.1 + 6.0.0，参数化自动遍历 |
| **多环境** | dev / sit / uat / prod 4 档，配置独立 |
| **多用户** | per-role 用户池（admin/analyst/viewer/embed），支持 200+ VU |
| **E2E UI** | Playwright 自动化（4.1 SSR / 6.0 SPA 兼容） |
| **E2E API** | httpx 调用，含 CSRF + JWT |
| **E2E 多用户** | 工厂 fixture，按角色拿不同 user 跑并发 |
| **性能压测** | Locust（4 角色 28 task）+ k6（9 脚本 重点查询） |
| **基线对比** | p50/p95/p99 + error rate，critical 端点严格阈值 |
| **报告** | Allure HTML + Locust 原生 + k6 JSON + docker stats CSV |
| **CI** | GitHub Actions（PR/nightly/release）+ Jenkins（4 档） |

## 目录结构

```
superset-docs/
├── README.md                          # 本文档
├── Jenkinsfile                        # Jenkins Pipeline（perf + E2E）
├── .github/workflows/perf.yml         # GitHub Actions（perf）
│
├── superset-4.1/                      # Superset 4.1.1 完整环境
│   ├── README.md
│   ├── docker-compose.yml
│   ├── superset_config.py
│   └── pythonpath/load_examples_init.py
│
├── superset-6.0/                      # Superset 6.0.0 完整环境
│   ├── README.md
│   ├── docker-compose.yml
│   ├── superset_config.py
│   └── pythonpath/load_examples_init.py
│
├── example-data/                      # 示例数据集（2 版本共享，离线加载）
│
└── e2e/                               # 端到端 + 性能测试套件
    ├── README.md                      # E2E 详细文档
    ├── docs/QUICKSTART.md             # 一页式快速开始
    ├── run.py                         # CLI 入口（支持 --env）
    ├── conftest.py                    # 顶层 fixture
    ├── pyproject.toml
    ├── requirements.txt
    │
    ├── config/                        # 配置（多环境分层）
    │   ├── README.md
    │   ├── config.yaml                # base（dev）
    │   ├── config.sit.yaml            # SIT
    │   ├── config.uat.yaml            # UAT
    │   ├── config.prod.yaml           # PROD
    │   └── settings.py
    │
    ├── fixtures/                      # pytest fixtures
    │   ├── README.md
    │   ├── conftest.py
    │   ├── playwright_fixtures.py     # 含多用户 fixture
    │   └── allure_config.py
    │
    ├── pages/                         # Page Object
    │   ├── login_page.py
    │   ├── dashboard_page.py
    │   ├── explore_page.py
    │   └── sqllab_page.py
    │
    ├── utils/                         # 工具
    │   ├── README.md
    │   ├── api.py                     # API helper
    │   ├── bdd.py                     # Given/When/Then
    │   ├── page_actions.py            # 高亮 Playwright 包装
    │   ├── stability.py               # 健壮选择器 / 轮询
    │   ├── process.py                 # 子进程
    │   ├── service.py                 # docker compose 编排
    │   ├── logging.py
    │   └── user_pool.py               # 多用户池（NEW）
    │
    ├── tests/                         # E2E 用例
    │   ├── README.md
    │   ├── health/
    │   ├── auth/
    │   ├── dashboards/
    │   ├── charts/
    │   ├── sqllab/
    │   ├── databases/
    │   ├── import_export_alerts/
    │   ├── extras/
    │   ├── settings/
    │   └── multi_user/                # 多用户 E2E（NEW）
    │       └── test_multi_user_e2e.py
    │
    ├── spec/                          # BDD feature 文件
    │
    ├── reports/                       # 运行时产物
    │
    └── perf/                          # 性能测试（P5）
        ├── README.md
        ├── PLAN.md                    # 详细规划
        ├── CHANGELOG.md               # 变更日志
        ├── docs/
        │   ├── JENKINS.md             # Jenkins 部署
        │   └── MULTI_ENV_USER.md      # 多环境/多用户
        ├── requirements.txt
        ├── common/                    # 6 个共享模块
        ├── locust/                    # Locust 4 角色 + LoginStorm
        ├── k6/scripts/                # 9 个 k6 脚本
        ├── baselines/                 # 基线 JSON
        ├── reports/                   # 压测报告
        ├── tools/                     # 辅助脚本
        └── tests/                     # 元测试
```

## 端口分配

| 服务              | 4.1    | 6.0    | 备注                       |
| ----------------- | ------ | ------ | -------------------------- |
| Superset Web      | 18088  | 18089  | 用户访问端口              |
| PostgreSQL        | 15433  | 15434  | `localhost:<port>` 直连   |
| Redis             | 16380  | 16381  |                            |

两个版本使用独立端口与独立数据卷，可同时运行。默认账号：`admin / admin`。

## 快速开始

### 1. 前置要求

- Docker Desktop / Docker Engine 24+
- Python 3.10+（推荐 3.12）
- 8 GB 可用内存（两版本同时跑建议 12 GB+）
- 10 GB 可用磁盘

### 2. 启动 Superset（首次约 5 min）

```bash
# 启动 4.1
cd superset-4.1 && docker compose up -d
# 启动 6.0
cd ../superset-6.0 && docker compose up -d

# 等 init 容器退出
docker compose -f superset-4.1/docker-compose.yml ps
docker compose -f superset-6.0/docker-compose.yml ps
# STATUS = Exited (0) 时 Web 才健康
```

### 3. 验证健康

```bash
curl http://localhost:18088/health   # 4.1 → OK
curl http://localhost:18089/health   # 6.0 → OK
```

### 4. 跑 E2E smoke 测试

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium

# 复用现有服务跑 smoke（首次推荐）
python run.py -m smoke

# 冷启动（先 down -v 再 up -d，从零加载示例）
python run.py --mode cold -m smoke

# 只跑 6.0
python run.py --instance 6.0 -m smoke
```

### 5. 跑性能压测

```bash
cd e2e
pip install -r perf/requirements.txt

# Locust 200 VU / 10 min（默认 dev 6.0）
bash perf/tools/run_locust.sh

# k6 重点查询
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js
```

更详细的步骤见 [`e2e/docs/QUICKSTART.md`](./e2e/docs/QUICKSTART.md)。

## E2E 自动化测试

[`e2e/`](./e2e) 目录提供针对两个版本的端到端自动化测试。

### 关键命令

```bash
cd e2e

# 复用模式（默认）
python run.py -m smoke

# 冷启动模式
python run.py --mode cold -m smoke

# 限定版本
python run.py --instance 4.1
python run.py --instance 6.0

# 关键字过滤
python run.py -k dashboard

# 跑全部 + 生成 Allure
python run.py --allure

# 多用户并发
python run.py -m multi_user
```

详细文档：[`e2e/README.md`](./e2e/README.md)

## 性能测试 (P5)

[`e2e/perf/`](./e2e/perf) 提供两套互补的性能测试方案。

| 框架 | 用途 | 重点 |
| --- | --- | --- |
| **Locust** | 多角色真实用户行为 | 4 角色 28 task，模拟生产 |
| **k6** | 高并发专项 | 9 脚本 重点查询（dashboard / charts / chart_data） |

### 5 分钟快速跑

```bash
cd e2e
pip install -r perf/requirements.txt
# 安装 k6（Linux）
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 \
    --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Locust 200 VU / 10 min
bash perf/tools/run_locust.sh
# → 报告输出到 perf/reports/locust/

# k6 重点
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js  # 300 VU
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js       # 100 VU
# → 报告输出到 perf/reports/k6/
```

### 基线对比

```bash
# 对比当前结果 vs 基线（strict 模式重点超阈值即 fail）
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail

# 存为新基线
python perf/tools/save_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --note "200 VU / 10 min cold-start"
```

详细文档：[`e2e/perf/README.md`](./e2e/perf/README.md) | [`e2e/perf/PLAN.md`](./e2e/perf/PLAN.md)

## 多环境与多用户

支持 4 套环境（dev / sit / uat / prod）和 per-role 多用户池（用于 200+ VU 并发）。

### 切换环境

```bash
# dev（默认）
python run.py -m smoke

# SIT
python run.py --env sit -m smoke

# UAT
E2E_ENV=uat python run.py -m multi_user

# 列出当前 env 的 user_pool
python run.py --list-users --env sit
```

### 多用户压测

```bash
# Locust 自动从 user_pool 分配用户
E2E_ENV=sit bash perf/tools/run_locust.sh

# k6 多用户（用 viewer 池）
E2E_ENV=sit bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js --multi-user viewer
```

详细文档：[`e2e/perf/docs/MULTI_ENV_USER.md`](./e2e/perf/docs/MULTI_ENV_USER.md)

## CI/CD

| 系统 | 入口 | 用途 |
| --- | --- | --- |
| **GitHub Actions** | [`.github/workflows/perf.yml`](./.github/workflows/perf.yml) | 外部 PR / 社区 |
| **Jenkins** | [`Jenkinsfile`](./Jenkinsfile) | 公司内网，4 档参数化 |

Jenkins 详细部署：[`e2e/perf/docs/JENKINS.md`](./e2e/perf/docs/JENKINS.md)

## 子模块文档

| 模块 | 文档 |
| --- | --- |
| Superset 4.1 容器 | [`superset-4.1/README.md`](./superset-4.1/README.md) |
| Superset 6.0 容器 | [`superset-6.0/README.md`](./superset-6.0/README.md) |
| 示例数据 | [`example-data/README.md`](./example-data/README.md) |
| E2E 测试 | [`e2e/README.md`](./e2e/README.md) |
| E2E 一页式入门 | [`e2e/docs/QUICKSTART.md`](./e2e/docs/QUICKSTART.md) |
| E2E 配置 | [`e2e/config/README.md`](./e2e/config/README.md) |
| E2E Fixtures | [`e2e/fixtures/README.md`](./e2e/fixtures/README.md) |
| E2E Utils | [`e2e/utils/README.md`](./e2e/utils/README.md) |
| 性能测试 | [`e2e/perf/README.md`](./e2e/perf/README.md) |
| 性能规划 | [`e2e/perf/PLAN.md`](./e2e/perf/PLAN.md) |
| 性能 changelog | [`e2e/perf/CHANGELOG.md`](./e2e/perf/CHANGELOG.md) |
| 性能报告说明 | [`e2e/perf/reports/README.md`](./e2e/perf/reports/README.md) |
| Jenkins 部署 | [`e2e/perf/docs/JENKINS.md`](./e2e/perf/docs/JENKINS.md) |
| 多环境/多用户 | [`e2e/perf/docs/MULTI_ENV_USER.md`](./e2e/perf/docs/MULTI_ENV_USER.md) |

## 示例结果（Demo）

仓库自带最近一次基线压测的产物，**直接打开看效果**：

| 文件 | 链接 |
| --- | --- |
| Locust 表格化汇总（200 VU / 120s） | [`e2e/perf/reports/locust/summary_6.0.txt`](./e2e/perf/reports/locust/summary_6.0.txt) |
| Locust HTML 报告 | [`e2e/perf/reports/locust/report_6.0.html`](./e2e/perf/reports/locust/report_6.0.html) |
| Locust JSON 快照 | [`e2e/perf/reports/locust/current_6.0.json`](./e2e/perf/reports/locust/current_6.0.json) |
| 6.0 基线 JSON | [`e2e/perf/baselines/v6_0.json`](./e2e/perf/baselines/v6_0.json) |
| 4.1 基线 JSON | [`e2e/perf/baselines/v4_1.json`](./e2e/perf/baselines/v4_1.json) |

> 完整解读见 [`e2e/perf/reports/README.md`](./e2e/perf/reports/README.md#60-实测结果示例)。

## 常见问题

| 问题 | 解决 |
| --- | --- |
| 端口被占用 | 修改 `docker-compose.yml` 中 `POSTGRES_PORT/REDIS_PORT/SUPERSET_PORT` |
| init 容器失败 | `docker compose logs superset-init`，确认 `INIT DONE` |
| 登录后看不到示例 | 确认 `example-data/` 已挂载到 `/app/local_samples` |
| Web 一直 restart | `docker compose logs superset`，多为 `superset_config.py` 错误 |
| 清空数据 | `docker compose down -v && docker compose up -d` |
| 快速验证 API | `curl http://localhost:<port>/health` |
| `playwright install` 失败 | Windows 不要加 `--with-deps`；手动下浏览器到 ms-playwright 目录 |
| `No module named 'config'` | 必须在 `e2e/` 目录跑 `python run.py` |
| 冷启动超时 | 首次 4-5 min 属正常，可调 `cold_start_instance` timeout |
| `CSRF token is missing` | 写操作（执行 SQL）需要 CSRF，走 API 调用 |
| `Mapbox 429` | 已知限流，框架自动 skip；可配 `MAPBOX_API_KEY` |
| `k6: not found` | `apt-get install k6` 或 `brew install k6` |
| `locust: GBK 错误` | Windows 设 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` |
| `user_pool empty` | `python run.py --list-users` 检查配置；SIT/UAT 需写 `config.<env>.yaml` |
| `404 /api/v1/dashboard/{id}/charts/` | 6.0 路径不带尾斜杠，参见 `e2e/perf/PLAN.md` §5.2 |

## 变更记录

| 日期       | 说明                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------ |
| 初始版本   | Superset 4.1 + 6.0 双环境 + E2E 测试框架                                                   |
| 2026-06-20 | 引入本地 `example-data/`，init 脚本从本地加载示例数据，去除外网依赖                        |
| 2026-06-20 | E2E 增加 SQL Lab 跨版本兼容、6.0 SPA 适配、Allure 分类与报告                              |
| 2026-06-21 | P5 性能测试套件：Locust + k6 + 基线对比，重点查询 70%+ RPS                                |
| 2026-06-21 | Jenkins Pipeline：4 档参数化（pr-gate/nightly/release/smoke）                              |
| 2026-06-21 | 多环境/多用户：`config.{dev,sit,uat,prod}.yaml` + `user_pool` + 多用户 fixture & 压测    |
| 2026-06-21 | 文档体系：完善 README / config / fixtures / utils / reports，新增 QUICKSTART 一页式指南    |
