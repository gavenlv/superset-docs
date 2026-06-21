# Superset 性能测试套件

> 状态：**v1.0 已实现**（2026-06-21）  
> 适用版本：Superset 4.1 / 6.0  
> **重点**：`dashboard / charts / chart_data` 三类查询（承担 70%+ RPS）

详细规划见 [PLAN.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/PLAN.md)，
变更历史见 [CHANGELOG.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/CHANGELOG.md)，
Jenkins 部署见 [docs/JENKINS.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/docs/JENKINS.md)，
**多环境 / 多用户** 见 [docs/MULTI_ENV_USER.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/docs/MULTI_ENV_USER.md)。

## 实施状态（2026-06-21）

| 阶段 | 状态 |
| --- | :---: |
| P5-1 基建（目录、配置、Locust 基类） | ✅ |
| P5-2 重点 Locust（Viewer/Analyst 读路径） | ✅ |
| P5-3 重点 k6（dashboard_list/chart_data/dashboard_render） | ✅ |
| P5-4 PR 门禁（GitHub Actions） | 🚧 草案 |
| P5-5 Locust 全角色（AdminOps/Embed + docker stats） | ✅ |
| P5-6 k6 全脚本（9 个） | ✅ |
| P5-7 报告 + 文档 | 🚧 进行中 |

**元测试**：`pytest perf/tests/ -v` → **13/13 passed**  
**基线（6.0）**：`perf/baselines/v6_0.json`（10 VU / 2 min cold-start，16 端点，0 错误）  
**基线（4.1）**：`perf/baselines/v4_1.json` 暂为占位（待 P5-1 跑出正式基线）

## 跨版本差异（必看）

| 差异点 | 4.1 | 6.0 |
| --- | --- | --- |
| `/api/v1/dashboard/{id}/charts/` | 接受尾斜杠 | **去掉尾斜杠**（`/charts`）否则 404 |
| `POST /api/v1/chart/data` payload | `{"slice_id": N}` | **`{"datasource": {"id":N,"type":"table"}, "queries":[...]}`** |
| 重点端点基线（p95）| 占位中 | `v6_0.json` 实测 |

k6 脚本通过 `SUPERSET_VERSION=4.1|6.0`（默认 6.0）自动切换 payload；Locust 脚本里 Viewer/Analyst/Embed 已硬编码 6.0 兼容写法，4.1 跑需手动调整 `_CHART_DATA_PAYLOAD`。

## 目录

```
e2e/perf/
├── PLAN.md              详细规划
├── README.md            本文件
├── CHANGELOG.md         变更日志
├── requirements.txt     Python 依赖
│
├── common/              跨框架通用
│   ├── config_loader.py 加载 e2e/config/config.yaml 的 perf 段
│   ├── auth.py          复用 utils.api 的登录（10min token 缓存）
│   ├── metrics.py       Apdex / Stability / p99 drift
│   ├── thresholds.py    基线加载 + 重点/普通分级对比
│   ├── docker_stats.py  压测期间后台采集容器 CPU/内存
│   └── report.py        报告输出
│
├── locust/              Locust 主场景
│   ├── locustfile.py    入口（4 角色）
│   └── tasks/
│       ├── base.py      SupersetUser 基类 + BaseBehavior
│       ├── admin_ops.py AdminOps 角色（写路径）
│       ├── analyst.py   Analyst 角色
│       ├── viewer.py    Viewer 角色（**重点**）
│       ├── embed.py     Embed 角色
│       └── login_storm.py 独立登录风暴
│
├── k6/                  k6 高并发专项（重点查询 CI 门禁）
│   └── scripts/
│       ├── lib.js               每 VU token 缓存
│       ├── dashboard_list.js    300 VU / 3 min（PR 必跑）
│       ├── dashboard_detail.js  200 VU / 3 min
│       ├── dashboard_render.js  150 VU / 3 min
│       ├── chart_list.js        200 VU / 2 min（PR 必跑）
│       ├── chart_data.js        100 VU / 5 min（4.1/6.0 兼容）
│       ├── login_storm.js       200 VU / 30 s
│       ├── smoke.js             30 VU / 1 min
│       ├── endurance.js         50 VU / 30 min
│       └── explore_stress.js    100 VU / 2 min
│
├── baselines/           基线 JSON（git 跟踪）
│   ├── v4_1.json
│   └── v6_0.json
│
├── reports/             压测报告（gitignore）
│
├── tools/               辅助脚本
│   ├── wait_healthy.py         等待 Superset 就绪
│   ├── run_locust.sh           启动 Locust（默认 200 VU / 10 min）
│   ├── run_k6.sh               启动 k6（按脚本名自动选 VU/duration）
│   ├── compare_baseline.py     对比当前结果 vs 基线
│   ├── save_baseline.py        把当前结果存为基线（角色变体聚合）
│   └── collect_docker_stats.py 压测期间采集容器 CPU/内存
│
└── tests/               元测试（pytest 显式触发）
    ├── test_config.py
    ├── test_baseline_schema.py
    └── test_thresholds.py
```

## 安装

```bash
pip install -r perf/requirements.txt
# k6
sudo apt-get install k6   # Linux
brew install k6           # macOS
# 或 docker run grafana/k6
```

## 快速开始

### 1. 启动 Superset

```bash
cd e2e
python run.py --mode cold   # 冷启动示例数据
```

### 2. 跑 Locust 重点压测（200 VU / 10 min）

```bash
cd e2e
bash perf/tools/run_locust.sh
# 压 4.1: PERF_TARGET_VERSION=4.1 bash perf/tools/run_locust.sh
# 启动 Web UI: bash perf/tools/run_locust.sh --web
# → http://localhost:8089
```

输出到 `perf/reports/locust/`：
- `current_6.0.json` — 当前快照（与 baselines/v6_0.json 同 schema）
- `summary_6.0.txt` — 表格化汇总
- `run_6.0_stats.csv` / `report_6.0.html` — Locust 自带

### 3. 跑 k6 重点脚本

```bash
cd e2e

# PR 必跑
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js   # 300 VU
bash perf/tools/run_k6.sh perf/k6/scripts/chart_list.js       # 200 VU

# release 必跑
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js       # 100 VU / 5 min

# 跨版本：4.1 / 6.0 自动切换 payload
SUPERSET_VERSION=4.1 bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js
```

输出到 `perf/reports/k6/*.json`。

### 4. 对比基线（PR 门禁）

```bash
# 全部端点对比
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json

# 重点查询严格模式（重点超阈值即 fail）
python perf/tools/compare_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --strict --exit-on-fail
```

### 5. 采集容器资源（可选）

```bash
# 后台跑
python perf/tools/collect_docker_stats.py \
    --containers superset-6.0-web,superset-6.0-postgres,superset-6.0-redis \
    --out perf/reports/locust/docker_stats.csv \
    --interval 2
```

### 6. 把当前结果存为基线

```bash
python perf/tools/save_baseline.py \
    --version 6.0 \
    --current perf/reports/locust/current_6.0.json \
    --note "200 VU / 10 min cold-start"
# 写入 perf/baselines/v6_0.json（git 跟踪，自动聚合角色变体）
```

## 重点查询（CI 门禁）

| 端点 | Locust 频率 | k6 脚本 | PR 必跑 |
| --- | ---: | --- | :---: |
| `GET /api/v1/dashboard/` | 60/min | `dashboard_list.js` (300 VU) | ✅ |
| `GET /api/v1/dashboard/{id}` | 40/min | `dashboard_detail.js` (200 VU) | – |
| `GET /api/v1/dashboard/{id}/charts` | 30/min | `dashboard_detail.js` | – |
| `GET /superset/dashboard/{id}/` | 25/min | `dashboard_render.js` (150 VU) | – |
| `GET /api/v1/chart/` | 50/min | `chart_list.js` (200 VU) | ✅ |
| `GET /api/v1/chart/{id}` | 20/min | `dashboard_detail.js` | – |
| `POST /api/v1/chart/data` ⭐⭐ | 45/min | `chart_data.js` (100 VU) | – |

## 阈值

| 类别 | fail 阈值（p95 较基线） | error rate fail |
| --- | ---: | ---: |
| ⭐⭐ chart/data | **+15%** | **>0.5%** |
| ⭐ 重点查询 | **+20%** | >0.5% |
| 普通查询 | +50% | >1% |

可在 `e2e/config/config.yaml` 的 `perf.thresholds` 段调整。

## 元测试

```bash
cd e2e
pytest perf/tests/ -v
```

验证：
- 配置加载
- 基线 schema
- 阈值分级判定逻辑
- 重点端点白名单覆盖

## CI 集成

参考 [PLAN.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/PLAN.md#9-cicd-集成) §9 节。
GitHub Actions 阶段（`.github/workflows/perf.yml` 草案）：
- PR push → `dashboard_list.js` + `chart_list.js`
- nightly → Locust 10 min + 全部重点 k6 脚本
- release → Locust 30 min + chart_data 5 min
