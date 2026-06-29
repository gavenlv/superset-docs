# 离线示例数据导入指南

> 在没有外网访问的环境下，如何将本地 example-data 导入到 Superset 中。

## 目录

- [问题背景](#问题背景)
- [方案概述](#方案概述)
- [Docker 环境（推荐）](#docker-环境推荐)
- [源码启动环境](#源码启动环境)
- [核心机制详解](#核心机制详解)
- [重新加载示例数据](#重新加载示例数据)
- [添加自定义数据集](#添加自定义数据集)
- [常见问题](#常见问题)
- [快速检查清单](#快速检查清单)

---

## 问题背景

默认情况下，Superset 从 GitHub 下载 examples 数据：

- 网络不稳定时下载失败
- GitHub 在某些地区访问受限
- 企业内网环境无法访问外网

**解决方案**：将 examples 数据放在本地，通过 Docker Volume 挂载到容器，实现完全离线加载。

---

## 方案概述

```
本地 example-data/
       ↓
Docker Volume 挂载
       ↓
容器内 /app/local_samples/
       ↓
load_examples_init.py 覆盖 BASE_URL
       ↓
Superset 从本地读取数据（无需外网）
```

### 数据目录结构

```
superset-docs/
├── example-data/              ← 示例数据文件（CSV/JSON）
│   ├── airports.csv.gz
│   ├── birth_names.csv
│   ├── energy.json.gz
│   ├── sales.csv
│   ├── countries.json.gz
│   └── datasets/examples/
│       ├── covid_vaccines.csv
│       └── slack/
│           ├── channels.csv
│           └── messages.csv
├── superset-4.1/
│   ├── docker-compose.yml
│   └── pythonpath/
│       └── load_examples_init.py
└── superset-6.0/
    ├── docker-compose.yml
    └── pythonpath/
        └── load_examples_init.py
```

---

## Docker 环境（推荐）

### 步骤 1：确认数据目录

确保 `example-data/` 目录包含以下核心文件：

| 文件 | 用途 |
|------|------|
| `birth_names.csv` | 时间序列图表 |
| `energy.json.gz` | 雷达图 |
| `sales.csv` | 销售仪表盘 |
| `countries.json.gz` | 地图 |
| `datasets/examples/slack/` | 多表关联 |

### 步骤 2：启动 Superset

**启动 Superset 4.1**：

```bash
cd superset-4.1
docker compose up -d

# 查看初始化进度（首次约 4-5 分钟）
docker compose logs -f superset-init
```

**启动 Superset 6.0**：

```bash
cd superset-6.0
docker compose up -d

docker compose logs -f superset-init
```

### 步骤 3：关键配置解析

`docker-compose.yml` 中的核心配置：

```yaml
# 环境变量
SUPERSET_LOCAL_SAMPLES_DIR: "/app/local_samples"   # 本地数据目录（容器内路径）
EXAMPLES_DB_URI: "postgresql+psycopg2://superset:superset@postgres:5432/superset"

# Volume 挂载（将本地 example-data 挂载到容器）
volumes:
  - ../example-data:/app/local_samples:ro    # 只读挂载，不修改源文件
```

### 步骤 4：验证加载结果

```bash
# 方法 1：检查日志中是否有 "[done] example data loaded"
docker compose logs superset-init | grep "done"

# 方法 2：检查数据库中的示例表
docker exec superset-4.1-postgres psql -U superset -d superset -c "\dt" | grep -E "birth|energy|sales"

# 方法 3：登录 Web UI 查看
# http://localhost:18088 (4.1) 或 http://localhost:18089 (6.0)
# 账号：admin / admin
```

---

## 源码启动环境

如果您在本地直接运行 Superset 源码（非 Docker），需要额外配置。

### 步骤 1：环境准备

```bash
# 1. 确保本地安装了 PostgreSQL 和 Redis
# PostgreSQL: 端口 5432，数据库 superset，用户 superset/superset
# Redis: 端口 6379

# 2. 设置环境变量
export SUPERSET_LOCAL_SAMPLES_DIR="/path/to/example-data"
export EXAMPLES_DB_URI="postgresql+psycopg2://superset:superset@localhost:5432/superset"
export SQLALCHEMY_DATABASE_URI="postgresql+psycopg2://superset:superset@localhost:5432/superset"
export SQLALCHEMY_EXAMPLES_URI="postgresql+psycopg2://superset:superset@localhost:5432/superset"
export REDIS_HOST="localhost"
export REDIS_PORT=6379
```

### 步骤 2：配置 superset_config.py

在您的 Superset 源码目录中创建或修改 `superset_config.py`：

```python
# superset_config.py
import os

SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+psycopg2://superset:superset@localhost:5432/superset"
)

SQLALCHEMY_EXAMPLES_URI = os.environ.get(
    "SQLALCHEMY_EXAMPLES_URI",
    "postgresql+psycopg2://superset:superset@localhost:5432/superset"
)

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

SECRET_KEY = "your-secret-key-change-in-production"

# 缓存配置
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
}
DATA_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_data_"}
FILTER_STATE_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_filter_"}
```

### 步骤 3：修改 load_examples_init.py（关键）

从 `superset-4.1/pythonpath/load_examples_init.py` 或 `superset-6.0/pythonpath/load_examples_init.py` 复制脚本后，**必须修改数据库主机名**：

```python
# 修改前（Docker 环境）
EXAMPLES_DB_URI = os.environ.get(
    "EXAMPLES_DB_URI",
    "postgresql+psycopg2://superset:superset@postgres:5432/superset"  # ← postgres
)

# 修改后（本地源码环境）
EXAMPLES_DB_URI = os.environ.get(
    "EXAMPLES_DB_URI",
    "postgresql+psycopg2://superset:superset@localhost:5432/superset"  # ← localhost
)
```

> ⚠️ **原因**：Docker 环境中 `postgres` 是容器名，通过 Docker 网络解析。本地环境需要改为 `localhost`。

### 步骤 4：运行初始化脚本

```bash
# Superset 4.1
python load_examples_init.py

# Superset 6.0 - 需要用 venv 中的 Python
# 假设 venv 在 ~/superset/.venv
~/superset/.venv/bin/python load_examples_init.py
```

### 步骤 5：启动 Superset

```bash
# 4.1
superset run -h 0.0.0.0 -p 8088

# 6.0
superset run -h 0.0.0.0 -p 8088 --with-threads
```

---

## 核心机制详解

### 4.1 vs 6.0 的差异

| 维度 | Superset 4.1 | Superset 6.0 |
|------|-------------|-------------|
| **数据协议** | `file://` URL | `http://localhost:18099/` |
| **原因** | `get_example_url` 不校验 URL | `marshmallow.fields.URL()` 强制 http(s) |
| **处理方式** | 直接替换 `get_example_url` 返回 `file://` | 在容器内启动临时 HTTP 服务 |
| **额外修复** | 无 | 修复图表 `query_context.datasource.id` 不一致 |

### load_examples_init.py 执行流程

```python
# 1. 创建 Flask app context
app = create_app()
with app.app_context():
    # 2. 覆盖 BASE_URL（指向本地目录）
    import superset.examples.helpers as _ex_helpers
    _ex_helpers.BASE_URL = WORKING_BASE
    
    # 3. 修复 examples 数据库 URI（SQLite → PostgreSQL）
    examples_db.sqlalchemy_uri = EXAMPLES_DB_URI
    
    # 4. 修复表元数据 schema（main → public）
    for t in stale_tables:
        t.schema = physical_default_schema
    
    # 5. 调用 load_examples_run() 加载数据
    load_examples_run()
    
    # 6. 6.0 额外：修复图表 datasource_id
    for slc in mismatched:
        qc["datasource"]["id"] = slc.datasource_id
```

### 为什么需要修复数据库 URI？

默认情况下，`superset init` 会创建 SQLite 数据库 `/app/superset_home/examples.db`，但：

1. **init 容器与 web 容器的 `superset_home` 目录不同**，数据会丢失
2. **SQLite 默认 schema 是 `main`**，而 PostgreSQL 默认是 `public`，导致元数据不一致
3. **PostgreSQL 支持并发访问**，适合多容器环境

### 6.0 为什么需要本地 HTTP 服务？

6.0 的 YAML 配置中 `data` 字段使用 `marshmallow.fields.URL()` 校验，**只接受 `http(s)://`** 协议，不支持 `file://`。

解决方案：在 init 脚本中启动一个临时 HTTP 服务（端口 18099），让 `BASE_URL` 指向 `http://localhost:18099/`。

### 关于 SUPERSET_EXAMPLES_BASE_URL

`SUPERSET_EXAMPLES_BASE_URL` 是一个**回退 URL**，当本地数据文件缺失时，Superset 会尝试从该 URL 下载。

```yaml
# docker-compose.yml 中的配置
SUPERSET_EXAMPLES_BASE_URL: "https://raw.githubusercontent.com/apache-superset/examples-data/master/"
```

> 💡 **在完全离线（Air-Gapped）环境中**：这个变量实际上**不生效**。只要 `SUPERSET_LOCAL_SAMPLES_DIR` 已设置且数据完整，`load_examples_init.py` 会直接使用本地文件，不会尝试访问 GitHub。因此在纯内网环境中，可以放心保留此配置，它不会导致网络请求失败。

---

## 重新加载示例数据

如需重新加载（例如添加了新数据集）：

```bash
# 方法 1：完全重建（清空数据卷）
docker compose down -v
docker compose up -d

# 方法 2：只重新运行 init 容器
docker compose up --force-recreate superset-init

# 方法 3：手动在容器内执行
docker exec -it superset-4.1 bash
python /app/pythonpath/load_examples_init.py
```

---

## 添加自定义数据集

### 步骤 1：准备数据文件

将 CSV 或 JSON 文件放入 `example-data/` 目录：

```bash
# 示例：添加自定义销售数据
cp my_sales_data.csv example-data/

# 或放入子目录
cp custom_data.csv example-data/datasets/examples/
```

### 步骤 2：重建容器

```bash
docker compose down -v
docker compose up -d
```

### 步骤 3：验证新数据

登录 Web UI → Data → Datasets，查看新添加的数据集。

---

## 常见问题

### Q1：init 容器一直 Running，不退出？

```bash
# 查看详细日志
docker compose logs -f superset-init

# 可能原因：本地数据文件缺失，正在尝试从 GitHub 下载
# 解决方案：确认 example-data 目录完整，包含所有需要的文件
```

### Q2：启动后看不到示例图表？

```bash
# 检查 examples 数据库是否指向 PostgreSQL
# 登录 Web UI → Data → Databases → examples
# 确认 SQLAlchemy URI 是 postgresql+psycopg2://...

# 手动修复
docker exec -it superset-4.1 bash
python /app/pythonpath/load_examples_init.py
```

### Q3：6.0 报 "Not a valid URL" 错误？

```bash
# 检查日志中是否有 "[http] serving ..."
docker compose logs superset-init | grep http

# 原因：本地 HTTP 服务未启动
# 解决方案：确认容器以 root 用户运行（6.0 需要写 venv）
```

### Q4：如何切换在线/离线模式？

修改 `docker-compose.yml` 中的 `SUPERSET_LOCAL_SAMPLES_DIR`：

```yaml
# 离线模式（默认）
SUPERSET_LOCAL_SAMPLES_DIR: "/app/local_samples"

# 在线模式（从 GitHub 下载）
# SUPERSET_LOCAL_SAMPLES_DIR: ""  # 注释掉或设为空
```

### Q5：示例数据存放在哪里？

数据存储在 PostgreSQL 数据库中，不是文件系统。Volume `superset_4_1_db`（或 `superset_6_0_db`）持久化了数据库数据。

### Q6：如何完全清空数据？

```bash
# 删除所有数据卷（数据库、Redis、上传文件）
docker compose down -v

# 重新启动（会重新创建所有数据）
docker compose up -d
```

---

## 快速检查清单

启动前确认：

- [ ] `example-data/` 目录完整（包含 `birth_names.csv`, `energy.json.gz` 等）
- [ ] `docker-compose.yml` 中 `SUPERSET_LOCAL_SAMPLES_DIR` 已设置
- [ ] Volume 挂载路径正确：`../example-data:/app/local_samples:ro`
- [ ] PostgreSQL 和 Redis 服务正常运行
- [ ] 6.0 版本容器使用 `user: root`

启动后验证：

- [ ] `docker compose ps` 显示 `superset-init` 状态为 `Exited (0)`
- [ ] `docker compose logs superset-init` 包含 `[done] example data loaded`
- [ ] Web UI 可正常访问并看到示例图表
- [ ] `docker compose ps` 显示 `superset` 状态为 `healthy`

---

## 参考文件

| 文件 | 说明 |
|------|------|
| [example-data/README.md](../../example-data/README.md) | 数据文件清单和来源 |
| [superset-4.1/docker-compose.yml](../../superset-4.1/docker-compose.yml) | 4.1 Docker 配置 |
| [superset-6.0/docker-compose.yml](../../superset-6.0/docker-compose.yml) | 6.0 Docker 配置 |
| [superset-4.1/pythonpath/load_examples_init.py](../../superset-4.1/pythonpath/load_examples_init.py) | 4.1 加载脚本 |
| [superset-6.0/pythonpath/load_examples_init.py](../../superset-6.0/pythonpath/load_examples_init.py) | 6.0 加载脚本 |