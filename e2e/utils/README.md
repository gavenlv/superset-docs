# utils/

通用工具函数。覆盖 BDD 上下文管理、Playwright 高亮操作、docker compose 编排、**多用户池**。

## 目录

- [文件索引](#文件索引)
- [`utils.stability`](#utilsstability)
- [`utils.service`](#utilsservice)
- [`utils.bdd`](#utilsbdd)
- [`utils.page_actions`（推荐）](#utilspage_actions推荐)
- [`utils.user_pool`（多用户池）](#utilsuser_pool多用户池)
- [`utils.api`](#utilsapi)
- [`utils.process`](#utilsprocess)
- [`utils.logging`](#utilslogging)
- [添加新 helper](#添加新-helper)

## 文件索引

| 文件              | 职责                                                       |
| ----------------- | ---------------------------------------------------------- |
| `process.py`      | 子进程调用、容器状态查询、HTTP 健康等待                    |
| `service.py`      | docker compose 编排（cold / reuse）、ServiceState 数据类   |
| `stability.py`    | `wait_for` 轮询等待、`robust_click` 多 selector 健壮点击   |
| `logging.py`      | 日志初始化（彩色输出、level 切换）                         |
| `bdd.py`          | Given/When/Then 上下文管理器 + 焦点高亮 + 截图附件        |
| `page_actions.py` | Playwright 操作的高亮包装（click/fill/hover/...）          |
| `api.py`          | API helper（httpx 包装，CSRF + JWT 自动）                  |
| `user_pool.py`    | 多用户池（多环境 / 多角色 / 多用户并发）                   |

## `utils.stability`

```python
from utils.stability import wait_for, robust_click

# 轮询等待任意条件为真
wait_for(
    lambda: page.locator(".chart").count() > 0,
    timeout=30,
    interval=0.5,
    description="chart loaded",
)

# 健壮点击：尝试多个 selector 直到成功
robust_click(
    page,
    [".ant-btn", "button[type='submit']"],
    timeout=10,
    description="submit button",
)
```

## `utils.service`

```python
from utils.service import cold_start_instance, reuse_instance, shutdown_instance

# 冷启动
state = cold_start_instance(superset_instance)   # 自动 down -v && up -d
# state.instance / .started_by_us / .health_check_seconds / .api_token_len

# 复用
state = reuse_instance(superset_instance)        # 仅健康检查
```

## `utils.bdd`

让测试可读性 + 报告体验更好。

```python
from utils.bdd import scenario, given, when, then, and_, highlight

@scenario("List all databases", tags=("database", "smoke"))
def test_list(superset_instance):
    """Scenario: List all databases
    When the client calls "/api/v1/database"
    Then the result contains at least one database
    """
    with when('calls "/api/v1/database"'):  ...
    with then("at least one database"):  assert ...
```

`when/then/given/and_` 支持：

| 参数        | 作用                                             |
| ----------- | ------------------------------------------------ |
| `page=`     | 关联的 Playwright page                           |
| `focus=`    | 高亮元素的 CSS selector                          |
| `screenshot`| 是否截当前帧附加到 Allure                        |
| `label=`    | 高亮角标文本（默认用 step 描述）                 |

## `utils.page_actions`（推荐）

`page_actions` 是 Playwright 操作的「高亮包装」——headed 模式下浏览器实时显示红框 + 角标 + 呼吸动画，可直接观察「这个按钮正在被点」「这个输入框正在被填」。

```python
from utils import page_actions as pa

pa.goto(page, url)                                # 高亮 goto
pa.click(page, "button.submit")                   # 高亮 + click
pa.fill(page, 'input[name="x"]', value)            # 高亮 + fill
pa.type_text(page, sel, "abc")                    # 高亮 + 逐字 type
pa.hover(page, sel)                               # 高亮 + hover
pa.select(page, sel, "v")                         # 高亮 + select_option
pa.check(page, sel) / pa.uncheck(page, sel)       # 高亮 + check / uncheck
pa.press(page, "Enter")                           # 按键
pa.focus(page, sel)                               # 只高亮 + focus
pa.clear_highlights(page)                         # 清除所有高亮
```

每个操作会：

1. 注入高亮（4px 红框 + 角标显示动作名）
2. 执行 Playwright 调用
3. 保留高亮 300ms 便于肉眼观察
4. 自动注册为 Allure step（`Action: click -> <selector>`）

> **强制要求**：任何 UI 操作必须走 `pa.*`，禁止 `page.click/fill/goto/...` 直接调用。
> 例外（只读 / 等待）见 [project_rules.md §1.2](../../../.trae/rules/project_rules.md)。

## `utils.user_pool`（多用户池）

为多用户 E2E 和性能压测提供线程安全的凭据池 + token 缓存。

### 核心 API

```python
from utils.user_pool import user_pool

# 选用户
u  = user_pool.pick("viewer")                            # 随机
u1 = user_pool.pick("viewer", index=0)                   # 固定索引（确定性）
u2 = user_pool.pick("viewer", strategy="round_robin")    # 轮询
u3 = user_pool.acquire("viewer")                         # 同 round_robin（压测 VU 用）

# token 缓存（线程安全；默认 10 min TTL）
token = user_pool.token_for(u, base_url)
csrf  = user_pool.csrf_for(u, base_url)

# 释放 / 失效
user_pool.mark_active(u)             # 标记活跃
user_pool.release(u)                 # 标记空闲
user_pool.invalidate(u, base_url)    # 强制重登
user_pool.clear_cache()              # 清空所有 token

# 状态查询
viewers = user_pool.users("viewer")  # tuple[User, ...]
user_pool.has("admin")               # bool
user_pool.all_roles()                # ('admin', 'analyst', 'viewer', 'embed')
user_pool.active_count("viewer")     # 当前活跃 user 数
```

### 选用户策略

| 场景 | strategy | 说明 |
| --- | --- | --- |
| 单元 / 集成测试 | `random`（默认） | 简单、互不干扰 |
| 性能压测 VU | `round_robin` | 每个 VU 拿不同 user，**不挤兑** |
| 确定性场景 | `index=N` | 固定取 user[N]（可重放） |

### Token 缓存机制

- key = `(username, base_url)`
- value = `(token, csrf, expires_at)`
- 提前 30s 刷新（避免边界过期）
- 默认 TTL = 600s
- 失效时自动重新登录（POST `/api/v1/security/login` + GET `/api/v1/security/csrf_token/`）

### 与 fixtures 配合

`fixtures/playwright_fixtures.py` 已经把 `user_pool` 包装成 `login_as_role` 和 `multi_user_pages` 工厂，**E2E 测试优先用 fixture**（自动清理 context）。

```python
# E2E 推荐
def test_xxx(login_as_role):
    p1 = login_as_role("viewer", index=0)
    p2 = login_as_role("viewer", index=1)

# 性能脚本（Locust/k6）直接用
def on_start():
    self.user = user_pool.acquire("viewer")
    self.token = user_pool.token_for(self.user, host)
```

### 回退策略

如果某 role 在当前 env 没配 user，`pick()` 会：

1. 如果不是 admin：warning + fallback 到 admin
2. 如果是 admin：抛 `RuntimeError`

## `utils.api`

API 客户端（httpx 包装）。

```python
from utils.api import api_client

client = api_client("http://localhost:18089")
# 自动：登录 → 拿 JWT → 拿 CSRF
client.get("/api/v1/dashboard/")
client.post("/api/v1/chart/data", json={...})
```

## `utils.process`

子进程 + HTTP 健康等待。

```python
from utils.process import wait_for_http, run_cmd

# 等待 /health 返回 200
wait_for_http("http://localhost:18088/health", timeout=600)

# 跑子进程
run_cmd(["docker", "compose", "ps"], cwd=Path("../superset-6.0"))
```

## `utils.logging`

```python
from utils.logging import setup_logging

setup_logging(level="INFO")  # 默认；也可 E2E_LOG_LEVEL=DEBUG
```

## 添加新 helper

- 新工具应放在 `utils/` 下，**不依赖** `fixtures/` 或 `tests/`
- 涉及多用户 / 多环境：复用 `config.settings.CONFIG` + `utils.user_pool.user_pool`
- 文档追加到本文档表格
