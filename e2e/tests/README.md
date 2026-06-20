# tests/

E2E 测试用例目录，按功能领域划分。

| 子目录          | 标记           | 说明                                | 主要文件                          |
| --------------- | -------------- | ----------------------------------- | --------------------------------- |
| `health/`       | `health` `smoke` | `/health`、登录 API、登录页        | `test_health.py`                  |
| `auth/`         | `auth` `smoke`   | 登录 / 登出 / 凭据错误            | `test_auth.py`                    |
| `databases/`    | `database` `smoke` | 数据库列表、examples URI、datasets | `test_databases.py`               |
| `charts/`       | `chart` `smoke`   | 图表列表、查询数据、Explore 页    | `test_charts.py`                  |
| `dashboards/`   | `dashboard` `smoke` | 仪表盘列表、打开示例仪表盘     | `test_dashboards.py`              |
| `sqllab/`       | `sqllab` `smoke`  | SQL Lab 加载、数据库下拉、查询    | `test_sqllab.py`                  |

## 运行单个模块

```bash
# 仅 health
python run.py -m health

# 仅 sqllab
python run.py -m sqllab

# 仅 dashboards
python run.py -m dashboard
```

详见 [`../README.md`](../README.md#标记-markers)。

## 公共模式

每个测试文件遵循统一模式：

1. `_get_token(base_url)` 内部工具函数：登录获取 JWT
2. `*_list_*(base_url)` 内部工具函数：列资源
3. `class TestXxx`：使用 `pytest` 类组织（仅分组，不共享 setup）
4. 测试方法参数 `superset_instance: ServiceState`：参数化 4.1 / 6.0

## 添加新测试模块

1. 在 `tests/<area>/` 下新建 `test_<name>.py`
2. 在 `pyproject.toml` 的 `markers` 中添加新标记
3. 在本文档表格中追加一行
4. 复用现有 `pages/` Page Object 与 `utils/stability.py` helper
