# utils/

通用工具函数。

## 文件

| 文件           | 职责                                                       |
| -------------- | ---------------------------------------------------------- |
| `process.py`   | 子进程调用、容器状态查询、HTTP 健康等待                    |
| `service.py`   | docker compose 编排（cold / reuse）、ServiceState 数据类   |
| `stability.py` | `wait_for` 轮询等待、`robust_click` 多 selector 健壮点击   |
| `logging.py`   | 日志初始化（彩色输出、level 切换）                         |

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

## 添加新 helper

新工具应放在 `utils/` 下，**不依赖** `fixtures/` 或 `tests/`，确保可复用性。文档请追加到本文档表格。
