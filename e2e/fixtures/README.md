# fixtures/

pytest fixtures 集中目录。

## 文件

| 文件                       | 提供的 fixture                                                                                  |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| `conftest.py`              | `test_config`、`instance_4_1`、`instance_6_0`、`superset_instance`（参数化）、`_setup_logging`  |
| `playwright_fixtures.py`   | `playwright`、`browser`、`context`、`page`、`logged_in_page`                                    |
| `allure_config.py`         | `_allure_environment`（自动）、`pytest_runtest_makereport`（自动打标签）                       |

## 关键 fixture

### `superset_instance`（参数化）

```python
@pytest.mark.smoke
def test_xxx(superset_instance: ServiceState):
    # 自动遍历 4.1 与 6.0
    base_url = superset_instance.instance.base_url
    ...
```

由 `instance_4_1` / `instance_6_0` 提供底层状态，根据 `E2E_MODE` 自动选择 `cold_start_instance` 或 `reuse_instance`。

### `logged_in_page`

```python
def test_xxx(logged_in_page, superset_instance):
    # page 已自动登录为 admin
    logged_in_page.goto(...)
```

依赖 `context` + `_login` 内部步骤，跳过登录页直接进入受保护页面。

## 添加新 fixture

- 会话级（一次性启动）：`scope="session"`
- 用例级：默认 `function` scope
- 跨用例共享的状态放 `conftest.py`，避免重复创建
- 文档追加到本文档表格
