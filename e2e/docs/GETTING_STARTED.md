# 从零开始：E2E 测试入门教程

> 本文档面向**完全零基础**的初学者，一步一步带你学会使用这个测试框架。
> 不需要任何测试经验，只要会用终端就行！

## 📚 学习路径

```
第 0 步：环境准备        → 安装工具，启动 Superset
    ↓
第 1 步：跑第一个测试    → 体验 smoke 测试，看报告
    ↓
第 2 步：理解测试结构    → 认识目录、文件、fixture
    ↓
第 3 步：写第一个测试    → 动手写一个简单测试用例
    ↓
第 4 步：调试测试        → 用 headed 模式看测试在做什么
    ↓
第 5 步：进阶技巧        → BDD 风格、多用户、性能测试
```

---

## 第 0 步：环境准备

### 0.1 安装 Python

- **Windows**：从 [python.org](https://www.python.org/downloads/) 下载 3.10+
- **macOS**：`brew install python`
- **Linux**：`sudo apt-get install python3.10`

验证安装：
```bash
python --version   # 或 python3 --version
# 应输出 Python 3.10.x 或更高
```

### 0.2 安装 Docker Desktop

去 [Docker 官网](https://www.docker.com/products/docker-desktop/) 下载安装。

验证安装：
```bash
docker --version
docker compose version
```

### 0.3 启动 Superset

框架需要两个 Superset 实例（4.1 和 6.0）：

```bash
# 进入项目目录
cd superset-docs

# 启动 4.1（首次启动需要 4-5 分钟加载示例数据）
cd superset-4.1 && docker compose up -d
cd ..

# 启动 6.0
cd superset-6.0 && docker compose up -d
cd ..

# 验证服务是否健康
curl http://localhost:18088/health   # 4.1 → 返回 OK
curl http://localhost:18089/health   # 6.0 → 返回 OK
```

> 💡 **小提示**：首次启动后，`docker compose ps` 查看 `superset-init` 容器状态，显示 `Exited (0)` 才算完全就绪。

### 0.4 安装 E2E 依赖

```bash
cd e2e

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（chromium）
playwright install chromium
```

> 💡 **Windows 用户注意**：如果 `playwright install` 失败，不要加 `--with-deps`，手动下载浏览器放到 `%USERPROFILE%\AppData\Local\ms-playwright\`。

---

## 第 1 步：跑第一个测试

### 1.1 跑 smoke 测试

```bash
cd e2e
python run.py -m smoke
```

等待一会儿，应该看到类似输出：

```
============================= test session starts ==============================
platform win32 -- Python 3.12.1
collected 8 items

tests/health/test_health.py::test_health[4.1] PASSED
tests/health/test_health.py::test_health[6.0] PASSED
tests/auth/test_auth.py::test_login_admin[4.1] PASSED
tests/auth/test_auth.py::test_login_admin[6.0] PASSED
...
============================= 8 passed in 45.23s ==============================
```

### 1.2 看测试报告

```bash
# 生成 Allure HTML 报告
python run.py --allure

# 查看报告（浏览器会自动打开）
allure serve reports/allure-results
```

> 💡 **小提示**：如果 `allure` 命令找不到，运行 `npm install -g allure-commandline` 安装。

### 1.3 理解报告内容

打开 Allure 报告后，可以看到：
- **Overview**：测试通过率、耗时统计
- **Suites**：按测试文件分组的测试用例
- **Timeline**：测试执行时间线
- 点击单个测试用例可以看到详细步骤和截图

---

## 第 2 步：理解测试结构

### 2.1 目录结构

```
e2e/
├── run.py                  # 🚀 入口命令（所有测试都从这里跑）
├── config/                 # ⚙️ 配置文件（环境、用户、超时等）
│   ├── config.yaml         # base 配置
│   └── settings.py         # 配置加载逻辑
├── fixtures/               # 🛠️ pytest 夹具（浏览器、登录等）
│   └── playwright_fixtures.py
├── pages/                  # 📄 Page Object（封装页面交互）
│   ├── login_page.py
│   └── dashboard_page.py
├── tests/                  # 🧪 测试用例（业务场景）
│   ├── auth/
│   ├── dashboards/
│   └── health/
├── utils/                  # 🛠️ 工具函数（高亮、BDD、稳定性）
│   ├── page_actions.py
│   └── bdd.py
└── reports/                # 📊 测试报告（自动生成）
```

### 2.2 核心概念

#### 什么是 Fixture？

Fixture 是 pytest 的「夹具」，用来准备测试环境。比如：
- `page` fixture：提供一个干净的浏览器页面
- `logged_in_page` fixture：提供一个已经登录的页面
- `superset_instance` fixture：提供当前测试的 Superset 实例（4.1 或 6.0）

测试用例通过函数参数获取 fixture：

```python
def test_login(logged_in_page):
    # logged_in_page 就是一个已经登录的浏览器页面
    assert "/login/" not in logged_in_page.url
```

#### 什么是 Page Object？

Page Object 把页面交互封装成类方法，比如：

```python
class LoginPage:
    def login(self, username, password):
        # 输入用户名、密码、点击登录
        ...

class DashboardPage:
    def goto(self):
        # 导航到 dashboard 列表页
        ...
```

好处：测试用例不用关心具体的元素选择器，只调用高层方法。

#### 什么是 Page Actions？

Page Actions (`pa`) 是 Playwright 操作的增强版：
- `pa.click(page, selector)` → 高亮元素 + 记录步骤 + 点击
- `pa.fill(page, selector, value)` → 高亮 + 记录 + 填值

---

## 第 3 步：写第一个测试

### 3.1 模板：最简单的测试

在 `tests/` 目录下创建 `test_my_first.py`：

```python
import pytest


@pytest.mark.smoke
def test_my_first_test(superset_instance, logged_in_page):
    """Scenario: My first test
    Given 已登录 admin
    When 访问首页
    Then 页面包含 Superset 标题
    """
    from pages.dashboard_page import DashboardPage
    
    # 创建 DashboardPage 对象
    page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    
    # 导航到 dashboard 列表
    page.goto()
    
    # 验证 dashboard 数量 > 0
    assert page.dashboard_count() > 0, "至少应该有一个 dashboard"
```

### 3.2 运行测试

```bash
python run.py tests/test_my_first.py
```

### 3.3 测试结构详解

```python
# 1. 导入 pytest（必须）
import pytest

# 2. 加标记（用于筛选测试）
@pytest.mark.smoke

# 3. 测试函数名必须以 test_ 开头
def test_my_first_test(
    superset_instance,    # fixture：当前 Superset 实例（4.1 或 6.0）
    logged_in_page        # fixture：已登录的浏览器页面
):
    """4. docstring 描述测试场景（BDD 风格）"""
    
    # 5. 业务逻辑
    from pages.dashboard_page import DashboardPage
    page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    page.goto()
    assert page.dashboard_count() > 0
```

### 3.4 常用断言

```python
# 基本断言
assert page.dashboard_count() > 0
assert "Superset" in page.title()

# 带错误信息的断言（推荐）
assert page.dashboard_count() > 0, f"预期至少 1 个 dashboard，实际 {page.dashboard_count()} 个"

# 使用 BDD 断言（更可读）
from utils.bdd import assert_with_msg
assert_with_msg(page.dashboard_count() > 0, "dashboard 列表为空")
```

---

## 第 4 步：调试测试

### 4.1 有头模式（看测试在做什么）

```bash
python run.py --headed tests/test_my_first.py
```

会弹出一个浏览器窗口，你可以看到：
- 测试自动打开页面
- 操作的元素会被红色框高亮
- 操作步骤会显示在元素角标上

### 4.2 断点调试

在测试代码中加 `breakpoint()`：

```python
def test_my_first_test(superset_instance, logged_in_page):
    from pages.dashboard_page import DashboardPage
    page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    
    breakpoint()  # 在这里停住
    
    page.goto()
    assert page.dashboard_count() > 0
```

运行后会进入调试模式，可以：
- 查看变量值（输入 `page.url`）
- 执行 Playwright 命令（输入 `page.locator(".dashboard-item").count()`）
- 继续执行（输入 `c`）

### 4.3 查看失败截图

测试失败时，框架会自动截图：

```bash
# Windows
explorer e2e\reports\screenshots

# macOS
open e2e/reports/screenshots
```

截图文件名格式：`test_name__version__timestamp.png`

---

## 第 5 步：进阶技巧

### 5.1 BDD 风格测试

使用 `given/when/then` 让测试更可读：

```python
import pytest
from utils import page_actions as pa
from utils.bdd import given, when, then, and_


@pytest.mark.dashboard
@pytest.mark.smoke
def test_dashboard_list(superset_instance, logged_in_page):
    """Scenario: Dashboard list loads correctly
    
    Given 已登录 admin 用户
    When 访问 dashboard 列表页
    Then 页面显示至少 1 个 dashboard
    And 每个 dashboard 都有标题
    """
    from pages.dashboard_page import DashboardPage
    
    with given("已登录 admin 用户", page=logged_in_page):
        page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    
    with when("访问 dashboard 列表页", page=page, focus="a[href*='/dashboard']"):
        page.goto()
    
    with then("页面显示至少 1 个 dashboard", screenshot=True):
        count = page.dashboard_count()
        assert count > 0, f"预期至少 1 个，实际 {count} 个"
    
    with and_("每个 dashboard 都有标题", page=page):
        titles = page.dashboard_titles()
        assert all(titles), "发现空标题的 dashboard"
```

### 5.2 多用户测试

测试不同角色的用户：

```python
@pytest.mark.multi_user
def test_viewer_cannot_access_admin_panel(login_as_role, superset_instance):
    """验证 viewer 用户看不到 admin 面板"""
    # 获取 viewer 用户的页面
    viewer_page = login_as_role("viewer")
    
    # 验证 viewer 看不到 admin 菜单
    assert viewer_page.locator("[data-test='admin-menu']").count() == 0
```

### 5.3 跑性能测试

```bash
# 安装性能测试依赖
pip install -r perf/requirements.txt

# 跑 k6 测试（dashboard 列表，300 用户）
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js

# 跑 Locust 测试（多角色，200 用户）
bash perf/tools/run_locust.sh

# 看 Locust 报告
start perf/reports/locust/report_6.0.html
```

### 5.4 切换环境

```bash
# 默认 dev 环境
python run.py -m smoke

# 切换到 SIT 环境
python run.py --env sit -m smoke

# 查看当前环境的用户池
python run.py --env sit --list-users
```

---

## 🎯 练习任务

### 练习 1：写一个测试

场景：登录 admin，访问数据库列表，验证至少有 1 个数据库。

提示：参考 `tests/databases/test_databases.py`

### 练习 2：调试一个失败的测试

故意写一个会失败的测试：

```python
def test_failure_example(logged_in_page):
    """故意失败的测试"""
    assert 1 == 2
```

运行后查看截图和 Allure 报告。

### 练习 3：用 BDD 风格重写测试

把练习 1 的测试改写成 BDD 风格。

---

## 📖 学习资源

| 资源 | 说明 |
|-----|------|
| [QUICKSTART.md](./QUICKSTART.md) | 一页式快速开始 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构设计（为什么这么设计） |
| [REPORTS.md](./REPORTS.md) | 报告查看指南 |
| [Playwright 文档](https://playwright.dev/python/docs/intro) | Playwright 官方文档 |
| [pytest 文档](https://docs.pytest.org/) | pytest 官方文档 |
| [Allure 文档](https://docs.qameta.io/allure/) | Allure 报告文档 |

---

## 💡 常见问题

### Q1：为什么测试跑这么慢？

A：首次启动需要加载 Docker 容器和示例数据（4-5 分钟）。后续复用模式会快很多。

### Q2：怎么跳过某个测试？

A：在测试函数前加 `@pytest.mark.skip(reason="...")`

### Q3：怎么只跑 6.0？

A：`python run.py --instance 6.0`

### Q4：怎么跑指定的测试文件？

A：`python run.py tests/auth/test_auth.py`

### Q5：怎么看测试的详细输出？

A：`python run.py -v` 或 `python run.py -s`（显示打印）

---

## 附录：离线 Examples 数据导入

### A.1 什么是 Examples？

Examples 是 Superset 内置的示例数据，用于演示各种图表类型和功能。包括：
- 婴儿姓名（birth_names）- 时间序列
- 能源结构（energy）- 雷达图
- 销售数据（sales）- 仪表盘
- COVID 疫苗数据（covid_vaccines）
- 旧金山地图（san_francisco）- 地图
- Slack 数据集（多表关联）

### A.2 为什么需要离线导入？

**问题背景**：默认情况下，Superset 从 GitHub 下载 examples 数据：
- 网络不稳定时下载失败
- GitHub 在某些地区访问受限
- CI/CD 环境无法访问外网

**解决方案**：将 examples 数据放在本地，通过 volume 挂载到容器，实现完全离线加载。

### A.3 目录结构

```
superset-docs/
├── example-data/              ← 示例数据文件（CSV/JSON）
│   ├── birth_names.csv
│   ├── energy.json.gz
│   ├── sales.csv
│   └── datasets/examples/     ← 更多数据集
│       ├── covid_vaccines.csv
│       └── slack/            ← Slack 多表
├── superset-4.1/             ← Superset 4.1
│   ├── docker-compose.yml
│   └── pythonpath/
│       └── load_examples_init.py  ← 加载脚本
└── superset-6.0/             ← Superset 6.0
    ├── docker-compose.yml
    └── pythonpath/
        └── load_examples_init.py  ← 加载脚本
```

### A.4 加载机制详解

#### 4.1 vs 6.0 的区别

| 维度 | 4.1 | 6.0 |
|-----|------|------|
| 协议 | `file://` URL | `http://localhost:18099/` |
| 原因 | `get_example_url` 不校验 URL | `marshmallow.fields.URL()` 强制 http(s) |
| 镜像要求 | 任意 | 必须 `user: root`（需要写 venv） |
| 图表修复 | 不需要 | 自动对齐 `query_context.datasource.id` |

#### 加载流程（以 4.1 为例）

```
docker compose up -d
        ↓
superset-init 容器启动
        ↓
安装依赖（psycopg2-binary, redis）
        ↓
superset db upgrade（数据库迁移）
        ↓
superset init（初始化）
        ↓
创建 admin 用户
        ↓
python load_examples_init.py ← 关键！
        ↓
superset-init 退出（Exited 0）
        ↓
superset 容器启动
```

### A.5 load_examples_init.py 做了什么？

这个脚本完成了以下关键步骤：

```python
# 1. 修复 examples 数据库的 sqlalchemy_uri
#    默认是 sqlite，改成 postgresql
examples_db.sqlalchemy_uri = "postgresql+psycopg2://superset:superset@postgres:5432/superset"

# 2. 覆盖 BASE_URL，优先从本地加载
import superset.examples.helpers as _ex_helpers
_ex_helpers.BASE_URL = "/app/local_samples/"

# 3. 修复 SqlaTable.schema
#    从 SQLite 默认 "main" → PostgreSQL 默认 "public"
for t in stale_tables:
    t.schema = "public"

# 4. 调用 load_examples_run 加载全部示例
from superset.cli.examples import load_examples_run
load_examples_run()

# 5. 6.0 额外修复图表 datasource_id 不一致问题
```

### A.6 环境变量说明

```bash
# 本地示例数据目录（挂载到容器内）
SUPERSET_LOCAL_SAMPLES_DIR: "/app/local_samples"

# GitHub 回退 URL（本地加载失败时使用）
SUPERSET_EXAMPLES_BASE_URL: "https://raw.githubusercontent.com/apache-superset/examples-data/master/"

# Examples 数据库 URI（改成 PostgreSQL）
EXAMPLES_DB_URI: "postgresql+psycopg2://superset:superset@postgres:5432/superset"
```

### A.7 如何验证 Examples 加载成功？

```bash
# 方法 1：检查 init 容器日志
docker compose -f superset-4.1/docker-compose.yml logs superset-init | grep "done"

# 方法 2：登录 Superset Web UI
# 访问 http://localhost:18088 → 登录 admin/admin
# 导航到 Charts / Dashboards，应该能看到示例图表

# 方法 3：检查数据库中的表
docker exec superset-4.1-postgres psql -U superset -d superset -c "\dt" | grep -E "birth|energy|sales"
```

### A.8 如何重新加载 Examples？

如果需要重新加载（例如修改了自定义数据集）：

```bash
# 方法 1：完全重建（清空数据）
docker compose -f superset-4.1/docker-compose.yml down -v
docker compose -f superset-4.1/docker-compose.yml up -d

# 方法 2：只重新运行 init 容器
docker compose -f superset-4.1/docker-compose.yml up --force-recreate superset-init

# 方法 3：手动在容器内执行
docker exec -it superset-4.1 bash
python /app/pythonpath/load_examples_init.py
```

### A.9 如何添加自定义数据集？

1. **准备数据文件**：CSV 或 JSON 格式，放入 `example-data/` 目录

2. **注册数据集**：在 `load_examples_init.py` 中添加注册逻辑

3. **重建容器**：
   ```bash
   docker compose -f superset-4.1/docker-compose.yml down -v
   docker compose -f superset-4.1/docker-compose.yml up -d
   ```

### A.10 常见问题

**Q1：init 容器一直处于 Running 状态？**

A：Examples 加载可能需要 5-10 分钟。如果是网络下载，可能更久。可以查看日志：
```bash
docker logs superset-4.1-init -f
```

**Q2：Examples 加载失败，报 "No such file"？**

A：检查 volume 挂载是否正确：
```bash
docker inspect superset-4.1-init | grep -A5 "Mounts"
```
确保 `../example-data:/app/local_samples:ro` 正确挂载。

**Q3：如何切换在线/离线模式？**

A：修改 `docker-compose.yml` 中的 `SUPERSET_LOCAL_SAMPLES_DIR`：
- 离线模式：`SUPERSET_LOCAL_SAMPLES_DIR: "/app/local_samples"`
- 在线模式：注释掉或设为空

**Q4：Examples 数据存放在哪里？**

A：数据存储在 PostgreSQL 数据库中，不是文件系统。Volume `superset_4_1_db` 持久化了数据库数据。

---

## 🎉 恭喜！

你已经学会了：
1. 环境准备和启动
2. 跑测试和看报告
3. 理解测试结构
4. 写简单测试
5. 调试测试
6. BDD 风格和多用户测试

接下来可以：
- 查看 [ARCHITECTURE.md](./ARCHITECTURE.md) 理解设计理念
- 阅读 [QUICKSTART.md](./QUICKSTART.md) 掌握常用命令
- 尝试写更多测试用例