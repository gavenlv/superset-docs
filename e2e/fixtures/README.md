# fixtures/

pytest fixtures 集中目录。支持服务生命周期、Playwright 浏览器、**多用户并发**、Allure 报告附件。

## 目录

- [文件索引](#文件索引)
- [服务生命周期 fixture](#服务生命周期-fixture)
- [Playwright 浏览器 fixture](#playwright-浏览器-fixture)
- [多用户 fixture（重点）](#多用户-fixture重点)
- [Allure 报告附件](#allure-报告附件)
- [自定义 marker](#自定义-marker)
- [添加新 fixture](#添加新-fixture)

## 文件索引

| 文件                       | 提供的 fixture                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------- |
| `conftest.py`              | `test_config`、`instance_4_1`、`instance_6_0`、`superset_instance`（参数化）、`_setup_logging`            |
| `playwright_fixtures.py`   | `playwright`、`browser`、`context`、`page`、`logged_in_page`、`user_pool`、`login_as_role`、`multi_user_pages` |
| `allure_config.py`         | `_allure_environment`（自动）、`pytest_runtest_makereport`（自动打标签）                                |

## 服务生命周期 fixture

### `superset_instance`（参数化）

```python
@pytest.mark.smoke
def test_xxx(superset_instance: ServiceState):
    # 自动遍历 4.1 与 6.0
    base_url = superset_instance.instance.base_url
    ...
```

由 `instance_4_1` / `instance_6_0` 提供底层状态，根据 `E2E_MODE` 自动选择 `cold_start_instance` 或 `reuse_instance`。

`ServiceState` 包含：

| 字段                  | 说明                                    |
| --------------------- | --------------------------------------- |
| `instance`            | `SupersetInstance`（name/version/base_url/compose_dir 等） |
| `started_by_us`       | 是否本次测试启动的（cold 模式 = True） |
| `health_check_seconds`| 健康检查耗时                            |
| `api_token_len`       | admin JWT 长度                          |

### `instance_4_1` / `instance_6_0`（会话级）

只跑单一版本时直接用：

```python
def test_4_1_only(instance_4_1):
    base = instance_4_1.instance.base_url
```

## Playwright 浏览器 fixture

| Fixture            | 作用域       | 说明                                  |
| ------------------ | ------------ | ------------------------------------- |
| `playwright`       | session      | `sync_playwright()` 入口              |
| `browser`          | session      | 浏览器实例（chromium/firefox/webkit）  |
| `context`          | function     | 隔离的 BrowserContext（每个 case 新建） |
| `page`             | function     | 测试 Page                              |
| `logged_in_page`   | function     | 已登录 admin 的 Page（最常用）         |

### `logged_in_page`

```python
def test_xxx(logged_in_page, superset_instance):
    # page 已自动登录为 admin
    logged_in_page.goto(...)
```

依赖 `context` + `_login` 内部步骤，跳过登录页直接进入受保护页面。

## 多用户 fixture（重点）

`playwright_fixtures.py` 提供**两个工厂 fixture**用于多用户并发 E2E。

### `user_pool`（暴露单例）

```python
def test_xxx(user_pool):
    viewers = user_pool.users("viewer")
    assert len(viewers) >= 5
```

### `login_as_role`（工厂）

按角色 + 索引取一个 user，登录到**独立 BrowserContext**（互不干扰）。

```python
def test_two_viewers(login_as_role, superset_instance):
    """2 个不同 viewer 同时操作。"""
    p1 = login_as_role("viewer", index=0)   # viewer[0]
    p2 = login_as_role("viewer", index=1)   # viewer[1]

    base = superset_instance.instance.base_url
    p1.goto(f"{base}/dashboard/list/")
    p2.goto(f"{base}/dashboard/list/")
    # 两个 page 独立 cookies/localStorage
```

支持的调用方式：

| 调用 | 行为 |
| --- | --- |
| `login_as_role("viewer")` | 随机取一个 viewer |
| `login_as_role("viewer", index=0)` | 固定取 viewer[0]（确定性） |
| `login_as_role("admin", index=1)` | admin[1] |
| `login_as_role("analyst")` | analyst 随机 |

测试结束自动 close 所有 page + context。

### `multi_user_pages`（参数化）

通过 `@pytest.mark.multi_user(N)` 拿 N 个不同 user 的 page list。

```python
@pytest.mark.multi_user(3)
def test_three_users(multi_user_pages, superset_instance):
    """3 个不同 viewer 同时登录。"""
    p1, p2, p3 = multi_user_pages
    for p in (p1, p2, p3):
        assert "/login/" not in p.url
```

或用 parametrize：

```python
@pytest.mark.parametrize("multi_user_pages", [5], indirect=True)
def test_five_users(multi_user_pages):
    p1, p2, p3, p4, p5 = multi_user_pages
```

> 默认 role = `viewer`。如需其他角色，写 fixture 参数扩展。

### 多用户 vs 性能压测

| 场景 | 用什么 |
| --- | --- |
| E2E 验证 2~5 个 user session 隔离 | `login_as_role` / `multi_user_pages` |
| 性能压测 100+ VU 并发 | 性能脚本（Locust/k6）+ `utils.user_pool.user_pool` |
| API 压测 | `user_pool.token_for()` 拿 JWT |

## Allure 报告附件

`pytest_runtest_makereport` hook 自动：

1. 测试失败时全屏截图 → `reports/screenshots/<test>__<ver>__<ts>.png`
2. 附加 PNG 到 Allure
3. 附加当前 HTML 到 Allure

自动打标签：

- `instance: 4.1` / `6.0`
- `version: 4.1.1` / `6.0.0`
- 所有 marker

## 自定义 marker

`pyproject.toml` 声明：

```toml
[tool.pytest.ini_options]
markers = [
    "smoke: 冒烟测试",
    "slow: 耗时较长",
    "multi_user(N): 多用户并发 N 个 user",
    # ...
]
```

`multi_user(N)` marker 用法见上。

## 添加新 fixture

- **会话级**（一次性启动）：`scope="session"`
- **用例级**：默认 `function` scope
- **工厂 fixture**：`yield <callable>`，teardown 用 try/finally 清理
- **跨用例共享的状态**放 `conftest.py`，避免重复创建
- **多用户 fixture** 优先复用 `utils.user_pool.user_pool`，不要新建池
- 文档追加到本文档表格
