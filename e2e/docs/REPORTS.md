# 测试报告查看指南

> E2E + 性能 + 元测试报告 **一站式查看手册**。
> 适用 Superset 4.1 / 6.0 · dev / sit / uat / prod。

## 目录

- [报告类型总览](#报告类型总览)
- [E2E 测试报告](#e2e-测试报告)
- [性能测试报告（Locust）](#性能测试报告locust)
- [性能测试报告（k6）](#性能测试报告k6)
- [基线对比报告](#基线对比报告)
- [元测试报告](#元测试报告)
- [容器资源报告](#容器资源报告)
- [报告分享 / 归档](#报告分享--归档)
- [常见问题](#常见问题)

## 报告类型总览

| 报告 | 来源 | 输出 | 查看方式 |
| --- | --- | --- | --- |
| **E2E Allure 报告** | `pytest --alluredir=...` | `reports/allure-results/*.json` + 截图 | `allure serve` 或 `allure generate` 出 HTML |
| **E2E 失败截图** | 自动（hook） | `reports/screenshots/*.png` | 文件浏览器直接打开 |
| **E2E pytest 终端报告** | `pytest -v` | stdout | 终端看 |
| **Locust HTML 报告** | Locust 自带 | `perf/reports/locust/report_<ver>.html` | 浏览器双击 |
| **Locust 表格汇总** | 自研 `summary_<ver>.txt` | `perf/reports/locust/summary_<ver>.txt` | 文本查看器 |
| **Locust 原始 stats** | Locust | `perf/reports/locust/run_<ver>_stats.csv` | Excel / pandas |
| **Locust JSON 快照** | 自研 | `perf/reports/locust/current_<ver>.json` | `jq` / 文本 |
| **k6 报告** | k6 | `perf/reports/k6/*.json` | k6 Cloud / Grafana / 文本 |
| **基线对比报告** | `compare_baseline.py` | stdout + exit code | 终端看 |
| **元测试报告** | `pytest perf/tests/ -v` | stdout | 终端看 |
| **容器 metrics** | `collect_docker_stats.py` | `perf/reports/locust/docker_stats.csv` | Excel / pandas |

---

## E2E 测试报告

### 1) Allure HTML 报告（推荐）

**生成**：

```bash
cd e2e

# 方式 1：跑测试时直接生成 allure-results（默认行为）
python run.py -m smoke             # 自动写到 reports/allure-results/

# 方式 2：跑完生成 HTML（推荐用于分享）
python run.py --allure             # 自动 allure generate

# 方式 3：手动两步
python -m pytest --alluredir=reports/allure-results -v
allure generate reports/allure-results -o reports/allure-report --clean
```

**查看**（两种方式二选一）：

```bash
# 方式 A：本地动态服务（带历史趋势 + 重试 + 过滤）
allure serve reports/allure-results
# 浏览器自动打开 http://localhost:<随机端口>

# 方式 B：生成静态 HTML（用于分享 / 归档）
allure generate reports/allure-results -o reports/allure-report --clean
# 用浏览器打开 reports/allure-report/index.html
```

> ⚠️ 端口冲突：`allure serve` 占用随机端口；若想固定端口：
> ```bash
> allure serve reports/allure-results --port 9999
> ```

**Allure 报告能看什么**：

| 视图 | 内容 |
| --- | --- |
| **Overview** | 总览：pass/fail/skip 数饼图、duration 趋势、severity 分布 |
| **Suites** | 按测试文件 / 类目树状展开 |
| **Graphs** | duration / status / 重试率趋势图 |
| **Timeline** | 并发执行时间线 |
| **Categories** | 失败分类（自动按 `categories.json` 归类：Superset 内部错 / Mapbox 限流 / 服务不可用 / 其他 / Broken）|
| **Packages** | 按代码包路径聚合 |
| **Behaviors** | 按 BDD Feature / Story 聚合（与 `spec/*.feature` 对应）|

**点击单条用例看什么**：

- 步骤（来自 `with when/then/given` 上下文管理器）
- 失败时自动附加的 **截图 PNG** + **HTML 快照**
- env：browser、headless、Superset 实例、env

### 2) 失败截图（无需 Allure）

```bash
# Windows
explorer e2e\reports\screenshots

# macOS
open e2e/reports/screenshots

# Linux
xdg-open e2e/reports/screenshots

# 或直接 ls
ls -lt e2e/reports/screenshots/*.png | head -20
```

文件命名规则：

```
<test_name>__<instance>__<timestamp>.png
例：test_login_admin__6.0__1781961422008.png
```

### 3) pytest 终端报告

```bash
# 详细模式
python -m pytest -v tests/auth/test_auth.py

# 显示每个用例打印
python -m pytest -s tests/sqllab/

# 失败时显示完整 traceback
python -m pytest --tb=long tests/dashboards/

# 简短 traceback
python -m pytest --tb=short tests/charts/
```

---

## 性能测试报告（Locust）

### 1) 跑完自动产出

```bash
bash perf/tools/run_locust.sh
```

输出到 `perf/reports/locust/`：

| 文件 | 用途 | 怎么看 |
| --- | --- | --- |
| `report_<ver>.html` | Locust 自带交互报告（请求分布 / 时间线） | 浏览器双击 |
| `summary_<ver>.txt` | 自研表格汇总（按端点 p50/p95/p99/Apdex） | 文本查看器 / `cat` |
| `current_<ver>.json` | 自研 JSON 快照（与 baseline 同 schema） | `jq` / Python |
| `run_<ver>_stats.csv` | Locust 原始 stats（per endpoint） | Excel / pandas |
| `run_<ver>_stats_history.csv` | 时间序列（每 10s 一行） | Excel 画趋势图 |
| `run_<ver>_failures.csv` | 失败请求 | `cat` / Excel |
| `run_<ver>_exceptions.csv` | 异常堆栈 | 文本 |
| `docker_stats.csv` | 容器 CPU/内存（如果开了） | pandas |

### 2) 查看报告（4 种姿势）

#### 姿势 A：浏览器看 Locust HTML

```bash
# Windows
start perf/reports/locust/report_6.0.html

# macOS
open perf/reports/locust/report_6.0.html

# Linux
xdg-open perf/reports/locust/report_6.0.html
```

#### 姿势 B：看表格汇总（最直观）

```bash
cat perf/reports/locust/summary_6.0.txt
```

输出示例：

```
Endpoint                                       count   err%     p50     p95     p99  apdex  stab
------------------------------------------------------------------------------
GET /api/v1/dashboard/  (viewer)                 135   0.0%  315.9ms 809.5ms 1265.0ms 0.889  4.0
POST /api/v1/chart/data  (viewer)                100   0.0%   87.9ms 239.6ms  437.2ms 0.995 4.97
...
```

#### 姿势 C：jq 看 JSON 快照

```bash
# 安装 jq（Windows: choco install jq / scoop install jq）
# macOS: brew install jq / Linux: apt-get install jq

# 看指定端点
jq '.endpoints["GET /api/v1/dashboard/  (viewer)"]' perf/reports/locust/current_6.0.json

# 所有端点 p95 排序
jq -r '.endpoints | to_entries | sort_by(.value.p95_ms)[] | "\(.value.p95_ms|tostring| (.+ "ms" | " "*(10-length)))|\(.key)"' perf/reports/locust/current_6.0.json

# 总览
jq 'keys' perf/reports/locust/current_6.0.json
```

#### 姿势 D：pandas / Excel 分析 CSV

```bash
# 看 stats 表头
head -1 perf/reports/locust/run_6.0_stats.csv
# Type,Name,Request Count,Failure Count,Median Response Time,...

# 用 pandas 分析
python -c "
import pandas as pd
df = pd.read_csv('perf/reports/locust/run_6.0_stats.csv')
print(df[['Name', 'Request Count', 'Failure Count', '95%']].sort_values('95%'))
"

# 时间序列
python -c "
import pandas as pd
df = pd.read_csv('perf/reports/locust/run_6.0_stats_history.csv')
print(df.tail())
"
```

### 3) Locust Web UI（实时）

跑测试时**开 Web UI**，边跑边看：

```bash
bash perf/tools/run_locust.sh --web
# 浏览器打开 http://localhost:8089
```

可看：
- New test：参数配置
- Charts：实时 RPS / 响应时间 / 失败数
- Failures：失败列表
- Download data：跑完下载 CSV
- Logs：实时日志

---

## 性能测试报告（k6）

### 1) 跑完产出

```bash
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
```

输出到 `perf/reports/k6/<script>_<vu>vu_<ts>.json`。

### 2) 查看（3 种姿势）

#### 姿势 A：k6 终端汇总（默认）

跑完 k6 自动在终端打印类似：

```
     ✓ dashboard_list status 200
     █ setup        █ teardown

     checks.................: 100.00% ✓ 9200      ✗ 0
     data_received.........: 124 MB  4.1 MB/s
     data_sent.............: 8.6 MB  287 kB/s
     http_req_blocked......: avg=1.2ms    p(95)=4.5ms
     http_req_connecting...: avg=420µs   p(95)=1.2ms
     http_req_duration.....: avg=45.2ms   p(95)=210ms   p(99)=380ms
     http_req_failed.......: 0.00%  ✓ 0         ✗ 9200
     http_req_receiving....: avg=120µs   p(95)=450µs
     http_req_sending......: avg=80µs    p(95)=200µs
     http_req_tls_handshaking: avg=0s      p(95)=0s
     http_req_waiting......: avg=44.9ms   p(95)=209ms
     http_reqs.............: 9200    306.6/s
     iteration_duration....: avg=985ms   p(95)=2.1s
     iterations............: 9200    306.6/s
     vus...................: 300     min=0       max=300
     vus_max...............: 300     min=300     max=300
```

#### 姿势 B：导入 k6 Cloud

```bash
# 注册 https://app.k6.io/ 后
k6 login cloud
k6 run --out cloud perf/k6/scripts/dashboard_list.js
```

#### 姿势 C：转 Grafana / Prometheus

k6 JSON 含完整时序，可写入 InfluxDB / Prometheus / TimescaleDB：

```bash
k6 run --out influxdb=http://localhost:8086/k6 perf/k6/scripts/dashboard_list.js
```

或本地起 Grafana：

```bash
docker run -d -p 3000:3000 grafana/grafana
# 配 InfluxDB 数据源 + k6 dashboard
```

---

## 基线对比报告

### 1) 命令行对比

```bash
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail
```

输出：

```
Comparing vs baseline v6.0 (cold-start 10 VU 2 min)
================================================================

WARN  GET /api/v1/chart/  (viewer)  p95=1890ms  (baseline=1780ms, +6.2%, threshold +20%)  → WARN
PASS  POST /api/v1/chart/data  (viewer)  p95=240ms  (baseline=220ms, +9.1%, threshold +15%)
PASS  GET /api/v1/dashboard/  (viewer)  p95=810ms  (baseline=832ms, -2.6%, threshold +20%)
...

Summary: 24 PASS / 1 WARN / 0 FAIL
```

退出码：
- `0` — 全部 PASS / WARN（strict 模式下 WARN 也可 fail）
- `1` — 有 FAIL

### 2) 在 CI 中用

```yaml
# GitHub Actions / Jenkins
- name: Compare baseline
  run: |
    python perf/tools/compare_baseline.py \
      --version 6.0 \
      --current perf/reports/locust/current_6.0.json \
      --strict --exit-on-fail
```

---

## 元测试报告

`pytest perf/tests/` 跑的是**测试框架自身**的测试（配置 / schema / 阈值）。

```bash
# 详细
python -m pytest perf/tests/ -v

# 短输出
python -m pytest perf/tests/ --tb=short

# 单独跑某个
python -m pytest perf/tests/test_config.py -v
python -m pytest perf/tests/test_thresholds.py::test_critical_error_rate_fails -v
```

输出示例：

```
============================= test session starts ==============================
platform win32 -- Python 3.12.1, pytest-8.3.3
configfile: pyproject.toml
plugins: allure-pytest-2.13.5, ...
collected 18 items

perf/tests/test_baseline_schema.py::test_baseline_exists[4.1] PASSED     [  5%]
...
perf/tests/test_thresholds.py::test_critical_error_rate_fails PASSED     [100%]

============================= 18 passed in 0.52s ==============================
```

---

## 容器资源报告

```bash
# 跑压测时后台启动
python perf/tools/collect_docker_stats.py \
    --containers superset-6.0-web,superset-6.0-postgres \
    --out perf/reports/locust/docker_stats.csv \
    --interval 2

# 跑完分析
python -c "
import pandas as pd
df = pd.read_csv('perf/reports/locust/docker_stats.csv')
print(df.groupby('container')[['cpu_pct', 'mem_pct']].describe())
"
```

---

## 报告分享 / 归档

### 本地分享

```bash
# Allure 静态 HTML
allure generate reports/allure-results -o reports/allure-report --clean
# 整个 reports/allure-report/ 目录 zip 发给同事

# Locust HTML
# 直接发 perf/reports/locust/report_6.0.html（单文件）
```

### CI 产物上传

`.github/workflows/perf.yml` 已配：

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: allure-results
    path: |
      e2e/reports/allure-results
      e2e/perf/reports/locust
```

下载后用 `allure serve <下载目录/allure-results>` 查看。

### 长期归档

```bash
# 加时间戳归档
ts=$(date +%Y%m%d_%H%M%S)
tar czf reports_${ts}.tar.gz reports/ perf/reports/
# 上传对象存储 / 内部共享盘
```

---

## 常见问题

| 问题 | 解决 |
| --- | --- |
| `allure: command not found` | `npm i -g allure-commandline` 或 `scoop install allure`（Windows）|
| `allure serve` 启动后空白 | 浏览器禁用缓存或 `Ctrl+Shift+R` 硬刷新 |
| 看不到截图 | 检查 `reports/screenshots/` 是否有 PNG；Allure 报告 → 单击用例 → Attachments |
| Locust HTML 打开显示 0 请求 | 压测时间太短；最少 30s |
| `k6: not found` | `apt-get install k6` / `brew install k6` / `choco install k6` |
| 报告路径不对 | 必须在 `e2e/` 目录跑命令 |
| `compare_baseline.py` 报 baseline 缺失 | `python perf/tools/save_baseline.py --version 6.0 --current ... --note "first baseline"` |
| 想看历史趋势 | Allure `allure serve` 自动读取 `allure-results/history/`，多次跑会累积 |
| 元测试挂了 | 改完配置跑一次 `pytest perf/tests/ -v`，必须 18/18 通过 |

---

## 一键汇总命令

```bash
# 一键打印最近一次的所有报告
cd e2e
echo "=== E2E Allure ===" && ls reports/allure-results/ | head -5
echo "=== E2E 失败截图 ===" && ls reports/screenshots/ | wc -l
echo "=== Locust 报告 ===" && ls perf/reports/locust/
echo "=== k6 报告 ===" && ls perf/reports/k6/ 2>/dev/null || echo "  (k6 报告目录为空)"
echo "=== 基线 ===" && ls perf/baselines/
echo "=== 元测试 ===" && python -m pytest perf/tests/ -q 2>&1 | tail -3
```
