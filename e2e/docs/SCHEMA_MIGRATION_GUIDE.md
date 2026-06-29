# Superset 独立 Schema 部署 - 完整过程文档

## 1. 目标

将 Superset 部署为 **元数据（metadata）与业务数据分离** 的架构：
- Superset 元数据（dashboards、charts、users、permissions）保留在 `public` schema
- 业务数据（示例数据集 `birth_names`、`flights` 等）放入独立 `superset_examples` schema

**优点**：
- 元数据与业务数据互不污染
- 易于备份：可以单独备份元数据或业务数据
- 多租户隔离：可以为不同业务创建不同的 schema
- 迁移/升级安全：升级 Superset 时不会动业务数据

---

## 2. 环境信息

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows |
| PostgreSQL | 16.1 (本地) |
| PostgreSQL 端口 | 25011 |
| PostgreSQL 客户端 | `C:\sandbox\tools\postgresql16\bin\` |
| 数据库 | `superset` |
| Superset 目录 | `d:\workspace\superset-space\superset-github\superset-4.1-token` |
| Python venv | `./venv/` |

---

## 3. 关键配置

### 3.1 PostgreSQL schema 创建

```sql
-- 连接到 superset 数据库
psql -h localhost -p 25011 -U postgres -d superset

-- 创建业务数据 schema
CREATE SCHEMA IF NOT EXISTS superset_examples;

-- 授权（如果用其他用户）
GRANT ALL ON SCHEMA superset_examples TO postgres;

-- 设置默认 search_path
ALTER USER postgres SET search_path TO public, superset_examples;
```

### 3.2 `superset_config.py` 关键配置

```python
# 元数据存储（默认 public schema）
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres@localhost:25011/superset"

# 示例数据存储（通过 search_path 限定到 superset_examples）
# 关键: ?options=-c search_path=... 让 pd.to_sql / INSERT 自动写入指定 schema
SQLALCHEMY_EXAMPLES_URI = (
    "postgresql+psycopg2://postgres@localhost:25011/superset"
    "?options=-c%20search_path%3Dsuperset_examples%2Cpublic"
)
```

**为什么用 `?options=-c search_path=...`？**
- psycopg2 会在连接时执行 `SET search_path TO ...`
- 所有 `CREATE TABLE` / `INSERT` 自动使用新 schema
- 不需要修改 Superset 源码

---

## 4. 执行步骤

### 4.1 验证 PostgreSQL 连接

```powershell
"C:\sandbox\tools\postgresql16\bin\pg_isready.exe" -h localhost -p 25011
# 输出: localhost:25011 - 接受连接
```

### 4.2 创建 schema

```powershell
$C:\sandbox\tools\postgresql16\bin\psql.exe -h localhost -p 25011 -U postgres -d superset `
  -c "CREATE SCHEMA IF NOT EXISTS superset_examples;
      GRANT ALL ON SCHEMA superset_examples TO postgres;
      ALTER USER postgres SET search_path TO public, superset_examples;"
```

输出：
```
CREATE SCHEMA
GRANT
ALTER ROLE
```

### 4.3 修改 `superset_config.py`

将原 15435 端口的 Docker 配置改为 25011 端口的本地 PostgreSQL，并加上 `search_path` URL 参数。

### 4.4 备份元数据（重要！）

```powershell
$C:\sandbox\tools\postgresql16\bin\pg_dump.exe `
  -h localhost -p 25011 -U postgres -d superset -n public -F c `
  -f "superset_metadata_backup_20260630_073909.backup"
```

输出：`superset_metadata_backup_20260630_073909.backup` (160KB)

### 4.5 加载示例数据

由于 `superset` CLI 输出在 Windows gitbash 下被吞掉，使用 Python 直接调用：

```powershell
cd d:\workspace\superset-space\superset-github\superset-4.1-token
$env:SUPERSET_CONFIG_PATH = "superset_config.py"
./venv/Scripts/python.exe -c "
from superset.app import create_app
app = create_app()
with app.app_context():
    from superset.cli.examples import load_examples_run
    load_examples_run(force=True)
"
```

输出（关键片段）：
```
Loading examples metadata and related data into examples
Loading [World Bank's Health Nutrition and Population Stats]
Creating table [wb_health_population] reference
Loading [Birth names]
Done loading table!
Loading [Random long/lat data]
Done loading table!
Loading [Country Map data]
Done loading table!
Loading [Flights data]
Done loading table!
Loading [BART lines]
Loading [Misc Charts] dashboard
Loading DECK.gl demo
```

---

## 5. 验证结果

### 5.1 Schema 分离验证

```sql
SELECT table_schema, table_name, pg_size_pretty(pg_total_relation_size(...)) AS size
FROM information_schema.tables
WHERE table_schema IN ('public', 'superset_examples')
ORDER BY table_schema, table_name;
```

**public schema（49 张表）**：
```
ab_permission, ab_role, ab_user, dashboards, slices, tables, dbs,
alembic_version, css_templates, key_value, logs, query, ...
```

**superset_examples schema（7 张表）**：
```
table_schema      | table_name              | size
------------------+-------------------------+--------
supersetset_examples | bart_lines              | 16 kB
superset_examples    | birth_france_by_region  | 40 kB
superset_examples    | birth_names             | 6272 kB
superset_examples    | flights                 | 21 MB
superset_examples    | long_lat                | 37 MB
superset_examples    | sf_population_polygons  | 152 kB
superset_examples    | wb_health_population    | 18 MB
```

### 5.2 数据量验证

```sql
SELECT 'birth_names' AS tbl, COUNT(*) FROM superset_examples.birth_names
UNION ALL SELECT 'flights', COUNT(*) FROM superset_examples.flights
UNION ALL SELECT 'wb_health_population', COUNT(*) FROM superset_examples.wb_health_population
UNION ALL SELECT 'long_lat', COUNT(*) FROM superset_examples.long_lat;
```

| 表 | 行数 |
| --- | --- |
| birth_names | 75,691 |
| flights | 55,105 |
| wb_health_population | 11,770 |
| long_lat | 261,552 |

### 5.3 元数据指向验证

```sql
SELECT table_name, schema FROM public.tables
WHERE schema IS NOT NULL AND schema != ''
ORDER BY table_name;
```

```
       table_name       |      schema
------------------------+-------------------
 bart_lines             | superset_examples
 birth_france_by_region | superset_examples
 birth_names            | superset_examples
 flights                | superset_examples
 long_lat               | superset_examples
 sf_population_polygons | superset_examples
 wb_health_population   | superset_examples
```

✅ Superset 的 `tables` 元数据正确指向 `superset_examples` schema

---

## 6. 关键 SQL 模板

### 6.1 查看表分布

```sql
SELECT 
    table_schema, 
    COUNT(*) AS table_count,
    pg_size_pretty(SUM(pg_total_relation_size(
        quote_ident(table_schema) || '.' || quote_ident(table_name)
    ))) AS total_size
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
GROUP BY table_schema
ORDER BY table_count DESC;
```

### 6.2 查看元数据 vs 业务数据

```sql
-- 元数据表（公开 schema）
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' AND tablename NOT LIKE 'ab_%'
ORDER BY tablename;

-- 业务数据表（独立 schema）
SELECT tablename FROM pg_tables 
WHERE schemaname = 'superset_examples'
ORDER BY tablename;
```

### 6.3 备份独立 schema

```bash
# 只备份元数据
pg_dump -h localhost -p 25011 -U postgres -d superset -n public -F c -f metadata.backup

# 只备份业务数据
pg_dump -h localhost -p 25011 -U postgres -d superset -n superset_examples -F c -f examples.backup

# 恢复业务数据
pg_restore -h localhost -p 25011 -U postgres -d superset -n superset_examples examples.backup
```

### 6.4 迁移到新数据库

```sql
-- 1. 在新数据库创建 schema
CREATE SCHEMA superset_examples;

-- 2. 导入业务数据
\i examples_data.sql

-- 3. 修改 superset_config.py 指向新数据库
SQLALCHEMY_EXAMPLES_URI = "postgresql+psycopg2://user:pass@new_host/new_db?options=-c search_path=superset_examples,public"

-- 4. 在 Superset UI 中执行 "Refresh metadata" 让 datasets 重新连接到新库
```

---

## 7. 常见问题

### Q1: CLI 命令无输出

**症状**: `superset load_examples` 在 Windows gitbash 下输出空白

**原因**: gitbash TTY 处理问题

**解决**: 用 Python 直接调用：
```powershell
./venv/Scripts/python.exe -c "
from superset.app import create_app
app = create_app()
with app.app_context():
    from superset.cli.examples import load_examples_run
    load_examples_run(force=True)
"
```

### Q2: Dataset 元数据未更新

**症状**: 加载示例后，UI 中看不到 dataset

**解决**: 加载时已经自动创建 `public.tables` 元数据，但可以手动刷新：
```powershell
./venv/Scripts/superset.exe refresh-datasources
```

### Q3: SQL 查询找不到表

**症状**: `SELECT * FROM birth_names` 报 "relation does not exist"

**原因**: 默认 search_path 不包含 `superset_examples`

**解决**:
- 在 SQL Lab 中使用完整限定名: `SELECT * FROM superset_examples.birth_names`
- 或者在连接中设置 search_path

### Q4: 如何回滚到 metadata 共享 schema

```sql
-- 1. 删除独立 schema
DROP SCHEMA superset_examples CASCADE;

-- 2. 恢复 metadata 备份
pg_restore -h localhost -p 25011 -U postgres -d superset -n public superset_metadata_backup_20260630_073909.backup

-- 3. 修改 superset_config.py
SQLALCHEMY_EXAMPLES_URI = "postgresql+psycopg2://postgres@localhost:25011/superset"
```

---

## 8. 后续优化

### 8.1 多 schema 业务数据

```sql
-- 业务 A
CREATE SCHEMA business_a;
-- 业务 B
CREATE SCHEMA business_b;

-- 不同的 database connection 使用不同的 search_path
-- business_a:
SQLALCHEMY_DATABASE_URI = ".../superset?options=-c search_path=business_a,public"
-- business B:
SQLALCHEMY_DATABASE_URI = ".../superset?options=-c search_path=business_b,public"
```

### 8.2 自动化迁移脚本

将所有 SQL 写入 `migrations/001_create_examples_schema.sql`：
```sql
-- migrations/001_create_examples_schema.sql
CREATE SCHEMA IF NOT EXISTS superset_examples;
GRANT ALL ON SCHEMA superset_examples TO superset_user;
```

### 8.3 Docker 部署

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: superset
      POSTGRES_USER: superset
      POSTGRES_PASSWORD: superset
    volumes:
      - ./migrations/001_create_examples_schema.sql:/docker-entrypoint-initdb.d/001.sql
    ports:
      - "15435:5432"
```

---

## 9. 测试清单（已全部通过 ✅）

| # | 测试项 | 结果 | 详情 |
| --- | --- | --- | --- |
| 1 | PostgreSQL 连接 | ✅ | `localhost:25011 - 接受连接` |
| 2 | `superset_examples` schema 创建 | ✅ | `CREATE SCHEMA` |
| 3 | `superset_config.py` 配置更新 | ✅ | `?options=-c+search_path%3Dsuperset_examples%2Cpublic` |
| 4 | metadata 备份 | ✅ | `superset_metadata_backup_20260630_073909.backup` (160KB) |
| 5 | `load_examples_run` 加载 | ✅ | 7 张表 + 4 个 dashboard + 38 个 chart |
| 6 | `public` schema 只有元数据 | ✅ | 49 张元数据表 |
| 7 | `superset_examples` schema 只有业务数据 | ✅ | 7 张业务数据表 |
| 8 | `public.tables` 元数据指向 schema | ✅ | 全部 7 个 dataset → `superset_examples` |
| 9 | SQL Lab 查询 | ✅ | flights=55105, birth_names=75691 行 |
| 10 | `search_path` 生效 | ✅ | examples db 显示 `superset_examples,public` |
| 11 | HTTP 登录 API | ✅ | `200, Got JWT` |
| 12 | Dashboard 列表 API | ✅ | `count=4, USA Births/World Bank/Misc Charts/deck.gl` |
| 13 | Dataset 列表 API | ✅ | `count=7, all schema=superset_examples` |
| 14 | Chart 列表 API | ✅ | `count=38` |

### 9.1 HTTP API 测试输出

```json
[Test 1] /api/v1/security/login -> 200
  Got JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6Ik...

[Test 2] /api/v1/dashboard/ -> 200, count=4
  Dashboards:
    - id=4 title="deck.gl Demo" slug=deck published=True
    - id=3 title="Misc Charts" slug=misc_charts published=False
    - id=2 title="USA Births Names" slug=births published=True
    - id=1 title="World Bank's Data" slug=world_health published=True

[Test 3] /api/v1/dataset/ -> 200, count=7
  Datasets:
    - id=2 name=birth_names schema=superset_examples db=examples
    - id=5 name=sf_population_polygons schema=superset_examples db=examples
    - id=6 name=flights schema=superset_examples db=examples
    - id=4 name=birth_france_by_region schema=superset_examples db=examples
    - id=1 name=wb_health_population schema=superset_examples db=examples
    - id=3 name=long_lat schema=superset_examples db=examples
    - id=7 name=bart_lines schema=superset_examples db=examples

[Test 4] /api/v1/chart/ -> 200, count=38
```

### 9.2 数据库测试输出

```sql
[Test 1] Examples DB search_path: superset_examples,public
[Test 2] birth_names: 75691 rows
[Test 3] flights: 55105 rows
[Test 4] wb_health_population: 11770 rows
[Test 5] dashboards: 4 (via public fallback)
[Test 6] Datasets with schema (7 total):
  - bart_lines -> superset_examples
  - birth_france_by_region -> superset_examples
  - birth_names -> superset_examples
  - flights -> superset_examples
  - long_lat -> superset_examples
  - sf_population_polygons -> superset_examples
  - wb_health_population -> superset_examples
```

---

## 10. 快速启动

```powershell
cd d:\workspace\superset-space\superset-github\superset-4.1-token
$env:SUPERSET_CONFIG_PATH = "superset_config.py"
./venv/Scripts/superset.exe run -p 8188 --with-threads --reload --debugger
```

登录：
- URL: http://localhost:8188/
- 用户: admin
- 密码: admin

可访问的 dashboard：
- http://localhost:8188/superset/dashboard/world_health/ - World Bank
- http://localhost:8188/superset/dashboard/births/ - USA Births
- http://localhost:8188/superset/dashboard/deck/ - deck.gl Demo
- http://localhost:8188/superset/dashboard/misc_charts/ - Misc Charts
