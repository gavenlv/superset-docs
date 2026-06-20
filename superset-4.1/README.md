# Superset 4.1

Superset 4.1.1 的完整本地环境，基于 `apache/superset:4.1.1` 镜像。

## 目录

- [快速启动](#快速启动)
- [端口与服务](#端口与服务)
- [环境变量与配置](#环境变量与配置)
- [数据持久化](#数据持久化)
- [init 流程](#init-流程)
- [示例数据加载机制](#示例数据加载机制)
- [与 6.0 的差异](#与-60-的差异)
- [常见问题](#常见问题)

## 快速启动

```bash
cd superset-4.1
docker compose up -d

# 跟踪 init 进度（首次约 4-5 分钟）
docker compose logs -f superset-init
```

等待 `superset-init` 容器退出（`STATUS=Exited (0)`），随后 `superset` 容器将变为 `healthy`。

Web 入口：http://localhost:18088
默认账号：`admin / admin`

```bash
# 健康检查
curl http://localhost:18088/health   # OK

# 停止
docker compose down

# 完全清理（含数据卷）
docker compose down -v
```

## 端口与服务

| 服务            | 容器名                  | 主机端口 | 备注                  |
| --------------- | ----------------------- | -------- | --------------------- |
| `superset`      | `superset-4.1`          | 18088    | Web UI                |
| `postgres`      | `superset-4.1-postgres` | 15433    | 主库 + 示例数据       |
| `redis`         | `superset-4.1-redis`    | 16380    | 缓存                  |
| `superset-init` | `superset-4.1-init`     | —        | 一次性初始化（完成即退出） |

可在 `docker-compose.yml` 中通过环境变量覆盖：

```yaml
POSTGRES_PORT=15433   # 默认
REDIS_PORT=16380      # 默认
SUPERSET_PORT=18088   # 默认
```

## 环境变量与配置

### `docker-compose.yml` 关键环境变量

| 变量                            | 默认值                                                                       | 说明                                            |
| ------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------- |
| `SUPERSET_SECRET_KEY`           | `superset-4.1-secret-key-please-change-in-production`                       | Flask SECRET，生产环境必须修改                  |
| `SUPERSET_LOAD_EXAMPLES`        | `yes`                                                                        | 启用 `superset load_examples` 逻辑              |
| `SUPERSET_CONFIG_PATH`          | `/app/superset_config.py`                                                    | 配置文件路径                                    |
| `SUPERSET_EXAMPLES_BASE_URL`    | `https://raw.githubusercontent.com/apache-superset/examples-data/master/`    | 远程兜底源（本地数据缺失时使用）                |
| `EXAMPLES_DB_URI`               | `postgresql+psycopg2://superset:superset@postgres:5432/superset`             | examples 数据库连接串                           |
| `SUPERSET_LOCAL_SAMPLES_DIR`    | `/app/local_samples`                                                         | 本地示例数据目录（见 `load_examples_init.py`）  |

### `superset_config.py`

通过 bind mount 挂载到容器 `/app/superset_config.py`：

- `SQLALCHEMY_DATABASE_URI` — 主库（PostgreSQL）
- `SQLALCHEMY_EXAMPLES_URI` — 示例库（PostgreSQL），避免 init/web 容器共享 SQLite 路径
- `CACHE_CONFIG` / `DATA_CACHE_CONFIG` / `FILTER_STATE_CACHE_CONFIG` — Redis 缓存
- `WTF_CSRF_ENABLED` + `WTF_CSRF_EXEMPT_LIST` — CSRF 豁免 `/superset/views/core.log` 与图表数据接口
- `UPLOAD_FOLDER` / `SQLLAB_CTAS_NO_LIMIT` — 文件上传与 SQL Lab 配置

## 数据持久化

使用 Docker 命名卷：

| 数据卷               | 容器内路径                  | 用途                          |
| -------------------- | --------------------------- | ----------------------------- |
| `superset_4_1_db`    | `/var/lib/postgresql/data`  | PostgreSQL 数据               |
| `superset_4_1_redis` | `/data`                     | Redis 持久化（AOF/RDB）       |
| `superset_4_1_data`  | `/app/superset_home`        | Superset 上传、SQL Lab 查询等 |

容器销毁数据不丢；`docker compose down -v` 会一并删除。

## init 流程

`superset-init` 容器一次性执行：

```bash
pip install --no-cache-dir psycopg2-binary redis       # 1. 安装驱动
superset db upgrade                                     # 2. 迁移 schema
superset init                                           # 3. 初始化角色/权限
(superset fab list-users | grep admin) ||               # 4. 确保 admin 存在
    superset fab create-admin ...
python /app/pythonpath/load_examples_init.py            # 5. 自定义示例加载
echo 'INIT DONE'
```

详细：[`pythonpath/load_examples_init.py`](./pythonpath/load_examples_init.py)

## 示例数据加载机制

完全离线加载，无外网依赖：

1. 仓库根目录 `../example-data` 被 bind mount 到容器内 `/app/local_samples`
2. init 脚本 `load_examples_init.py` 在 `superset.examples.helpers` 模块中：
   - 覆盖 `BASE_URL`（远程兜底源）
   - 替换 `get_example_url` 为读取本地 `file://` URL
3. 修复 `examples` 数据库的 `sqlalchemy_uri` 指向 PostgreSQL（默认指向 SQLite，跨容器路径不共享会导致数据丢失）
4. 修复元数据 schema 不一致（SQLite 默认 `main` → PostgreSQL 默认 `public`）
5. 调用 `superset.cli.examples.load_examples_run` 加载所有示例数据

## 与 6.0 的差异

| 维度         | 4.1                                    | 6.0                                       |
| ------------ | -------------------------------------- | ----------------------------------------- |
| Worker       | 无（4.1 可选 Celery，配置更简单）      | 强制 Celery worker                        |
| 容器用户     | 默认 `superset`（UID 1000）            | `root`（v6.0 镜像需 root 写 venv）        |
| Python 路径  | 系统 Python                            | `/app/.venv/bin/python`（uv 管理）        |
| 配置模块     | `superset.examples.helpers`            | 同，但 6.0 YAML 走 `marshmallow.URL()` 校验 |
| 前端         | 服务端渲染为主                         | SPA + Ant Design                          |
| API 鉴权     | JWT（写操作需 CSRF）                   | JWT + 强制 CSRF                           |

完整差异见 [`../superset-6.0/README.md`](../superset-6.0/README.md)。

## 常见问题

| 症状                                          | 解决                                                                       |
| --------------------------------------------- | -------------------------------------------------------------------------- |
| init 容器一直 Pending                         | 检查 postgres / redis 健康检查是否通过；`docker compose ps` 查看依赖关系   |
| `INIT DONE` 出现但 web 容器 unhealthy         | `docker compose logs superset`，多为 `superset_config.py` 语法错误          |
| 登录后看不到 example 图表                     | 检查 `examples` 库是否指向 postgres：登录 → Data → Databases              |
| 想跳过示例数据重新加载                        | `docker compose down -v && docker compose up -d`                          |
| `ModuleNotFoundError: No module named 'psycopg2'` | init/web 容器内 `pip install psycopg2-binary` 是否成功（查看日志）        |
