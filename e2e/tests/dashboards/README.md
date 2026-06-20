# tests/dashboards/

仪表盘相关测试。

## 用例

| 测试                          | 标记                  | 验证内容                                              |
| ----------------------------- | --------------------- | ----------------------------------------------------- |
| `test_dashboards_list_api`    | `dashboard smoke`     | API 列出仪表盘包含 Sales/Video Game/Slack 等示例      |
| `test_open_example_dashboard` | `dashboard` (参数化)   | 打开 `unicode-test` / `deck` 示例仪表盘，无 5xx 错误 |
| `test_dashboards_list_page`   | `dashboard`           | 仪表盘列表页能正常显示                                |

## 运行

```bash
python run.py -m dashboard
```

## 参数化测试

`test_open_example_dashboard` 使用 `EXAMPLE_DASHBOARDS` 表参数化：

```python
EXAMPLE_DASHBOARDS = [
    ("unicode-test", "Unicode Test"),
    ("deck", "deck.gl Demo"),
]
```

如果某个版本未加载到该 slug，测试会 `pytest.skip` 而不是失败。
