# config/

E2E 与性能测试全局配置。支持**多环境分层**（dev/sit/uat/prod）、**多用户池**（per-role）、**性能测试段**集中管理。

## 目录

- [文件结构](#文件结构)
- [多环境架构](#多环境架构)
- [优先级](#优先级)
- [多用户池 user_pool](#多用户池-user_pool)
- [性能测试段 perf](#性能测试段-perf)
- [环境变量](#环境变量)
- [自定义实例](#自定义实例)
- [运行时 API](#运行时-api)
- [常见示例](#常见示例)

## 文件结构

| 文件                | 职责                                                       |
| ------------------- | ---------------------------------------------------------- |
| `settings.py`       | `TestConfig` 数据类 + 从 yaml/env 构造 + user_pool 解析    |
| `config.yaml`       | base 配置（dev 的默认值）                                  |
| `config.sit.yaml`   | SIT 覆盖层（深度合并到 base 之上）                         |
| `config.uat.yaml`   | UAT 覆盖层                                                 |
| `config.prod.yaml`  | PROD 覆盖层                                                |

```
config/
├── README.md           本文档
├── settings.py
├── config.yaml         base（dev）
├── config.sit.yaml     SIT 覆盖
├── config.uat.yaml     UAT 覆盖
└── config.prod.yaml    PROD 覆盖
```

## 多环境架构

```
┌─────────────────────────────────────────────────┐
│ config.yaml（base / dev 默认）                   │
│  - mode, browser, headless                       │
│  - instances: [4.1, 6.0]                        │
│  - user_pool: { admin, analyst, viewer, embed } │
│  - perf: { users, thresholds, ... }             │
└──────────┬──────────────────────────────────────┘
           │ deep_merge（env 覆盖 base）
           ▼
┌─────────────────────────────────────────────────┐
│ config.<env>.yaml（env 专属覆盖）               │
│  - instances[*].base_url    ← env URL           │
│  - user_pool.viewer         ← env 专属用户      │
│  - perf.users / thresholds  ← env 压测档位      │
└──────────┬──────────────────────────────────────┘
           │ deep_merge
           ▼
┌─────────────────────────────────────────────────┐
│ 环境变量（E2E_*/E2E_BASE_URL_*）                 │
│  优先级最高（永远覆盖 yaml）                     │
└─────────────────────────────────────────────────┘
           ▼
      CONFIG（单例）
```

### 切换环境

```bash
# dev（默认；只读 config.yaml）
python run.py -m smoke

# SIT
python run.py --env sit -m smoke
E2E_ENV=sit python run.py -m multi_user

# UAT / PROD 同理
E2E_ENV=uat python run.py -m smoke
E2E_ENV=prod python run.py -m health    # 通常仅健康检查
```

CLI：`--env` 会同时设置 `os.environ["E2E_ENV"]`，再交给 `settings.build_config()` 重新加载。

### 深度合并规则

`settings._deep_merge(base, override)` 是 dict 递归合并：
- 普通字段：override 直接覆盖
- 字典字段：继续递归
- 列表字段：**整体替换**（不合并元素）

所以 SIT 的 `instances` 是**替换** base 的 `instances`（不是 append），需要写完整的列表。

## 优先级

```
环境变量（E2E_*）  >  config.<env>.yaml  >  config.yaml
```

示例：

| 来源 | 字段 | 值 |
| --- | --- | --- |
| `config.yaml` | `instances[0].base_url` | `http://localhost:18088` |
| `config.sit.yaml` | `instances[0].base_url` | `https://sit.example.com` |
| `E2E_BASE_URL_SIT_4_1` | （运行时） | `https://override.example.com` |

→ 最终生效：`override.example.com`（env 变量覆盖 env yaml 覆盖 base yaml）

## 多用户池 user_pool

为 E2E 多用户并发与性能压测提供凭据池。**压测每个 VU 会拿一个用户**（避免共享 token 触发限流）。

### 配置格式

`config.yaml` 顶层：

```yaml
user_pool:
  admin:
    - admin/admin
    - admin_ops_1/Admin#1234
  analyst:
    - alpha/Alpha#1234
    - beta/Beta#1234
  viewer:                              # 至少 5 个（支持 100+ VU）
    - viewer1/Viewer#1234
    - viewer2/Viewer#1234
    - viewer3/Viewer#1234
    - viewer4/Viewer#1234
    - viewer5/Viewer#1234
  embed:
    - guest/Guest#1234
    - guest2/Guest#1234
```

**紧凑格式** `"user/pass"` — 推荐用于本地开发。

**详细格式**：

```yaml
user_pool:
  viewer:
    - username: viewer1
      password: Viewer#1234
      label: "team-A viewer"
    - username: viewer2
      password: Viewer#1234
      label: "team-B viewer"
```

混合两种格式也可（每条 list element 自适应）。

### 角色

| 角色 | 典型用途 | 最小数量（E2E） | 推荐数量（200 VU 压测） |
| --- | --- | :-: | :-: |
| `admin` | 配置、admin 路径 | 1 | 2 |
| `analyst` | Explore / chart 写 | 1 | 5 |
| `viewer` | dashboard / chart 读（重点） | 5 | 30+ |
| `embed` | 嵌入端点 | 1 | 5 |

### env 维度覆盖

`config.sit.yaml` 写一个 `user_pool` 段即整段替换 base 的同段：

```yaml
# config.sit.yaml
user_pool:
  admin:    [{ username: sit_admin, password: SIT#admin2025 }]
  analyst:  [{ username: sit_analyst, password: SIT#analyst2025 }]
  viewer:   # SIT 准备 20 个 viewer
    - { username: sit_v01, password: SIT#v01 }
    - { username: sit_v02, password: SIT#v02 }
    # ... 20 个
  embed:    [{ username: sit_guest, password: SIT#guest2025 }]
```

> 注意：因为 `user_pool` 段是 dict（role → list），整体替换生效；某个 env 缺某角色 = 0 用户，调用时会 fallback 到 admin（带 warning）。

### 运行时 API

```python
from config.settings import CONFIG, reload_config
from utils.user_pool import user_pool

# 直接读
viewers = CONFIG.users_for_role("viewer")
print(CONFIG.env)                       # 'dev' / 'sit' / ...

# 通过 user_pool（推荐）
u = user_pool.pick("viewer")                          # 随机
u = user_pool.pick("viewer", index=0)                 # 固定索引
u = user_pool.pick("viewer", strategy="round_robin")   # 轮询
token = user_pool.token_for(u, base_url)              # 线程安全 token 缓存

# 切换 env（CLI 也用这个）
cfg = reload_config("sit")
```

## 性能测试段 perf

`config.yaml` 的 `perf` 段被 `perf/common/config_loader.py` 读取，控制 Locust/k6 的全局行为。

```yaml
perf:
  enabled: true
  framework: locust               # locust | k6 | both
  duration_sec: 600               # 单次压测时长
  spawn_rate: 20                  # ramp-up 速度
  users: 200                      # 峰值用户数

  role_weights:                   # Locust 角色权重
    admin_ops: 1
    analyst: 10
    viewer: 30                    # 重点
    embed: 8

  baseline_dir: perf/baselines
  reports_dir: perf/reports

  thresholds:                     # 基线对比分级阈值
    p95_warn_pct: 15
    p95_fail_pct: 20
    p95_fail_pct_critical: 15     # chart/data 最重
    error_rate_fail_pct: 0.5

  critical_endpoints:             # 重点查询白名单
    - GET:/api/v1/dashboard/
    - POST:/api/v1/chart/data
  # ...
```

env 维度覆盖：

```yaml
# config.uat.yaml
perf:
  users: 1000                     # UAT 提高并发
  thresholds:
    p95_fail_pct: 25              # UAT 容差大一点
```

详细说明：[perf/PLAN.md](../perf/PLAN.md)、[perf/README.md](../perf/README.md)。

## 环境变量

| 变量                       | 说明                                       | 默认                |
| -------------------------- | ------------------------------------------ | ------------------- |
| `E2E_ENV`                  | dev / sit / uat / prod                     | `dev`               |
| `E2E_MODE`                 | cold / reuse                               | `reuse`             |
| `E2E_BROWSER`              | chromium / firefox / webkit                | `chromium`          |
| `E2E_HEADLESS`             | 1 / 0                                      | `1`                 |
| `E2E_CLEANUP`              | cold 模式结束是否清理容器                  | `1`                 |
| `E2E_RERUNS`               | 失败重试次数                               | `2`                 |
| `E2E_RERUNS_DELAY`         | 重试间隔（秒）                             | `3`                 |
| `E2E_PAGE_TIMEOUT_MS`      | 页面操作超时                               | `30000`             |
| `E2E_NAV_TIMEOUT_MS`       | 导航超时                                   | `60000`             |
| `E2E_ADMIN_USER`           | admin 用户名                               | `admin`             |
| `E2E_ADMIN_PASSWORD`       | admin 密码                                 | `admin`             |
| `E2E_BASE_URL_4_1`         | 4.1 base URL（覆盖 yaml）                  | `http://localhost:18088` |
| `E2E_BASE_URL_6_0`         | 6.0 base URL（覆盖 yaml）                  | `http://localhost:18089` |
| `E2E_BASE_URL_<ENV>_<VER>` | env 维度 base URL（最高优先级）            | —                   |
| `E2E_LOG_LEVEL`            | 日志级别                                   | `INFO`              |

仓库根目录可放 `.env` 文件（`dotenv.load_dotenv` 加载，**不会覆盖已有 env**）。

## 自定义实例

修改 `config.yaml` 的 `instances` 列表，每个实例需要：

| 字段                 | 说明                                         |
| -------------------- | -------------------------------------------- |
| `name`               | 标识符（用于 fixture 与 Allure label）        |
| `version`            | 版本号（写入 Allure environment）            |
| `base_url`           | 浏览器访问入口                                |
| `compose_dir`        | 相对 `e2e/` 的 docker-compose 目录           |
| `postgres_container` | PostgreSQL 容器名（用于 `docker exec` 直查） |
| `redis_container`    | Redis 容器名（可选）                          |

`name` 不要带点号（环境变量 `E2E_BASE_URL_<VER>` 会把 `.` 转成 `_`）。

## 运行时 API

`config/settings.py` 暴露：

```python
from config.settings import CONFIG, TestConfig, User, SupersetInstance, reload_config

CONFIG                          # TestConfig 单例（已 build）
CONFIG.env                      # 'dev' / 'sit' / 'uat' / 'prod'
CONFIG.instances                # tuple[SupersetInstance, ...]
CONFIG.user_pool                # dict[role, tuple[User, ...]]
CONFIG.users_for_role("viewer") # tuple[User, ...]
CONFIG.has_role("admin")        # bool
CONFIG.perf                     # dict（透传 yaml 的 perf 段）
CONFIG.screenshots_dir          # Path
CONFIG.allure_results_dir       # Path

# 重新加载（CLI / 多 env 测试用）
new_cfg = reload_config("uat")
```

`current_env()` 单独可调，校验 `E2E_ENV` 是否在 `SUPPORTED_ENVS`。

## 常见示例

### 例 1：本地 dev（默认）

不需要任何配置，`python run.py -m smoke` 直接生效。

### 例 2：内网 SIT

`config.sit.yaml`：

```yaml
instances:
  - name: 4.1
    version: 4.1.1
    base_url: "https://superset-4-1.sit.example.com"
    compose_dir: ../superset-4.1
    postgres_container: superset-4-1-postgres
    redis_container: superset-4-1-redis
  - name: 6.0
    version: 6.0.0
    base_url: "https://superset-6-0.sit.example.com"
    compose_dir: ../superset-6.0
    postgres_container: superset-6-0-postgres
    redis_container: superset-6-0-redis

user_pool:
  admin:  [{ username: sit_admin, password: ${SIT_ADMIN_PASS} }]
  viewer:
    - { username: sit_v01, password: ${SIT_VIEWER_PASS} }
    - { username: sit_v02, password: ${SIT_VIEWER_PASS} }
    # ... 20 个

perf:
  users: 500
```

> YAML 不支持 `${}` 变量；密码请放 `.env` 文件，由 `dotenv` 加载后程序从 `os.environ` 读。详见 `settings._load_env_config`。

### 例 3：临时指向别的 host

不动 yaml，命令行覆盖：

```bash
E2E_BASE_URL_SIT_4_1=https://staging-4-1.example.com \
    python run.py --env sit -m smoke
```

### 例 4：性能压测 UAT

```bash
E2E_ENV=uat bash perf/tools/run_locust.sh
# 读 config.uat.yaml 的 user_pool（200+ viewers） + perf.users=2000
```
