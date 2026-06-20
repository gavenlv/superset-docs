# pages/

Page Object Model，封装 Superset 各页面的 UI 操作。所有 Page Object 都做跨版本兼容（4.1 SSR vs 6.0 SPA + Ant Design）。

## 文件

| 文件                | 封装页面                                | 关键 API                                                |
| ------------------- | --------------------------------------- | ------------------------------------------------------- |
| `login_page.py`     | `/login/`                               | `goto()`、`login(user, pwd)`、`login_expect_fail(...)` |
| `dashboard_page.py` | `/superset/dashboard/{id}/`             | `goto()`、`wait_for_charts(n)`、`error_messages()`     |
| `explore_page.py`   | `/superset/explore/?slice_id=N`         | `goto_chart(id)`、`wait_chart_rendered()`               |
| `sqllab_page.py`    | `/sqllab/`                              | `goto()`、`type_query()`、`run_query()`、`wait_results()` |

## 用法

```python
from pages.dashboard_page import DashboardPage

def test_open_dashboard(superset_instance, logged_in_page):
    dp = DashboardPage(
        logged_in_page,
        superset_instance.instance.base_url,
        dashboard_id=1,
    )
    dp.goto()
    dp.wait_loaded()
    dp.wait_for_charts(2, timeout=20000)
```

## 跨版本兼容约定

- **选择器多路**：优先 `name` 4.1 风格，再降级到 `id` 6.0 风格
- **事件等待**：用 `domcontentloaded` 而非 `load`（避免静态资源超时）
- **轮询等待**：用 `utils.stability.wait_for` 替代 Playwright `wait_for_selector`
- **超时配置**：默认 30s，SQL Lab 等慢页面用 45-60s

## 添加新 Page Object

1. 继承 `Page` 句柄 + `base_url` 构造
2. 所有方法返回 `self`（链式调用）
3. 写完一个跨版本兼容层
4. 在 `pages/README.md` 表格中追加
