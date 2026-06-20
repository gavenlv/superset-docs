# superset-docs
superset docs

## 目录结构

- `superset-4.1/` — Superset 4.1.1 完整环境（Web + Postgres + Redis）
- `superset-6.0/` — Superset 6.0.0 完整环境（Web + Worker + Postgres + Redis）
- `example-data/` — 示例数据集（CSV/JSON），供两个版本加载示例图表

两个版本互相独立，使用不同的端口与独立的数据卷，可同时运行。

## 端口分配

| 服务 | 4.1 | 6.0 |
| --- | --- | --- |
| Superset Web | 18088 | 18089 |
| PostgreSQL | 15433 | 15434 |
| Redis | 16380 | 16381 |

默认账号 `admin / admin`（init 容器自动创建）。

## 启动方式

### 启动 4.1
```bash
cd superset-4.1
docker compose up -d
```

### 启动 6.0
```bash
cd superset-6.0
docker compose up -d
```

### 同时启动两个版本
```bash
cd superset-4.1 && docker compose up -d
cd ../superset-6.0 && docker compose up -d
```

## 数据持久化

每个版本都使用 **Docker 命名卷** 持久化：
- `superset_4_1_db` / `superset_6_0_db`：PostgreSQL 数据
- `superset_4_1_redis` / `superset_6_0_redis`：Redis 缓存
- `superset_4_1_data` / `superset_6_0_data`：Superset 上传文件、SQL Lab 查询等

容器销毁后数据不丢失，`docker compose down` 不会删卷；如需清理数据请加 `-v`：
```bash
docker compose down -v
```

## 查看数据卷
```bash
docker volume ls | grep superset
```

## 停止服务
```bash
cd superset-4.1 && docker compose down
cd ../superset-6.0 && docker compose down
```

## 示例数据

`example-data/` 目录包含 Superset 所有示例数据集（CSV/JSON），两个版本共享同一份数据。

- **4.1**：通过 `load_examples_init.py` 将 `get_example_url` 替换为读取本地 `file://` URL
- **6.0**：在 init 容器内启动临时 HTTP 服务（端口 18099），将 `BASE_URL` 指向 `http://localhost:18099/`，因为 6.0 的 YAML 配置使用 `marshmallow.fields.URL()` 校验，只接受 http/https

初始化脚本（`pythonpath/load_examples_init.py`）会自动：
1. 创建 `examples` 数据库并指向 PostgreSQL（而非默认 SQLite）
2. 从 `example-data/` 加载所有示例数据
3. 修复元数据 schema 不一致（SQLite `main` → PostgreSQL `public`）
4. 修复图表 `query_context` 中数据源 ID 不匹配问题（6.0）

完全清理后重新启动即可自动加载示例数据，无需网络下载。
