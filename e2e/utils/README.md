# utils/

通用工具函数。

## 文件

| 文件              | 职责                                                       |
| ----------------- | ---------------------------------------------------------- |
| `process.py`      | 子进程调用、容器状态查询、HTTP 健康等待                    |
| `service.py`      | docker compose 编排（cold / reuse）、ServiceState 数据类   |
| `stability.py`    | `wait_for` 轮询等待、`robust_click` 多 selector 健壮点击   |
| `logging.py`      | 日志初始化（彩色输出、level 切换）                         |
| `bdd.py`          | Given/When/Then 上下文管理器 + 焦点高亮 + 截图附件        |
| `page_actions.py` | Playwright 操作的高亮包装（click/fill/hover/...）          |

## 关键 API

### `utils.stability`

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

### `utils.service`

```python
from utils.service import cold_start_instance, reuse_instance, shutdown_instance

# 冷启动
state = cold_start_instance(superset_instance)   # 自动 down -v && up -d
# state.instance / .started_by_us / .health_check_seconds / .api_token_len

# 复用
state = reuse_instance(superset_instance)        # 仅健康检查
```

### `utils.bdd`

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

### `utils.page_actions`（推荐：所有 UI 操作走这里）

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

## 添加新 helper

新工具应放在 `utils/` 下，**不依赖** `fixtures/` 或 `tests/`，确保可复用性。文档请追加到本文档表格。
