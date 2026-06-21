# Superset E2E + 性能测试 一页式快速开始

> 5 分钟跑通 E2E + 性能基线，覆盖 Superset 4.1 / 6.0 双版本。
> 详细文档：[e2e/README.md](../README.md)、[perf/README.md](../perf/README.md)。

## 0. 前置要求

| 工具 | 版本 | 备注 |
| --- | --- | --- |
| Docker Desktop | 24+ | 两个 Superset 同时跑约 12 GB 内存 |
| Python | 3.10+（推荐 3.12） | |
| k6 | latest | 可选；性能测试用 |
| Locust | 2.x | `pip install locust` |

## 1. 启动 Superset（首次 5 min）

```bash
git clone <repo>
cd superset-docs

# 启动 4.1
cd superset-4.1 && docker compose up -d
cd ..

# 启动 6.0
cd superset-6.0 && docker compose up -d

# 等 init 容器退出（约 4-5 分钟；只看示例数据加载）
docker compose -f superset-4.1/docker-compose.yml ps
docker compose -f superset-6.0/docker-compose.yml ps
# STATUS = Exited (0) 才算 OK

# 验证健康
curl http://localhost:18088/health   # 4.1 → OK
curl http://localhost:18089/health   # 6.0 → OK
```

## 2. 装 E2E 依赖

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium
```

## 3. 跑 E2E smoke

```bash
# 复用现有服务（默认；推荐首次跑）
python run.py -m smoke

# 冷启动（先 down -v 再 up -d，从零加载示例）
python run.py --mode cold -m smoke

# 只跑 6.0
python run.py --instance 6.0 -m smoke

# 生成 Allure HTML 报告
python run.py --allure
# 报告：reports/allure-report/
```

## 4. 跑多用户 E2E

```bash
# 3 个 viewer 同时登录（验证 session 隔离）
python run.py -m multi_user

# 切到 SIT 环境
python run.py --env sit -m multi_user

# 看当前 env 的 user_pool
python run.py --list-users
```

## 5. 跑性能压测

```bash
cd e2e
pip install -r perf/requirements.txt

# k6（推荐先用这个；3 分钟出结果）
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js    # 300 VU / 3 min
bash perf/tools/run_k6.sh perf/k6/scripts/chart_list.js        # 200 VU / 2 min
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js        # 100 VU / 5 min

# Locust 多角色 200 VU / 10 min
bash perf/tools/run_locust.sh
# Web UI: bash perf/tools/run_locust.sh --web  → http://localhost:8089

# 对比基线（重点端点 strict 模式）
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail
```

## 6. 切换环境

```bash
# 4 套环境：dev / sit / uat / prod
python run.py --env sit -m smoke
E2E_ENV=uat python run.py -m multi_user
E2E_ENV=uat bash perf/tools/run_locust.sh

# 列出当前 env 的 user_pool
python run.py --env sit --list-users
```

`config.sit.yaml` / `config.uat.yaml` / `config.prod.yaml` 自动覆盖 base；`E2E_*` 环境变量优先级最高。

## 7. 写新测试（5 行模板）

```python
import pytest
from utils import page_actions as pa


@pytest.mark.dashboard
@pytest.mark.smoke
def test_dashboard_list(superset_instance, logged_in_page):
    """Scenario: dashboard 列表加载
    Given 已登录 admin
    When 访问 dashboard 列表
    Then 显示至少 1 个 dashboard
    """
    from pages.dashboard_page import DashboardPage
    page = DashboardPage(logged_in_page, superset_instance.instance.base_url)
    page.goto()
    assert page.dashboard_count() > 0
```

要点：
- 用 `superset_instance`（自动遍历 4.1 / 6.0）
- UI 操作走 `pa.*`（`pa.click` / `pa.fill` / `pa.goto`）
- 用 Page Object（`pages/<page>_page.py`）
- 详情：[e2e/README.md §编写新测试](../README.md#编写新测试)

## 8. 常见命令速查

```bash
# E2E
python run.py -m smoke                       # smoke 用例
python run.py -m auth                        # auth 用例
python run.py -k dashboard                   # 关键字过滤
python run.py --instance 6.0                 # 只跑 6.0
python run.py --mode cold -m smoke           # 冷启动
python run.py --allure                       # 生成 Allure
python run.py --env sit -m multi_user        # SIT 上跑多用户
python run.py --list-users                   # 列 user_pool
python run.py --headed -m smoke              # 有头模式（看高亮）

# 性能
bash perf/tools/run_locust.sh                                    # Locust 200 VU / 10 min
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js      # k6 300 VU / 3 min
python perf/tools/compare_baseline.py --version 6.0 --current .../current_6.0.json --strict
python perf/tools/save_baseline.py --version 6.0 --current ...   # 存为新基线

# 元测试
pytest perf/tests/ -v                       # 18 个元测试
```

## 9. 故障排查

| 症状 | 解决 |
| --- | --- |
| `playwright install` 失败 | Windows 不加 `--with-deps`；手动放浏览器到 `ms-playwright/` |
| `No module named 'config'` | 必须在 `e2e/` 目录跑 `python run.py` |
| 冷启动超时 | 首次 4-5 min 正常 |
| `user_pool empty` | `python run.py --list-users` 检查；SIT/UAT 需写 `config.<env>.yaml` |
| `unsupported E2E_ENV` | 只支持 dev/sit/uat/prod |
| `CSRF token is missing` | 写操作需 CSRF；走 API |
| `k6: not found` | `apt-get install k6` / `brew install k6` |
| `locust: GBK` | Windows: `set PYTHONUTF8=1` + `set PYTHONIOENCODING=utf-8` |

更多：[e2e/README.md §故障排查](../README.md#故障排查)。

## 10. 下一步

- 详细 E2E：[e2e/README.md](../README.md)
- 详细性能：[perf/README.md](../../perf/README.md)、[perf/PLAN.md](../../perf/PLAN.md)
- 多环境 / 多用户：[perf/docs/MULTI_ENV_USER.md](../../perf/docs/MULTI_ENV_USER.md)
- Jenkins 部署：[perf/docs/JENKINS.md](../../perf/docs/JENKINS.md)
- 顶层导航：[../../README.md](../../README.md)
