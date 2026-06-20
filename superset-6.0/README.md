# Superset 6.0

Superset 6.0.0 的完整本地环境，基于 `apache/superset:6.0.0` 镜像，包含 Web + Celery Worker + Init 三类服务。

## 目录

- [快速启动](#快速启动)
- [端口与服务](#端口与服务)
- [环境变量与配置](#环境变量与配置)
- [数据持久化](#数据持久化)
- [init 流程](#init-流程)
- [示例数据加载机制](#示例数据加载机制)
- [与 4.1 的差异](#与-41-的差异)
- [常见问题](#常见问题)

## 快速启动

```bash
cd superset-6.0
docker compose up -d

# 跟踪 init 进度（首次约 4-5 分钟）
docker compose logs -f superset-init
```

等待 `superset-init` 容器退出（`STATUS=Exited (0)`），随后 `superset` 和 `superset-worker` 容器将变为 `healthy` / `running`。

Web 入口：http://localhost:18089
默认账号：`admin / admin`

```bash
# 健康检查
curl http://localhost:18089/health   # OK

# 停止
docker compose down

# 完全清理（含数据卷）
docker compose down -v
```

## 端口与服务

| 服务                | 容器名                   | 主机端口 | 备注                          |
| ------------------- | ------------------------ | -------- | ----------------------------- |
| `superset`          | `superset-6.0`           | 18089    | Web UI                        |
| `superset-worker`   | `superset-6.0-worker`    | —        | Celery worker（SQL Lab 异步） |
| `superset-init`     | `superset-6.0-init`      | —        | 一次性初始化（完成即退出）    |
| `postgres`          | `superset-6.0-postgres`  | 15434    | 主库 + 示例数据               |
| `redis`             | `superset-6.0-redis`     | 16381    | 缓存 + Celery broker/results  |

可在 `docker-compose.yml` 中通过环境变量覆盖：

```yaml
POSTGRES_PORT=15434
REDIS_PORT=16381
SUPERSET_PORT=18089
```

## 环境变量与配置

### `docker-compose.yml` 关键环境变量

| 变量                            | 默认值                                                                       | 说明                                              |
| ------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------- |
| `SUPERSET_SECRET_KEY`           | `superset-6.0-secret-key-please-change-in-production`                       | Flask SECRET                                      |
| `SUPERSET_LOAD_EXAMPLES`        | `yes`                                                                        | 启用示例加载逻辑                                  |
| `SUPERSET_CONFIG_PATH`          | `/app/superset_config.py`                                                    | 配置文件路径                                      |
| `SUPERSET_EXAMPLES_BASE_URL`    | `https://raw.githubusercontent.com/apache-superset/examples-data/master/`    | 远程兜底源                                        |
| `EXAMPLES_DB_URI`               | `postgresql+psycopg2://superset:superset@postgres:5432/superset`             | examples 数据库连接串                             |
| `SUPERSET_LOCAL_SAMPLES_DIR`    | `/app/local_samples`                                                         | 本地示例数据目录                                  |
| `PATH`                          | `/app/.venv/bin:/usr/local/bin:/usr/bin:/bin`                                | 6.0 镜像用 uv，PATH 必须包含 venv                 |

### `superset_config.py`

相比 4.1 多出的项：

- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — Redis 0 号库
- `ENABLE_TEMPLATE_PROCESSING = True` — 启用 Jinja 模板
- `TALISMAN_ENABLED = False` — 关闭 CSP（仅本地）
- 相同的 `SQLALCHEMY_*`、`CACHE_*`、`WTF_CSRF_*`、`UPLOAD_FOLDER`

## 数据持久化

| 数据卷               | 容器内路径                  | 用途                          |
| -------------------- | --------------------------- | ----------------------------- |
| `superset_6_0_db`    | `/var/lib/postgresql/data`  | PostgreSQL 数据               |
| `superset_6_0_redis` | `/data`                     | Redis 持久化                  |
| `superset_6_0_data`  | `/app/superset_home`        | Superset 上传、SQL Lab 查询等 |

## init 流程

`superset-init` 容器以 `root` 身份执行：

```bash
uv pip install --python /app/.venv/bin/python --no-cache psycopg2-binary redis
superset db upgrade
superset init
(superset fab list-users | grep admin) ||
    superset fab create-admin ...
/app/.venv/bin/python /app/pythonpath/load_examples_init.py
echo 'INIT DONE'
```

`user: root` 是必须的：6.0 镜像用 uv 装的依赖位于 `/app/.venv`，默认用户无权写入。

详细：[`pythonpath/load_examples_init.py`](./pythonpath/load_examples_init.py)

## 示例数据加载机制

完全离线加载，无外网依赖。**与 4.1 的关键差异**：

4.1 的 `get_example_url` 用 `file://` URL 即可；6.0 的 YAML 配置中 `data` 字段走 `marshmallow.fields.URL()` 校验，**只接受 `http(s)://`**。

解决方案：`load_examples_init.py` 启动一个内置 HTTP 服务：

```python
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# 端口 18099，由 LOCAL_HTTP_PORT 控制
httpd = HTTPServer(("0.0.0.0", 18099), partial(SimpleHTTPRequestHandler, directory=LOCAL_SAMPLES_DIR))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

# 覆盖 BASE_URL，让 examples://xxx 转成 http://localhost:18099/xxx
_ex_helpers.BASE_URL = "http://localhost:18099/"
```

加载完成后，额外执行一次**图表 `query_context` 数据源 ID 修复**：

- 现象：部分 sales 图表 `query_context.datasource.id` ≠ `slice.datasource_id`，导致查询 "Columns missing"
- 修复：遍历所有含 `query_context` 的图表，强制把 `qc.datasource.id` 与 `slice.datasource_id` 对齐

## 与 4.1 的差异

| 维度         | 4.1                                    | 6.0                                            |
| ------------ | -------------------------------------- | ---------------------------------------------- |
| Worker       | 无                                     | 强制 Celery worker                             |
| 容器用户     | 默认 `superset`（UID 1000）            | `root`（写 `/app/.venv`）                      |
| Python       | 系统 Python                            | `/app/.venv/bin/python`（uv 管理）             |
| URL 校验     | 接受 `file://`                         | 强制 `http(s)://`（marshmallow）               |
| 前端         | 服务端渲染                             | SPA + Ant Design                               |
| 模板处理     | 默认开                                 | `ENABLE_TEMPLATE_PROCESSING` 显式开            |
| CSRF         | 大部分豁免                             | 写操作全部强制                                 |
| 图表 ID 修复 | 不需要                                 | 加载后自动对齐 `query_context.datasource.id`   |

## 常见问题

| 症状                                          | 解决                                                                                    |
| --------------------------------------------- | --------------------------------------------------------------------------------------- |
| `Permission denied: /app/.venv`               | 容器未以 `root` 运行；检查 `docker-compose.yml` 中 `user: root`                          |
| `uv: command not found`                       | 6.0 镜像自带 uv；确认用的是 `apache/superset:6.0.0` 而非 `4.1.x`                         |
| `Not a valid URL.` (yaml 校验失败)            | init 脚本未启动本地 HTTP 服务；查看 `[http] serving ...` 日志是否出现                  |
| `worker` 容器无法连接 redis                   | `depends_on.redis.condition: service_healthy` 满足后才启动；查看 `docker compose ps`   |
| 图表查询报 "Columns missing"                  | init 脚本中的图表 ID 修复逻辑未跑成功；查看 `[fix] fixed N chart datasource` 日志       |
| 前端 SPA 加载后空白                            | 浏览器 Console 报 JS 错误；F12 检查；考虑关闭浏览器缓存                                 |
