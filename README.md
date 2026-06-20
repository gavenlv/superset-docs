# superset-docs

Superset 4.1 与 6.0 双版本本地环境 + 端到端自动化测试。

## 目录结构

```
superset-docs/
├── README.md                  # 本文档
├── superset-4.1/              # Superset 4.1.1 完整环境
│   ├── README.md              # 4.1 子模块说明
│   ├── docker-compose.yml
│   ├── superset_config.py
│   └── pythonpath/load_examples_init.py
├── superset-6.0/              # Superset 6.0.0 完整环境（含 Celery worker）
│   ├── README.md
│   ├── docker-compose.yml
│   ├── superset_config.py
│   └── pythonpath/load_examples_init.py
├── example-data/              # 示例数据集（CSV/JSON，2 个版本共享）
│   ├── README.md
│   ├── datasets/examples/
│   ├── airports.csv.gz
│   └── ...
└── e2e/                       # 端到端自动化测试（pytest + Playwright + Allure）
    ├── README.md              # E2E 测试详细文档
    ├── run.py                 # CLI 入口
    ├── config/                # 配置
    ├── fixtures/              # pytest fixtures
    ├── pages/                 # Page Object Model
    ├── utils/                 # 工具函数
    ├── tests/                 # 测试用例
    └── reports/               # 报告输出（运行时生成）
```

## 端口分配

| 服务              | 4.1  | 6.0  | 备注                       |
| ----------------- | ---- | ---- | -------------------------- |
| Superset Web      | 18088 | 18089 | 用户访问端口              |
| PostgreSQL        | 15433 | 15434 | `localhost:<port>` 直连   |
| Redis             | 16380 | 16381 |                            |

两个版本使用独立端口与独立数据卷，可同时运行。

默认账号：`admin / admin`（由 init 容器自动创建）。

## 快速开始

### 前置要求

- Docker Desktop / Docker Engine 24+
- 至少 8 GB 可用内存（两个版本同时跑建议 12 GB+）
- 至少 10 GB 可用磁盘（命名卷、示例数据、Allure 报告）

### 启动 Superset 4.1

```bash
cd superset-4.1
docker compose up -d
docker compose logs -f superset-init   # 等待 init 完成（首次约 4-5 分钟）
```

Web 访问：http://localhost:18088

### 启动 Superset 6.0

```bash
cd superset-6.0
docker compose up -d
docker compose logs -f superset-init
```

Web 访问：http://localhost:18089

### 同时启动两个版本

```bash
cd superset-4.1 && docker compose up -d && cd ..
cd superset-6.0 && docker compose up -d && cd ..
```

启动后等待 `superset-init` 容器退出（`docker compose ps` 查看 `STATUS` 为 `Exited (0)`），Web 容器即会跟随启动并健康。

### 健康检查

```bash
# 4.1
curl http://localhost:18088/health

# 6.0
curl http://localhost:18089/health
```

返回 `OK` 表示 Web 服务可用。

## 数据持久化

每个版本都使用 **Docker 命名卷** 持久化：

| 数据卷                  | 用途                           |
| ----------------------- | ------------------------------ |
| `superset_4_1_db`       | 4.1 PostgreSQL 数据            |
| `superset_4_1_redis`    | 4.1 Redis 缓存                 |
| `superset_4_1_data`     | 4.1 Superset 上传文件、SQL Lab |
| `superset_6_0_db`       | 6.0 PostgreSQL 数据            |
| `superset_6_0_redis`    | 6.0 Redis 缓存                 |
| `superset_6_0_data`     | 6.0 Superset 上传文件、SQL Lab |

容器销毁后数据不丢失。`docker compose down` 不会删卷；如需完全清理请加 `-v`：

```bash
docker compose down -v   # ⚠️ 会删除所有数据
```

查看数据卷：

```bash
docker volume ls | grep superset
```

## 示例数据

仓库根目录的 [`example-data/`](./example-data) 包含 Superset 所有示例数据集，两个版本共享。

- **加载方式**：将 `example-data/` 挂载到 init 容器内的 `/app/local_samples`
- **数据源**：`load_examples_init.py` 在 `get_example_url` 之前优先匹配本地文件
- **网络兜底**：仍保留 `raw.githubusercontent.com` 作为离线加载失败时的备份源

完全清理（`docker compose down -v && up -d`）后重启即可自动加载示例数据，无需访问外网。

详细说明：[`example-data/README.md`](./example-data/README.md)

## 停止服务

```bash
# 停止 4.1
cd superset-4.1 && docker compose down && cd ..

# 停止 6.0
cd superset-6.0 && docker compose down && cd ..

# 完全清理（包括数据卷）
cd superset-4.1 && docker compose down -v && cd ..
cd superset-6.0 && docker compose down -v && cd ..
```

## E2E 自动化测试

[`e2e/`](./e2e) 目录提供针对两个版本的端到端自动化测试。

### 快速运行

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium

# 复用现有服务跑 smoke 测试
python run.py -m smoke

# 冷启动模式（先 down -v 再 up -d，从零加载示例数据）
python run.py --mode cold -m smoke

# 只跑 4.1
python run.py --instance 4.1

# 生成 Allure 报告
python run.py --allure
```

详细文档：[`e2e/README.md`](./e2e/README.md)

### 清理测试产物

```bash
cd e2e
rm -rf reports/allure-results/* reports/allure-report/* reports/screenshots/*.png
touch reports/allure-results/.gitkeep reports/screenshots/.gitkeep
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .ruff_cache .mypy_cache
```

## 子模块文档

- [`superset-4.1/README.md`](./superset-4.1/README.md) — 4.1 版本配置说明
- [`superset-6.0/README.md`](./superset-6.0/README.md) — 6.0 版本配置说明（含与 4.1 差异）
- [`example-data/README.md`](./example-data/README.md) — 示例数据加载机制
- [`e2e/README.md`](./e2e/README.md) — 端到端测试完整文档

## 常见问题

| 问题                              | 解决                                                                 |
| --------------------------------- | -------------------------------------------------------------------- |
| 端口被占用                        | 修改 `docker-compose.yml` 中 `POSTGRES_PORT/REDIS_PORT/SUPERSET_PORT` |
| init 容器失败                     | 查看 `docker compose logs superset-init`，确认 `INIT DONE` 是否出现  |
| 登录后看不到示例图表              | 确认 `example-data/` 已挂载到 `/app/local_samples`                   |
| Web 容器一直 restart              | 查看 `docker compose logs superset`，多为 `superset_config.py` 错误  |
| 想清空数据从零开始                | `docker compose down -v && docker compose up -d`                     |
| 想快速验证 API                    | `curl http://localhost:<port>/health`                                |

## 变更记录

| 日期       | 说明                                                                  |
| ---------- | --------------------------------------------------------------------- |
| 初始版本   | Superset 4.1 + 6.0 双环境 + E2E 测试框架                              |
| 2026-06-20 | 引入本地 `example-data/`，init 脚本从本地加载示例数据，去除外网依赖   |
| 2026-06-20 | E2E 测试增加 SQL Lab 跨版本兼容、6.0 SPA 适配、Allure 分类与报告      |
