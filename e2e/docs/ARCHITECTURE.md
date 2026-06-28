# 架构设计文档：为什么这样设计？

> 本文档解释 E2E + 性能测试框架的核心设计决策。
> 不仅告诉你「怎么做」，更重要的是「为什么这么做」。

## 目录

- [1. 设计哲学](#1-设计哲学)
- [2. 技术选型的思考](#2-技术选型的思考)
- [3. 配置系统设计](#3-配置系统设计)
- [4. 用户池设计](#4-用户池设计)
- [5. Page Object 设计](#5-page-object-设计)
- [6. Page Actions 设计](#6-page-actions-设计)
- [7. BDD 步骤设计](#7-bdd-步骤设计)
- [8. Fixture 生命周期设计](#8-fixture-生命周期设计)
- [9. 性能测试架构](#9-性能测试架构)
- [10. 稳定性策略](#10-稳定性策略)

---

## 1. 设计哲学

### 1.1 为什么是「分层架构」而不是「大泥球」？

**问题背景**：测试框架容易演变成「胶水代码」—— 测试用例直接混杂配置读取、浏览器操作、业务逻辑。

**设计决策**：采用清晰的分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    测试用例层 (tests/)                           │
│  只关注业务场景，不关心实现细节                                  │
│  例："登录 admin，访问 dashboard 列表，验证至少有 1 个"          │
├─────────────────────────────────────────────────────────────────┤
│                    Page Object 层 (pages/)                      │
│  封装页面交互，屏蔽 4.1/6.0 差异                                │
│  例：DashboardPage.goto() → 兼容 SSR 和 SPA                     │
├─────────────────────────────────────────────────────────────────┤
│                    Page Actions 层 (utils/page_actions.py)      │
│  封装 Playwright 操作，添加高亮 + Allure 步骤                    │
│  例：pa.click() → 高亮元素 + 记录步骤 + 执行点击                │
├─────────────────────────────────────────────────────────────────┤
│                    基础设施层                                   │
│  config/   → 多环境配置加载                                     │
│  fixtures/ → pytest 夹具（浏览器、登录、多用户）                  │
│  utils/    → 工具函数（稳定性、日志、BDD）                       │
└─────────────────────────────────────────────────────────────────┘
```

**为什么这样分层**：

| 层 | 职责 | 变更频率 | 理由 |
|---|---|---|---|
| 测试用例层 | 业务场景描述 | 高（频繁添加新用例） | 只写业务逻辑，不关心底层细节 |
| Page Object 层 | UI 交互封装 | 中（版本升级时变更） | 4.1/6.0 差异只在这里处理一次 |
| Page Actions 层 | 操作增强 | 低（稳定） | 所有测试共享同一套操作语义 |
| 基础设施层 | 配置、夹具、工具 | 低（稳定） | 框架核心，一旦稳定很少变更 |

**好处**：
- **可维护性**：修改 4.1/6.0 兼容逻辑只需改 Page Object
- **可读性**：测试用例读起来像自然语言
- **复用性**：Page Object 可被多个测试用例复用

---

## 2. 技术选型的思考

### 2.1 为什么选 Playwright 而不是 Selenium？

| 维度 | Playwright | Selenium | 为什么选 Playwright |
|-----|------------|----------|-------------------|
| **自动等待** | 内置 locator 等待 | 需要显式 wait | 减少 flaky test |
| **多浏览器** | Chromium/FF/WebKit | 需额外驱动 | 一套 API 测全部 |
| **网络拦截** | 原生支持 | 需插件 | 方便模拟网络状况 |
| **截图/录屏** | 内置 | 需额外配置 | 故障排查方便 |
| **生成器** | `playwright codegen` | 无 | 快速生成测试代码 |
| **稳定性** | 强（Microsoft 维护） | 中等（社区驱动） | CI 稳定性优先 |

### 2.2 为什么选 Locust + k6 双框架？

**Locust 的优势**：
- Python 编写，与 E2E 共享代码（auth、config）
- Web UI 实时监控，调试方便
- 支持复杂业务流程（多步骤任务链）

**k6 的优势**：
- Go 编译，性能极高（单机 50k+ VU）
- 脚本用 JavaScript，上手快
- 自带阈值断言，CI 集成方便

**双框架策略**：
- **Locust**：多角色混合压测（admin/analyst/viewer），模拟真实用户行为
- **k6**：单端点高压（300+ VU），验证重点查询性能
- **互补**：Locust 测场景，k6 测极限

---

## 3. 配置系统设计

### 3.1 为什么用分层配置（base + env 覆盖）？

**问题背景**：不同环境（dev/sit/uat/prod）有不同的配置：
- dev：localhost，少量用户
- sit：测试服务器，中等用户
- uat：预生产，大量用户
- prod：生产，严格阈值

**设计决策**：base + env 分层合并

```
config.yaml          ← base（dev 默认）
config.sit.yaml      ← SIT 覆盖（只写差异）
config.uat.yaml      ← UAT 覆盖
config.prod.yaml     ← PROD 覆盖
```

**加载优先级**（从低到高）：
1. `config.yaml`（base）
2. `config.<env>.yaml`（env 覆盖）
3. 环境变量 `E2E_*`（最高）

**为什么这样设计**：
- **DRY 原则**：公共配置只写一次（base）
- **灵活性**：每个环境只维护差异部分
- **安全**：敏感信息（prod 用户密码）不进代码库，用环境变量覆盖
- **可追溯**：diff 一目了然，知道每个环境改了什么

### 3.2 为什么用 dataclass 而不是 dict？

```python
# ❌ 不好：dict 没有类型检查
cfg = {"mode": "cold", "browser": 123}  # 不会报错

# ✅ 好：dataclass 有类型检查
@dataclass(frozen=True)
class TestConfig:
    mode: str = "reuse"
    browser: str = "chromium"
```

**理由**：
- **类型安全**：`browser` 必须是 `str`，传 `int` 会报错
- **自动补全**：IDE 能提示所有字段
- **不可变**：`frozen=True` 防止运行时意外修改配置
- **默认值**：未配置的字段有合理默认

### 3.3 为什么环境变量命名用 `E2E_` 前缀？

**理由**：
- **隔离**：避免与系统环境变量冲突
- **可识别**：一眼看出是 E2E 测试配置
- **可过滤**：`printenv | grep E2E_` 快速查看所有 E2E 配置

---

## 4. 用户池设计

### 4.1 为什么需要线程安全的用户池？

**问题背景**：性能测试中 200+ VU 并发请求用户，直接随机选可能导致：
- 同一用户被多个 VU 同时使用
- Token 缓存竞争条件
- 用户分配不均匀

**设计决策**：`UserPool` 类，使用 `threading.RLock` 保护共享状态

```python
class UserPool:
    def __init__(self):
        self._lock = threading.RLock()  # 可重入锁（支持嵌套调用）
        self._tokens: dict[tuple[str, str], _UserToken] = {}
        self._cursor: dict[str, int] = defaultdict(int)
```

**为什么用 RLock 而不是 Lock**：
- `acquire()` 内部可能调用 `pick()`，而 `pick()` 也需要锁
- RLock 允许同一线程多次获取同一把锁，不会死锁

### 4.2 为什么需要 Token 缓存？

**问题背景**：每次 HTTP 请求都登录会：
- 浪费时间（登录 API 也有开销）
- 给服务器造成额外压力
- 降低测试吞吐量

**设计决策**：per-user, per-base_url 的 Token 缓存

```python
def token_for(self, user: User, base_url: str, *, ttl_sec: int = 600) -> str:
    key = (user.username, base_url)  # 双维度 key
    with self._lock:
        cached = self._tokens.get(key)
        if cached and cached.is_valid:  # 提前 30s 刷新
            return cached.token
    # 缓存失效，重新登录
    token, csrf = _login(user, base_url)
    ...
```

**TTL 为什么是 600s（10 分钟）**：
- Superset 默认 JWT 过期时间是 1 小时
- 提前 30s 刷新（`is_valid` 判断）防止请求中途过期
- 10 分钟足够完成一个测试场景，又不会太长导致过期

### 4.3 为什么有三种选用户策略？

```python
def pick(self, role: str, *, index: int | None = None, strategy: str = "random") -> User:
```

| 策略 | 适用场景 | 理由 |
|-----|---------|-----|
| `random` | E2E 测试 | 随机选用户，模拟真实场景 |
| `round_robin` | 性能测试 | 均匀分配，避免某用户被过度使用 |
| `index` | 多用户 E2E | 固定用户，方便调试和复现问题 |

---

## 5. Page Object 设计

### 5.1 为什么用 Page Object 模式？

**问题背景**：直接在测试用例中写 `page.locator("button.submit").click()` 会：
- 选择器分散在各处，改一处要改全部
- 4.1/6.0 选择器不同，导致测试不可复用
- 测试用例冗长，难以阅读

**设计决策**：每个页面封装为一个类

```python
class DashboardPage:
    SEL_DASHBOARD_ITEM = ".dashboard-item, [data-test='dashboard-item']"
    
    def dashboard_count(self) -> int:
        return self.page.locator(self.SEL_DASHBOARD_ITEM).count()
```

**好处**：
- **封装**：选择器只定义一次
- **复用**：多个测试用例共享同一 Page Object
- **兼容**：4.1/6.0 差异在类内部处理

### 5.2 为什么选择器用逗号分隔？

```python
SEL_USERNAME = 'input[name="username"], input[id="username"]'
```

**理由**：
- 4.1 用 `name` 属性：`<input name="username">`
- 6.0 用 `id` 属性：`<input id="username">`
- Playwright locator 支持逗号并列多个选择器
- 一个选择器兼容两个版本，无需条件判断

---

## 6. Page Actions 设计

### 6.1 为什么不直接用 `page.click()`？

**问题背景**：直接调用 `page.click()` 在 headless 模式下：
- 无法看到测试在操作哪个元素
- 失败时难以定位问题
- 没有步骤记录

**设计决策**：封装 `pa.click()`，增加：
1. **高亮动画**：红框 + 角标 + 呼吸效果
2. **Allure 步骤**：自动记录操作
3. **延迟观察**：操作后保留高亮 300ms

```python
def click(page: Page, selector: str, *, timeout: float = 10000) -> None:
    with allure.step(f"Action: click -> {selector}"):
        _highlight(page, selector, action="click")  # 高亮
        loc = page.locator(selector).first
        loc.click(timeout=timeout)                   # 执行
        page.wait_for_timeout(300)                   # 保留高亮
```

### 6.2 为什么高亮用 CSS 注入而不是截图？

**理由**：
- **实时**：截图是静态的，CSS 高亮是动态的
- **轻量**：注入 CSS 几乎无开销，截图有 IO 开销
- **可观察**：headed 模式下能看到操作过程
- **兼容**：headless 模式也能生成带高亮的截图

---

## 7. BDD 步骤设计

### 7.1 为什么不直接用 pytest-bdd？

**问题背景**：pytest-bdd 功能强大但：
- 依赖重（需要额外安装）
- 学习曲线陡峭
- 配置复杂（feature 文件 + step 定义）
- 与 Playwright 集成不够灵活

**设计决策**：自实现轻量 BDD 体验

```python
from utils.bdd import given, when, then, and_

with given("已登录 admin", page=page, focus="header"):
    pass
with when("访问 dashboard 列表", page=page, focus="a[href='/dashboard']"):
    pa.click(page, "a[href='/dashboard']")
with then("显示至少 1 个 dashboard", screenshot=True):
    assert page.dashboard_count() > 0
```

**好处**：
- **轻量**：零额外依赖
- **灵活**：与 Playwright 无缝集成
- **可读**：测试用例像自然语言
- **可观测**：每个步骤自动高亮 + 截图

### 7.2 为什么用上下文管理器（`with`）？

```python
with when("点击提交", page=page, focus="button.submit"):
    pa.click(page, "button.submit")
```

**理由**：
- **自动清理**：退出 `with` 块时自动清除高亮
- **异常处理**：步骤内异常自动截图并传递
- **Allure 集成**：自动创建 step，无需手动 `allure.step()`

---

## 8. Fixture 生命周期设计

### 8.1 为什么 fixture 有不同的 scope？

```python
@pytest.fixture(scope="session")     # 整个测试会话一次
def playwright(): ...

@pytest.fixture(scope="session")     # 整个测试会话一次
def browser(playwright): ...

@pytest.fixture()                    # 每个测试用例一次（默认）
def context(browser): ...

@pytest.fixture()                    # 每个测试用例一次
def page(context): ...
```

**设计理由**：

| Fixture | Scope | 理由 |
|---------|-------|------|
| `playwright` | session | 启动/关闭开销大，全局共享 |
| `browser` | session | 浏览器进程重，全局共享 |
| `context` | function | **隔离关键**：每个测试独立的 cookies/localStorage |
| `page` | function | 每个测试独立页面 |

**为什么 `context` 必须是 function scope**：
- 如果两个测试共用同一个 context，登录状态会互相污染
- 一个测试的 `logout()` 会影响另一个测试的已登录状态
- 性能测试多用户场景需要完全隔离的浏览器上下文

### 8.2 为什么 `login_as_role` 是工厂 fixture？

```python
@pytest.fixture()
def login_as_role(superset_instance, browser):
    def _factory(role: str, *, index: int | None = None) -> Page:
        # 创建独立 context，登录，返回 page
        ...
    yield _factory
```

**问题背景**：测试可能需要多个不同角色的用户同时登录

**设计决策**：工厂模式，调用时动态创建

```python
def test_two_viewers(login_as_role):
    p1 = login_as_role("viewer", index=0)   # viewer1
    p2 = login_as_role("viewer", index=1)   # viewer2
    # 两个 page 完全隔离
```

**好处**：
- **按需创建**：需要几个用户就创建几个
- **完全隔离**：每个用户有独立的 browser context
- **灵活**：支持任意角色和用户索引

---

## 9. 性能测试架构

### 9.1 为什么性能测试与 E2E 共享配置？

**设计决策**：E2E 和性能测试共用 `config/` 和 `user_pool`

```
config/
├── settings.py        ← 两者共用的配置加载逻辑
├── config.yaml        ← base 配置
└── config.sit.yaml    ← SIT 配置

utils/
└── user_pool.py       ← 两者共用的用户池
```

**理由**：
- **一致性**：同一套用户凭据，避免配置不一致
- **维护成本**：只维护一份配置
- **环境切换**：`E2E_ENV=sit` 同时影响 E2E 和性能测试

### 9.2 为什么有「基线对比」机制？

**问题背景**：每次压测结果需要人工对比历史数据，效率低

**设计决策**：自动化基线对比

```python
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail
```

**对比维度**：
- p50/p95/p99 响应时间
- 错误率
- Apdex 分数
- 稳定性分数

**阈值策略**：
- **普通端点**：p95 允许 +20% 波动
- **关键端点**（dashboard 渲染、图表数据）：p95 只允许 +15% 波动
- **错误率**：不允许超过 1%

---

## 10. 稳定性策略

### 10.1 为什么需要失败重试？

**问题背景**：CI 中偶尔出现：
- 网络抖动导致的超时
- 页面加载延迟
- 429 Rate Limit

**设计决策**：`pytest-rerunfailures` 自动重试

```python
# 默认重试 2 次，间隔 3 秒
python run.py --reruns 2 --reruns-delay 3
```

**为什么不是无限重试**：
- 真正的 bug 应该失败，不应该被重试掩盖
- 2 次重试足以处理偶发的网络问题
- 过多重试会延长 CI 时间

### 10.2 为什么用 `wait_for` 而不是 `time.sleep`？

```python
# ❌ 不好：固定等待，浪费时间
time.sleep(5)

# ✅ 好：条件等待，满足立即返回
from utils.stability import wait_for
wait_for(
    lambda: page.locator(".dashboard-item").count() > 0,
    timeout=30000,
    description="dashboard items loaded"
)
```

**理由**：
- **高效**：元素出现立即返回，不浪费时间
- **健壮**：不会因为网络慢而失败
- **可调试**：超时时有明确的错误描述

### 10.3 为什么失败时自动截图？

**设计决策**：`pytest_runtest_makereport` hook 自动截图

```python
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        page = item.funcargs.get("page")
        page.screenshot(path=..., full_page=True)
        allure.attach.file(...)
```

**理由**：
- **快速定位**：失败时看到当时的页面状态
- **无需复现**：截图足以定位大多数问题
- **Allure 集成**：截图自动附加到报告

---

## 总结：设计原则

| 原则 | 体现 |
|-----|------|
| **分层架构** | 测试用例 → Page Object → Page Actions → 基础设施 |
| **单一职责** | 每个模块只做一件事 |
| **DRY** | 公共逻辑只写一次（配置、用户池、Page Object） |
| **可观测性** | 高亮、步骤记录、自动截图 |
| **可维护性** | 类型安全、清晰命名、封装差异 |
| **稳定性优先** | 重试、条件等待、异常处理 |
| **一致性** | E2E 与性能共用配置和用户池 |

理解这些设计原则后，你就能：
1. 快速定位问题（知道每一层负责什么）
2. 高效编写测试（遵循现有模式）
3. 安全修改代码（理解修改的影响范围）
4. 扩展功能（按照分层原则添加新模块）