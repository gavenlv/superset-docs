# Superset E2E 自动化测试

针对 Superset 4.1 和 6.0 的端到端自动化测试，支持 UI、API、数据库多层验证。

## 技术栈

| 关注点 | 选型 |
| --- | --- |
| 核心框架 | pytest 8.3 |
| 浏览器自动化 | Playwright 1.48 |
| HTTP 客户端 | httpx |
| 报告 | Allure + pytest-allure |
| 重试 | pytest-rerunfailures + tenacity |
| 编排 | docker compose CLI |

## 目录结构

```
e2e/
├── conftest.py              # 顶层 fixture 入口
├── run.py                   # CLI 入口
├── pyproject.toml           # pytest 配置 + 依赖
├── requirements.txt         # 显式依赖列表
├── config/
│   ├── settings.py          # 配置加载（yaml + env）
│   └── config.yaml          # 默认配置（端口、超时等）
├── fixtures/
│   ├── conftest.py          # 服务生命周期 fixture
│   ├── playwright_fixtures.py  # 浏览器、登录、截图 hook
│   └── allure_config.py     # Allure 环境与分类（运行时生成）
├── pages/                   # Page Object Model
│   ├── login_page.py
│   ├── dashboard_page.py
│   ├── explore_page.py
│   └── sqllab_page.py
├── utils/
│   ├── process.py           # 子进程 / HTTP 等待
│   ├── service.py           # docker compose 编排
│   ├── stability.py         # 健壮选择器、重试 helper
│   └── logging.py
├── tests/                   # 测试用例
│   ├── conftest.py
│   ├── health/              # 健康检查
│   ├── auth/                # 登录 / 登出
│   ├── dashboards/          # 仪表盘
│   ├── charts/              # 单图表
│   ├── sqllab/              # SQL Lab
│   └── databases/           # 数据库 / 数据集
└── reports/                 # 报告输出（运行时生成，已 gitignore）
    ├── allure-results/      # Allure 原始数据（.gitkeep 占位）
    ├── allure-report/       # Allure HTML（.gitkeep 占位）
    └── screenshots/         # 失败截图（.gitkeep 占位）
```

## 快速开始

### 1. 安装依赖

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium
```

> Windows 上如遇 `playwright install` 失败，先执行 `playwright install-deps`（管理员），
> 或下载 [浏览器](https://playwright.dev/python/docs/browsers#chromium-on-windows) 手动放到用户目录。

### 2. 启动 Superset

如果服务已运行（端口 18088 / 18089），可直接复用；否则：

```bash
# 启动 4.1
cd ../superset-4.1 && docker compose up -d && cd -

# 启动 6.0
cd ../superset-6.0 && docker compose up -d && cd -
```

### 3. 运行测试

```bash
# 复用现有服务跑 smoke
python run.py -m smoke

# 冷启动模式：先 down -v 再 up -d，保证从零加载示例数据
python run.py --mode cold -m smoke

# 只跑 4.1
python run.py --instance 4.1

# 跑全部并生成 Allure 报告
python run.py --allure

# 指定关键字
python run.py -k dashboard
```

### 4. 查看报告

```bash
# 启动 allure 服务（推荐）
allure serve reports/allure-results

# 或生成静态 HTML
allure generate reports/allure-results -o reports/allure-report --clean
```

## 配置

通过 `config/config.yaml` 或环境变量覆盖：

| 环境变量 | 说明 | 默认 |
| --- | --- | --- |
| `E2E_MODE` | `cold` / `reuse` | `reuse` |
| `E2E_BROWSER` | `chromium` / `firefox` / `webkit` | `chromium` |
| `E2E_HEADLESS` | `1` / `0` | `1` |
| `E2E_CLEANUP` | cold 模式结束后是否清理容器 | `1` |
| `E2E_RERUNS` | 失败重试次数 | `2` |
| `E2E_PAGE_TIMEOUT_MS` | 页面操作超时 | 30000 |
| `E2E_NAV_TIMEOUT_MS` | 导航超时 | 60000 |
| `E2E_ADMIN_USER` | admin 用户名 | `admin` |
| `E2E_ADMIN_PASSWORD` | admin 密码 | `admin` |
| `E2E_BASE_URL_4_1` | 4.1 base URL | `http://localhost:18088` |
| `E2E_BASE_URL_6_0` | 6.0 base URL | `http://localhost:18089` |

## 稳定性策略

1. **重试**：`pytest-rerunfailures` 失败后默认重试 2 次，每次间隔 3 秒
2. **超时**：每个用例 120s 超时，避免挂死
3. **健壮选择器**：`utils/stability.py::robust_click` 尝试多个 selector
4. **自动等待**：Playwright 默认 auto-wait + locator 隐式等待
5. **失败截图**：失败时自动附加全屏截图 + HTML 到 Allure
6. **偶发错误容忍**：`429 / Mapbox rate limit` 不会让测试 fail

## 标记 (markers)

| Marker | 说明 |
| --- | --- |
| `smoke` | 冒烟测试，每个版本必跑 |
| `auth` | 认证 |
| `dashboard` | 仪表盘 |
| `chart` | 图表 |
| `sqllab` | SQL Lab |
| `database` | 数据库 / 数据集 |
| `health` | 健康检查 |
| `slow` | 耗时较长 |

## CI 集成

```yaml
# GitHub Actions 示例
- name: Run E2E (cold)
  run: |
    cd e2e
    pip install -r requirements.txt
    playwright install --with-deps chromium
    python run.py --mode cold --allure
- name: Upload Allure
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: allure-results
    path: e2e/reports/allure-results
```

## 故障排查

- **浏览器无法启动**：执行 `playwright install --with-deps chromium`；Windows 跳过 `--with-deps`
- **`No module named config`**：在 `e2e/` 目录下运行 `python run.py`，不要在其他目录跑
- **冷启动超时**：`init` 容器首次加载示例需要 4-5 分钟，确认日志后调整 `cold_start_instance` 中的 timeout
- **测试 fail / 截图**：`reports/screenshots/` 下查看全屏截图，`reports/allure-results/` 包含 HTML 快照
- **Mapbox 429**：已知限流问题，测试已容忍；如需彻底解决请配置 `MAPBOX_API_KEY`

## 清理临时文件

测试运行会在 `reports/` 下生成临时产物（allure-results、截图、HTML 报告），这些文件已通过 `.gitignore` 忽略，不会进入版本控制。

手动清理：

```bash
# 清理测试产物（保留目录结构）
cd e2e
rm -rf reports/allure-results/* reports/allure-report/* reports/screenshots/*.png
# 保留 .gitkeep
touch reports/allure-results/.gitkeep reports/screenshots/.gitkeep

# 清理 Python 缓存
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .ruff_cache .mypy_cache

# 清理 Playwright 缓存（可选）
rm -rf .playwright
```

仓库中不应残留调试脚本（如 `debug_*.py`、`verify_*.py`），如需临时调试请放到 `e2e/` 之外或用完即删。
