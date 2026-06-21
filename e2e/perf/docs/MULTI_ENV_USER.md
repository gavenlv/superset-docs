# 多环境 / 多用户 / 多用户并发压测 指南

> 配套：
> - `e2e/config/config.{dev,sit,uat,prod}.yaml` — 环境配置
> - `e2e/utils/user_pool.py` — 用户池
> - `e2e/fixtures/playwright_fixtures.py` — E2E 多用户 fixture
> - `e2e/perf/locust/tasks/base.py` — Locust 多用户接入
> - `e2e/perf/k6/scripts/lib.js` — k6 多用户接入

## 1. 多环境

### 1.1 配置文件分层

```
e2e/config/
├── config.yaml          # 默认 / DEV 基线（始终存在）
├── config.dev.yaml      # DEV 覆盖（可选）
├── config.sit.yaml      # SIT 覆盖（外部环境）
├── config.uat.yaml      # UAT 覆盖（预发）
└── config.prod.yaml     # PROD 覆盖（生产，仅 smoke）
```

加载规则（`e2e/config/settings.py`）：
- `config.yaml` 是 base（必备）
- `config.<env>.yaml` 覆盖 base，**deep-merge**：未指定的 key 继承 base
- 环境变量 (`E2E_*`) 优先级最高

### 1.2 切换环境

```bash
# 方式 1：CLI 参数
python run.py --env sit -m smoke

# 方式 2：环境变量
E2E_ENV=uat python run.py -m smoke

# 方式 3：脚本里 export
export E2E_ENV=prod
bash perf/tools/run_locust.sh
```

### 1.3 列出当前环境的 user_pool

```bash
python run.py --list-users
python run.py --list-users --env sit
```

输出：
```
>> active env = sit
>> instances: [('4.1', 'https://superset-4.1.sit.internal.example.com'), ...]
>> user_pool:
      admin  (2 users)
     - sit_admin_1  label=ops-lead
     - sit_admin_2  label=ops-backup
     viewer  (10 users)
     - sit_viewer_01  ...
     ...
```

### 1.4 跨环境环境变量覆盖

特定环境的特定实例 URL 可通过 `E2E_BASE_URL_<ENV>_<VERSION>` 覆盖：

```bash
# SIT 4.1 用本地容器跑临时测试
E2E_BASE_URL_SIT_4_1=http://localhost:18088 python run.py --env sit -m smoke
```

支持的 token（依字母序）：
- `E2E_BASE_URL_4_1` / `E2E_BASE_URL_6_0` — 全局
- `E2E_BASE_URL_DEV_4_1` / `E2E_BASE_URL_DEV_6_0` — 仅 dev
- `E2E_BASE_URL_SIT_4_1` / `E2E_BASE_URL_SIT_6_0` — 仅 sit
- `E2E_BASE_URL_UAT_4_1` / `E2E_BASE_URL_UAT_6_0` — 仅 uat
- `E2E_BASE_URL_PROD_4_1` / `E2E_BASE_URL_PROD_6_0` — 仅 prod

### 1.5 各环境典型配置

| Env | 用途 | 实例 | 用户池规模 | 性能档 |
| --- | --- | --- | --- | --- |
| dev | 本地开发 | docker compose | 2/2/5/2 = 11 | 10 VU（手测） |
| sit | 集成测试 | K8s / docker | 2/3/10/2 = 17 | 200 VU / 10min |
| uat | 用户验收 | K8s 生产镜像 | 3/4/20/3 = 30 | 500 VU / 15min |
| prod | 生产 | K8s 主域名 | 1/1/1/1 = 4（仅 e2e 服务账号） | 30 VU / 1min（smoke） |

## 2. 用户池（多用户）

### 2.1 配置格式

**紧凑格式**（`e2e/config/config.yaml` dev 默认）：
```yaml
user_pool:
  admin:
    - admin/admin
    - admin_ops_1/Admin#1234
  viewer:
    - viewer1/Viewer#1234
    - viewer2/Viewer#1234
```

**详细格式**（带 label / extra）：
```yaml
user_pool:
  admin:
    - {username: sit_admin_1, password: SitAdmin#1234, label: ops-lead}
    - {username: sit_admin_2, password: SitAdmin#1234, label: ops-backup}
```

### 2.2 API（Python）

```python
from utils.user_pool import user_pool
from config.settings import CONFIG

# 列举
print(user_pool.users("viewer"))          # tuple[User, ...]
print(CONFIG.users_for_role("viewer"))    # 同上

# 挑选
v = user_pool.pick("viewer")              # 随机一个 viewer
v = user_pool.pick("viewer", index=0)     # 固定 viewer[0]
v = user_pool.acquire("viewer")           # round_robin（压测用）

# Token 缓存
token = user_pool.token_for(v, base_url)  # 必要时自动登录
user_pool.invalidate(v, base_url)         # 强制重登
```

### 2.3 角色名映射（locust）

locust User 类 → user_pool role：

| Locust User class | user_pool role | config.yaml role_weights key |
| --- | --- | --- |
| `AdminOpsUser` | `admin` | `admin_ops` (1) |
| `AnalystUser` | `analyst` | `analyst` (10) |
| `ViewerUser` | `viewer` | `viewer` (30) |
| `EmbedUser` | `embed` | `embed` (8) |

### 2.4 Token 缓存策略

- **per-user, per-base_url** 的 `dict[(username, base_url) → _UserToken]`
- TTL：10 分钟（提前 30s 刷）
- 写操作需要 CSRF：`get_csrf(base_url)` 同缓存
- 线程安全（`threading.RLock`）

## 3. 多用户 E2E 测试

### 3.1 Fixture

| Fixture | 说明 |
| --- | --- |
| `user_pool` | 单例 |
| `login_as_role(role, index=None)` | 工厂 fixture，返回新登录的 page（独立 context） |
| `multi_user_pages[N]` | 参数化拿 N 个不同用户，各一个 page |

### 3.2 示例：3 个 viewer 同时登录

```python
@pytest.mark.multi_user(3)
def test_concurrent_login(multi_user_pages, superset_instance):
    pages = multi_user_pages
    for p in pages:
        assert "/login/" not in p.url
        p.goto(f"{superset_instance.instance.base_url}/superset/welcome/")
```

### 3.3 示例：admin 与 viewer 对比

```python
def test_admin_vs_viewer_visibility(login_as_role, superset_instance):
    admin_page = login_as_role("admin", index=0)
    viewer_page = login_as_role("viewer", index=0)
    base = superset_instance.instance.base_url

    admin_page.goto(f"{base}/dashboard/list/")
    viewer_page.goto(f"{base}/dashboard/list/")

    # admin 看到的 dashboard 数 >= viewer
    admin_count = admin_page.locator(".dashboard-list-view .row").count()
    viewer_count = viewer_page.locator(".dashboard-list-view .row").count()
    assert admin_count >= viewer_count
```

### 3.4 跑多用户 E2E

```bash
# dev 6.0
python run.py --env dev -m multi_user -i 6.0

# sit
python run.py --env sit -m multi_user -i 6.0

# 仅跑 concurrent_login 这条
python run.py --env sit -k concurrent_login
```

## 4. 多用户并发性能压测

### 4.1 Locust 自动从池子挑用户

每个 VU 在 `on_start` 里调 `acquire_user(self.role)`：

```python
# perf/locust/tasks/base.py (已实现)
def on_start(self):
    user = acquire_user(self.role)         # round_robin 拿一个
    self._assigned_username = user.username
    token = get_cached_token(self.host)    # per-user 缓存
    self.client.headers["Authorization"] = f"Bearer {token}"
```

启动时打印池子：
```
[run_locust] env=sit target=6.0 host=...
[run_locust] user_pool:
       admin  (2 users): ['sit_admin_1', 'sit_admin_2']
     analyst  (3 users): ['sit_alpha', 'sit_beta', 'sit_gamma']
      viewer  (10 users): ['sit_viewer_01', 'sit_viewer_02', ...]
       embed  (2 users): ['sit_guest', 'sit_guest2']
```

### 4.2 k6 多用户

通过 `K6_USERS_JSON` 环境变量传入用户池：

```bash
# 自动从 user_pool.viewer 拉
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js --multi-user viewer
```

或手动：
```bash
K6_USERS_JSON='[{"username":"v1","password":"p"},{"username":"v2","password":"p"}]' \
  k6 run perf/k6/scripts/dashboard_list.js
```

每 VU 用 `(VU_id - 1) % pool_size` 选用户 → round-robin 均匀分布。

### 4.3 按用户统计性能

Locust endpoint name 自动追加 `  (username)` 后缀：

```json
"GET /api/v1/dashboard/  (viewer1)": {"count": 50, "p95": 320, ...},
"GET /api/v1/dashboard/  (viewer2)": {"count": 50, "p95": 305, ...}
```

聚合时（`save_baseline.py`）按 method+path 聚合，把不同用户的指标平均。

## 5. CI 集成

Jenkins / GHA 多 env 模式：

```yaml
# .github/workflows/e2e.yml
jobs:
  e2e-sit:
    env:
      E2E_ENV: sit
    steps:
      - run: python run.py -m smoke -i 6.0
      - run: python run.py -m multi_user -i 6.0
  e2e-uat:
    env:
      E2E_ENV: uat
    steps:
      - run: python run.py -m smoke -i 6.0
  perf-sit:
    env:
      E2E_ENV: sit
    steps:
      - run: E2E_ENV=sit USERS=200 bash perf/tools/run_locust.sh
      - run: E2E_ENV=sit bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js --multi-user viewer
```

## 6. 常见问题

**Q1: SIT/UAT 跑 E2E 但 Superset 没起容器，怎么跑 cold？**
A: 外部部署环境把 `mode: reuse`（在 `config.sit.yaml` 里已设），跳过 docker compose。

**Q2: 用户池不够 200 VU 怎么办？**
A: SIT 默认 10 个 viewer，200 VU / 10 = 20 VU/用户（合理）。如果想更均匀：
- UAT 已配 20 个 viewer（推荐跑 ≥400 VU）
- PROD 仅 1 个 viewer，**不要跑 Locust**（会封号）

**Q3: 用户名密码怎么保密？**
A: 推荐用 Jenkins Credentials / GitHub Secrets 注入：
- `E2E_ADMIN_PASSWORD` 等
- 配置 YAML 里写 `${VAR_NAME}` 占位 + CI 替换

**Q4: 跨 env 的基线怎么管理？**
A: `perf/baselines/v6.0_sit.json` / `v6.0_uat.json` 路径调整（待 P5-1 实施）。

## 7. 元测试

`pytest perf/tests/test_config.py` 已加 5 个多用户 / 多环境测试：

```
test_user_pool_has_four_roles
test_user_pool_viewer_size_supports_load
test_user_pool_pick_by_role
test_user_pool_pick_by_index_is_deterministic
test_supported_envs
```

```
pytest perf/tests/ -v    → 18/18 passed
```
