# Superset 性能测试计划

> 状态：**v1.0 已实现**（2026-06-21）  
> 适用版本：Superset 4.1 / 6.0  
> 作者：性能测试 P5 阶段规划  
> **核心重点**：`/api/v1/dashboard/*`、`/api/v1/chart/*`、`POST /api/v1/chart/data` 三类查询（承担 70%+ RPS）；200 VU / 10 min / 重点查询 5 套 k6 脚本 / 重点查询 PR 必跑门禁
>
> **实现进度**：P5-1～P5-5 已落地，**P5-6（k6 全脚本）已 100%**，P5-7（CI/CD 文档）部分落地。  
> 详细落地状态见末尾 [§10.1 实施进度](#101-实施进度) 与 [CHANGELOG.md](file:///d:/workspace/superset-space/superset-docs/e2e/perf/CHANGELOG.md)。

---

## 1. 选型结论

**主选：Locust**（API 行为模拟 / 集成测试 / 长时间稳定性）  
**副选：k6**（高并发压测 / **重点查询 CI 门禁** / 微基准）  
**辅助：Apache Superset 自带 `load_test_data`**（示例数据规模膨胀）

### 1.1 对比矩阵

| 维度 | Locust | k6 | wrk | JMeter | Artillery |
| --- | :---: | :---: | :---: | :---: | :---: |
| 语言 | Python | JavaScript | Lua/C | Java/Groovy | JS/YAML |
| 与现有栈契合（pytest+httpx） | ✅ | ❌ | ❌ | ❌ | ⚠️ |
| 真实用户行为 | ✅ Task | ✅ Scenario | ❌ | ✅ | ✅ |
| Web UI | ✅ 内置 | ⚠️ Cloud | ❌ | ✅ 桌面 | ❌ |
| 分布式 | ✅ Master/Worker | ✅ k6-operator | ❌ | ✅ | ⚠️ cluster |
| 吞吐上限（RPS，本机单进程） | ~3k | ~30k | ~100k+ | ~5k | ~5k |
| CI 原生门禁（阈值即结果） | ⚠️ 自定义 | ✅ | ❌ | ⚠️ JTL | ⚠️ |
| 多步业务流 | ✅ 原生 | ✅ | ❌ | ✅ | ✅ |
| 复用现有 `utils/api.py` | ✅ | ❌ | ❌ | ❌ | ❌ |
| 学习曲线 | 低 | 中 | 低 | 高 | 低 |

### 1.2 选型理由

1. **技术栈一致**：Locust 是 Python 项目，与现有 pytest + httpx + 4.1/6.0 容器编排完全契合；可直接 `import utils.api` 复用 `login_client` / `csrf_token` / `unwrap`。
2. **场景建模强**：E2E 测试已经覆盖了 144 个场景，性能测试可以**复用同一套登录/调用样板**，把"功能性请求"包装成"用户行为"。
3. **门槛低**：QA 工程师熟悉 Python，Locust 脚本即 Python 类，调试方便。
4. **可观察**：内置 Web UI 实时看 RPS / p95 / 错误率；非压测时段也能复现。
5. **可扩展**：单进程瓶颈时切到 master/worker 分布式，零业务代码变更。
6. **k6 补短板**：当需要"千级并发冲登录接口"或"CI 跑 5 分钟 smoke 压测"时，k6 阈值模式更直接。

---

## 2. 目标与范围

### 2.1 核心目标

| 目标 | 量化指标 |
| --- | --- |
| **基线建立** | 记录 4.1 / 6.0 在示例数据集（~25 个 dataset）下各端点 p50 / p95 / p99 |
| **容量规划** | 给出"X 并发下 Superset 仍稳定"的并发上限 |
| **回归拦截** | 关键接口 p95 增长 >20% → CI 失败 |
| **瓶颈定位** | 在压测中采集 DB / Redis / Worker CPU，能定位到具体组件 |

### 2.2 范围

| 层级 | 包含 | 不包含（建议下一期） |
| --- | --- | --- |
| API 端点 | `/health`、`/api/v1/{database,dataset,chart,dashboard,saved_query,rowlevelsecurity,tag,annotation_layer,css_template,explore,me}/`、`/api/v1/security/{login,logout,csrf_token}`、`/api/v1/chart/data`、`/api/v1/sqllab/` | WebSocket、嵌入 SDK |
| 浏览器渲染 | 仪表盘首屏 / Explore 渲染 / SQL Lab 编辑器加载（Playwright tracing） | 完整交互链路 |
| 后端资源 | Postgres / Redis / Celery worker 容器 CPU、内存、磁盘 IO | 宿主机/网络 |
| 数据规模 | 默认示例数据集（cold 启动后），`Superset` 内置 25 dataset | 自造 10x / 100x 规模数据（通过 `load_examples` 多次复制） |

### 2.3 与现有套件的关系

- **不替代** E2E：E2E 跑"功能对不对"，性能测试跑"够不够快/稳"。
- **不替代** 单元测试：E2E 已经覆盖了核心 API 行为。
- **共享** `config/config.yaml` 的 instances、admin 凭据；新增 `perf:` 段控制 Locust/k6 专属参数。
- **共享** `utils/api.py`：登录、CSRF、分页、字段清理全复用。
- **共享** `docker compose`：性能测试也跑在 cold/reuse 容器上。

---

## 3. 架构

### 3.1 模块关系图

```
┌────────────────────────────────────────────────────────────────────┐
│                       性能测试 perf/                                │
│                                                                    │
│  locust/                              k6/                          │
│   ├── locustfile.py (主场景集)         ├── scripts/                │
│   ├── tasks/                          │   ├── smoke.js             │
│   │   ├── base.py   (UserBehavior)    │   ├── login_storm.js       │
│   │   ├── admin.py  (CRUD 高频)       │   ├── chart_data.js        │
│   │   ├── viewer.py (只读浏览)        │   └── dashboard_render.js  │
│   │   └── embed.py  (无认证)          └── thresholds.json         │
│   ├── shapes/                                                    │
│   │   └── dashboard_summary.json                                 │
│   └── reports/                                                   │
│        ├── stats.csv                                              │
│        └── failures.html                                          │
│                                                                    │
│  common/                                                           │
│   ├── auth.py        (复用 utils.api)                              │
│   ├── datasets.py    (seed/cleanup 性能数据)                       │
│   ├── metrics.py     (p50/p95/p99 + 自定义指标)                   │
│   └── thresholds.py  (基准值 / 阈值管理)                           │
│                                                                    │
│  reports/ (与 e2e/reports 平行)                                    │
└────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
       ┌────────────────────────────────────────┐
       │   现有 e2e/utils/（login、csrf、page_actions）│
       │   现有 e2e/config/config.yaml          │
       │   现有 superset-4.1 / superset-6.0      │
       └────────────────────────────────────────┘
```

### 3.2 关键设计

- **Locust 主入口**：`perf/locust/locustfile.py`，与现有 pytest 入口平级但**完全独立**（不污染 pytest discovery）。
- **场景文件**：`perf/locust/tasks/` 下的 Python 类，每个类对应一个用户角色（admin/analyst/viewer/embed）。
- **k6 脚本**：`perf/k6/scripts/*.js`，仅在 CI 阈值检查或大流量专项时调用。
- **阈值基线**：`perf/common/thresholds.py` 集中保存版本 × 接口 × 指标（p95）映射，**修改需 PR 评审**。
- **数据共享**：性能测试运行前用 `perf/common/datasets.py` 决定是否 `load_test_data` 把示例数据复制 N 倍。

---

## 4. 测试场景（30+ 个）

### 4.1 Locust 用户行为（5 个角色）

> **总体原则**：**读路径占绝对主导**（Viewer + Analyst + Embed ≈ 95%），写路径（AdminOps）仅作背景噪声。  
> **dashboard / charts / chart_data 三类查询承担 70%+ 的 RPS**，是性能基线与回归拦截的重点。

| 角色 | 任务集合 | **新权重** | 模拟对象 | 备注 |
| --- | --- | ---: | --- | --- |
| **AdminOps** | 创建/编辑/删除 dataset / chart / dashboard / RLS / 标签 | **1** | 后台管理员日常 | 写路径，权重保持低位 |
| **Analyst** | 编辑 Explore、保存图表、加到仪表盘、SQL Lab 跑查询 | **10** | 数据分析师 | 包含大量 chart/data 写入 |
| **Viewer** | 打开仪表盘、切过滤器、刷新、查看图表数据 | **30** | 业务用户读路径 | **重点**压 dashboard / chart 读路径 |
| **Embed** | 打开 `/superset/embed/{uuid}/`，加过滤器，截图 | **8** | 嵌入式访问 | 高频只读 |
| **LoginStorm** | 仅做 login / CSRF / refresh | 0（独立脚本） | 登录风暴 | 独立触发 |

**总权重 49**；读路径 48 / 写路径 1 ≈ **98 : 2**，与真实线上流量分布一致。

### 4.2 Locust 任务清单

> **加粗项 = 重点查询**（dashboard / charts / chart_data），频率显著提升，回归门禁严格（fail_pct 15%）。  
> 非加粗项 = 后台噪声，回归门禁宽松（fail_pct 50%）。

| ID | 任务 | HTTP | 频率（per user / min） | 角色 | 重点 |
| --- | --- | --- | ---: | --- | --- |
| **T01** | **`/api/v1/dashboard/?q=...`** | GET | **60**（列表分页/搜索） | Viewer / Analyst | ⭐ |
| **T02** | **`/api/v1/dashboard/{id}`** | GET | **40**（详情） | Viewer | ⭐ |
| **T03** | **`/api/v1/dashboard/{id}/charts/`** | GET | **30**（拉图表列表） | Viewer | ⭐ |
| **T04** | **`/superset/dashboard/{id}/`** | GET（HTML） | **25**（页面渲染） | Viewer / Embed | ⭐ |
| **T05** | **`/api/v1/chart/?q=...`** | GET | **50**（图表列表） | Analyst / Viewer | ⭐ |
| **T06** | **`/api/v1/chart/{id}/data`** | POST | **45**（**执行查询，最重**） | Viewer / Analyst | ⭐⭐ |
| **T07** | **`/api/v1/chart/{id}`** | GET | **20**（图表详情） | Viewer / Analyst | ⭐ |
| **T08** | **`/api/v1/explore/?slice_id=N`** | GET | **20**（Explore 加载） | Analyst | ⭐ |
| **T09** | `/api/v1/dashboard/{id}/datasets/` | GET | 10 | Viewer |  |
| **T10** | `/api/v1/dataset/?q=...` | GET | 8 | Analyst |  |
| **T11** | `/api/v1/dataset/{id}` | GET | 5 | Analyst |  |
| **T12** | `/api/v1/database/1/schemas/` | GET | 3 | Analyst |  |
| **T13** | `/api/v1/database/1/function_names/` | GET | 1 | Analyst |  |
| **T14** | `/api/v1/sqllab/` | GET | 4 | Analyst |  |
| **T15** | `/api/v1/saved_query/?q=...` | GET | 2 | Analyst |  |
| **T16** | `/api/v1/chart/favorite_status/?q=...` | GET | 3 | Viewer |  |
| **T17** | `/api/v1/rowlevelsecurity/?q=...` | GET | 1 | AdminOps |  |
| **T18** | `/api/v1/tag/?q=...` | GET | 2 | Viewer |  |
| **T19** | `/api/v1/annotation_layer/?q=...` | GET | 1 | Analyst |  |
| **T20** | `/api/v1/css_template/?q=...` | GET | 1 | AdminOps |  |
| **T21** | `/api/v1/me/` | GET | 30 | All | 心率 |
| **T22** | `/health` | GET | 60 | All | 心率 |
| T23 | `/api/v1/security/login` | POST | 2 | LoginStorm | cold 启动 |
| T24 | `/superset/welcome/` | GET | 5 | Viewer |  |
| T25 | `/explore/?slice_id=N` | GET（HTML） | 10 | Analyst |  |
| T26 | `/api/v1/dashboard/{id}/copy/` | POST | 0.5 | AdminOps | 写 |
| T27 | `/api/v1/chart/{id}` (PUT/DELETE) | PUT/DELETE | 0.5 | AdminOps | 写 |
| T28 | `/api/v1/dataset/{id}` (PUT) | PUT | 0.3 | AdminOps | 写 |
| T29 | `/api/v1/saved_query/{id}` (CRUD) | POST/PUT/DELETE | 0.5 | Analyst | 写 |
| T30 | `/api/v1/rowlevelsecurity/{id}` (CRUD) | POST/PUT/DELETE | 0.3 | AdminOps | 写 |

**重点查询流量分布（按当前频率 × 角色权重估算 RPS）**：

| 端点 | 角色贡献 | 估算 RPS @ 200 VU | 占比 |
| --- | --- | ---: | ---: |
| `chart/{id}/data` | Viewer 30 + Analyst 10 | **≈ 30** | **38%** |
| `dashboard/?q=` | Viewer 30 + Analyst 10 | **≈ 18** | **23%** |
| `chart/?q=` | Analyst 10 + Viewer 30 | **≈ 12** | **15%** |
| `dashboard/{id}` | Viewer 30 | **≈ 9** | **11%** |
| `dashboard/{id}/charts/` | Viewer 30 | **≈ 7** | **9%** |
| `dashboard/{id}/`（HTML） | Viewer 30 + Embed 8 | **≈ 6** | **8%** |
| **小计** | | **≈ 82 / 200 VU** | **≈ 100%**（重点查询） |

### 4.3 k6 专项脚本（CI 阈值门禁 / 高并发专项）

| 脚本 | 场景 | 持续时间 | VU | 阈值 |
| --- | --- | ---: | ---: | --- |
| `smoke.js` | 30 VU 跑 1 分钟，覆盖 T01~T10 | 1 min | 30 | p95 < 800ms，error < 1% |
| `login_storm.js` | 200 VU 集中登录，验证 token 发放能力 | 30 s | 200 | p95 < 1500ms，error < 0.5% |
| **`dashboard_list.js`** | **持续 `GET /api/v1/dashboard/?q=...`** | 3 min | **300** | **p95 < 250ms，error < 0.5%** |
| **`dashboard_detail.js`** | **`GET /api/v1/dashboard/{id}` + `/charts/`** | 3 min | **200** | **p95 < 350ms，error < 0.5%** |
| **`dashboard_render.js`** | **GET 仪表盘 HTML 页面** | 3 min | **150** | **p95 < 3000ms，error < 0.5%** |
| **`chart_data.js`** | **`POST /api/v1/chart/data` 聚合查询** | 5 min | **100** | **p95 < 2000ms，error < 1%** |
| `chart_list.js` | `GET /api/v1/chart/?q=...` | 2 min | 200 | p95 < 300ms |
| `explore_stress.js` | `explore/?slice_id=*` | 2 min | 100 | p95 < 1500ms |
| `endurance.js` | 30 分钟长跑，检测内存泄漏 | 30 min | 50 | 平均 RPS 漂移 < 10% |

**重点 k6 脚本（dashboard / charts / chart_data）单独优先级提升**：  
- PR push 必跑 `dashboard_list.js` + `chart_list.js`（覆盖最重的两个列表查询）  
- nightly 跑全部 5 个 dashboard/chart 脚本  
- release 跑 `chart_data.js` 5min 极限

---

## 5. 指标与阈值

### 5.1 核心指标

| 指标 | 含义 | 计算 |
| --- | --- | --- |
| **RPS** | 每秒请求数 | Locust 自带 |
| **p50 / p95 / p99** | 响应时间分位 | Locust 自带 + k6 trend |
| **Error rate** | 失败请求占比 | `failures / total` |
| **Concurrent users** | 同时在线虚拟用户 | Locust 用户数 |
| **Apdex** | 用户满意度指数 | `(satisfied + tolerating/2) / total`（自定义） |
| **Stability score** | p99 是否 < 5× p50 | 自定义 |

### 5.2 阈值基线（草拟，cold 启动示例数据下，并发提高后）

> **重点查询（dashboard / charts / chart_data）** 单独一档，容量上限显著提高。  
> 下面"容量 VU"是 6.0 在 cold 启动 25 dataset / 11 dashboard 下的初始估值，正式基线在 P5-1 跑出后覆盖。

| 接口 | 4.1 p95 (ms) | 6.0 p95 (ms) | **容量 VU** | 类别 | 备注 |
| --- | ---: | ---: | ---: | --- | --- |
| **`GET /api/v1/dashboard/?q=`** | **150** | **200** | **300** | ⭐ 重点 | 11 个 dashboard，列表分页 |
| **`GET /api/v1/dashboard/{id}`** | **80** | **120** | **300** | ⭐ 重点 | 详情，缓存命中 |
| **`GET /api/v1/dashboard/{id}/charts`** | **100** | **150** | **250** | ⭐ 重点 | 拉图表列表（**6.0 无尾斜杠**） |
| **`GET /superset/dashboard/{id}/`** | **1500** | **2500** | **150** | ⭐ 重点 | HTML 渲染 + JS bundle |
| **`GET /api/v1/chart/?q=`** | **120** | **180** | **300** | ⭐ 重点 | 图表列表 |
| **`POST /api/v1/chart/data`** | **800** | **1200** | **100** | ⭐⭐ 最重 | 4.1 用 `slice_id`；**6.0 用 `datasource+queries`** |
| **`GET /api/v1/chart/{id}`** | **60** | **90** | **300** | ⭐ 重点 | 图表详情 |
| `/api/v1/dataset/?q=` | 100 | 150 | 80 | 普通 | 25 个 dataset |
| `/api/v1/dataset/{id}` | 60 | 90 | 80 | 普通 | 详情 |
| `/api/v1/security/login` | 200 | 250 | 200 | 普通 | JWT 签发 |
| `/api/v1/explore/?slice_id=` | 300 | 400 | 80 | 普通 | form_data 拼装 |
| `/api/v1/sqllab/` | 200 | 280 | 60 | 普通 | 多 tab 状态 |
| `/health` | 30 | 30 | 500 | 心率 | 静态响应 |

> **跨版本差异（必须注意）**：
> - **路径**：6.0 移除了 `/api/v1/dashboard/{id}/charts/` 的尾斜杠（4.1 接受，6.0 404）
> - **payload**：`POST /api/v1/chart/data` 在 6.0 改为 `datasource{id,type}+queries[]`（4.1 仍支持 `slice_id`）
> - **基线覆盖**：6.0 实测 16 端点（10 VU / 2 min cold-start），4.1 暂为占位（待 P5-1 跑出正式基线）

### 5.3 回归阈值（按类别分级）

> **重点查询**（dashboard / charts / chart_data）阈值更严格；**普通查询**保持原阈值。

| 类别 | 接口 | warn 阈值（p95 较基线） | **fail 阈值**（p95 较基线） | error rate fail |
| --- | --- | ---: | ---: | ---: |
| ⭐⭐ **最重** | `chart/{id}/data` | +10% | **+15%** | > 0.5% |
| ⭐ **重点** | dashboard / chart 列表与详情 / dashboard HTML | +15% | **+20%** | > 0.5% |
| 普通 | dataset / explore / sqllab / login | +20% | +50% | > 1.0% |

- 30 分钟长跑 p99 漂移 **> 30%** → 警告（疑似内存泄漏）
- 整体 Apdex **< 0.85** → 警告，**< 0.7** → 失败

---

## 6. 目录结构

```
e2e/
├── perf/                            # 新增：性能测试
│   ├── README.md                    # 性能测试使用说明
│   ├── PLAN.md                      # 本文档
│   ├── conftest_perf.py             # 与 e2e 共享 fixtures 的桥接
│   │
│   ├── locust/                      # Locust 主场景
│   │   ├── locustfile.py            # 入口
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # SupersetUser 基类（登录、CSRF、metrics 装饰器）
│   │   │   ├── admin_ops.py         # AdminOps 角色
│   │   │   ├── analyst.py           # Analyst 角色
│   │   │   ├── viewer.py            # Viewer 角色
│   │   │   ├── embed.py             # Embed 角色
│   │   │   └── login_storm.py       # 登录风暴（独立 locustfile）
│   │   ├── shapes/                  # 自定义数据 shape（可选）
│   │   │   └── load_test_data.py    # 调用 Superset load_test_data 复制示例
│   │   └── reports/                 # Locust 报告（gitignore）
│   │
│   ├── k6/                          # k6 副选
│   │   ├── scripts/
│   │   │   ├── smoke.js
│   │   │   ├── login_storm.js
│   │   │   ├── chart_data.js
│   │   │   ├── dashboard_render.js
│   │   │   ├── explore_stress.js
│   │   │   └── endurance.js
│   │   └── thresholds.json
│   │
│   ├── common/                      # 跨框架通用
│   │   ├── __init__.py
│   │   ├── auth.py                  # 包装 utils.api.login_client
│   │   ├── datasets.py              # 性能数据生成（load_test_data 包装）
│   │   ├── metrics.py               # 自定义指标（Apdex、Stability）
│   │   ├── thresholds.py            # 阈值加载、对比、判定
│   │   ├── docker_metrics.py        # 抓容器 CPU/内存（docker stats）
│   │   └── report.py                # Allure / HTML 报告输出
│   │
│   ├── baselines/                   # 基线（git 跟踪）
│   │   ├── v4.1.json
│   │   └── v6.0.json
│   │
│   ├── reports/                     # 性能报告（gitignore）
│   │   ├── locust/
│   │   └── k6/
│   │
│   ├── tools/                       # 辅助脚本
│   │   ├── run_locust.sh            # 本地 / CI 启动 Locust
│   │   ├── run_k6.sh                # 本地 / CI 启动 k6
│   │   ├── wait_healthy.py          # 等待 4.1 / 6.0 就绪
│   │   └── compare_baseline.py      # 对比当前结果 vs 基线
│   │
│   └── tests/                       # 性能测试的"元测试"（pytest）
│       ├── test_perf_smoke.py       # 在 perf 容器外跑 pytest，验证 k6/Locust 可执行
│       ├── test_thresholds.py       # 验证 thresholds.json 格式
│       └── test_baseline_schema.py  # 验证 baselines/*.json 字段完整
│
└── config/
    └── config.yaml                  # 新增 perf 段
```

### 6.1 `config/config.yaml` 新增段

```yaml
# ----------------------------------------------------------------------------
# 性能测试（重点压 dashboard / charts / chart_data）
# ----------------------------------------------------------------------------
perf:
  enabled: true
  framework: locust               # locust | k6 | both
  duration_sec: 600               # 单次压测时长（10 分钟，更稳的 p95/p99）
  spawn_rate: 20                  # 每秒拉起用户数（加快 ramp-up）
  users: 200                      # 峰值用户数（提高 4x，聚焦重点查询）

  # 角色权重（与 perf/locust/tasks/ 对应）
  role_weights:
    admin_ops: 1
    analyst: 10
    viewer: 30                    # 重点：dashboard / chart 读路径
    embed: 8

  # 数据集规模（可复制示例数据，模拟生产规模）
  dataset_multiplier: 5           # 5x 示例数据（默认 25 → 125 dataset）

  baseline_dir: perf/baselines

  # 阈值（按类别分级；重点查询更严格）
  thresholds:
    p95_warn_pct: 15
    p95_fail_pct: 20              # 重点查询统一 fail 阈值
    p95_fail_pct_critical: 15     # chart/data 最重查询更严
    p95_warn_pct_normal: 20
    p95_fail_pct_normal: 50
    error_rate_fail_pct: 0.5      # 重点查询 0.5%
    error_rate_fail_pct_normal: 1.0

  docker_metrics: true            # 抓容器 CPU/内存
  reports_dir: perf/reports
  k6_binary: k6                   # 或 docker run grafana/k6

  # 重点查询白名单（用于精准对比）
  # 注意：6.0 路径无尾斜杠（/charts 不带 /），payload 见上
  critical_endpoints:
    - GET:/api/v1/dashboard/
    - GET:/api/v1/dashboard/{id}
    - GET:/api/v1/dashboard/{id}/charts
    - GET:/superset/dashboard/{id}/
    - GET:/api/v1/chart/
    - GET:/api/v1/chart/{id}
    - POST:/api/v1/chart/data
```

---

## 7. 关键实现

### 7.1 Locust 入口示例

`perf/locust/locustfile.py`：

```python
"""Locust 主入口：组合所有角色，重点压 dashboard / charts / chart_data。

权重：AdminOps 1 : Analyst 10 : Viewer 30 : Embed 8 = 1 : 10 : 30 : 8
读路径占比 ≈ 98%，与真实线上流量分布一致。
"""
from locust import HttpUser, TaskSet, task, between, events, constant_pacing
from utils.api import login_client, csrf_token, auth_headers
from utils.config import load_config

from perf.locust.tasks.admin_ops import AdminOpsBehavior
from perf.locust.tasks.analyst import AnalystBehavior
from perf.locust.tasks.viewer import ViewerBehavior
from perf.locust.tasks.embed import EmbedBehavior


# 加载 perf 段配置（从 e2e/config/config.yaml 读）
_cfg = load_config().get("perf", {})
_role_weights = _cfg.get("role_weights", {
    "admin_ops": 1, "analyst": 10, "viewer": 30, "embed": 8,
})


class SupersetUser(HttpUser):
    """所有用户的基类：完成登录后交给具体角色行为。"""
    abstract = True
    wait_time = between(0.5, 2)  # 加快节奏，提高 RPS

    def on_start(self):
        # 复用现有 utils.api，避免重写登录
        client, token = login_client(self.host)
        self.client.headers.update({
            "Authorization": f"Bearer {token}",
        })
        self.client.cookies.update(client.cookies)


class AdminOpsUser(SupersetUser):
    weight = _role_weights["admin_ops"]      # 1
    tasks = [AdminOpsBehavior]


class AnalystUser(SupersetUser):
    weight = _role_weights["analyst"]        # 10
    tasks = [AnalystBehavior]


class ViewerUser(SupersetUser):
    """重点角色：dashboard / chart 读路径压测。"""
    weight = _role_weights["viewer"]         # 30
    wait_time = between(0.3, 1.5)            # Viewer 更密集的访问节奏
    tasks = [ViewerBehavior]


class EmbedUser(SupersetUser):
    weight = _role_weights["embed"]          # 8
    tasks = [EmbedBehavior]
```

### 7.2 阈值对比

`perf/common/thresholds.py`：

```python
"""加载基线，与当前结果对比，输出是否通过。"""
import json
from pathlib import Path
from typing import Any


def load_baseline(version: str) -> dict[str, Any]:
    path = Path(__file__).parent.parent / "baselines" / f"v{version.replace('.', '_')}.json"
    return json.loads(path.read_text())


def compare(version: str, current: dict[str, Any], warn_pct=20, fail_pct=50) -> dict:
    """返回 {"passed": bool, "violations": [...], "warnings": [...]}"""
    baseline = load_baseline(version)
    violations, warnings = [], []
    for endpoint, cur in current.items():
        base_p95 = baseline.get(endpoint, {}).get("p95_ms")
        if base_p95 is None:
            continue
        delta_pct = (cur["p95_ms"] - base_p95) / base_p95 * 100
        if delta_pct > fail_pct:
            violations.append({"endpoint": endpoint, "delta_pct": round(delta_pct, 1)})
        elif delta_pct > warn_pct:
            warnings.append({"endpoint": endpoint, "delta_pct": round(delta_pct, 1)})
    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
    }
```

### 7.3 容器指标采集

`perf/common/docker_metrics.py`：

```python
"""压测期间后台采集 Superset / Postgres / Redis 容器 CPU/内存。"""
import subprocess
import threading
import time
import csv
from pathlib import Path


def start_collector(containers: list[str], out_csv: Path, interval_sec: int = 2) -> threading.Thread:
    """启动后台线程，周期性 docker stats --no-stream。"""
    stop = threading.Event()

    def loop():
        with out_csv.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ts", "container", "cpu_pct", "mem_mb"])
            while not stop.is_set():
                for c in containers:
                    out = subprocess.run(
                        ["docker", "stats", c, "--no-stream", "--format",
                         "{{.CPUPerc}};{{.MemUsage}}"],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip()
                    if ";" in out:
                        cpu, mem = out.split(";", 1)
                        writer.writerow([
                            time.time(), c,
                            float(cpu.rstrip("%")),
                            mem.split("/")[0].strip(),
                        ])
                f.flush()
                time.sleep(interval_sec)

    t = threading.Thread(target=loop, daemon=True)
    t.start()

    def stop_():
        stop.set()

    t.stop = stop_
    return t
```

### 7.4 启动脚本

`perf/tools/run_locust.sh`：

```bash
#!/usr/bin/env bash
# 本地启动 Locust Web UI（http://localhost:8089）
# 重点压 dashboard / charts / chart_data（200 VU，10 分钟）
set -euo pipefail
cd "$(dirname "$0")/../.."

# 等待 4.1 / 6.0 就绪
python perf/tools/wait_healthy.py --versions 4.1,6.0

# 启动 Locust（重点查询压力测试）
locust -f perf/locust/locustfile.py \
  --host http://localhost:18088 \
  --users 200 --spawn-rate 20 --run-time 10m \
  --headless \
  --csv=perf/reports/locust/run \
  --html=perf/reports/locust/report.html
```

`perf/tools/run_k6.sh`：

```bash
#!/usr/bin/env bash
# k6 启动脚本：默认跑重点查询（dashboard_list / chart_data / dashboard_render）
set -euo pipefail
cd "$(dirname "$0")/../.."

SCRIPT="${1:-perf/k6/scripts/dashboard_list.js}"  # 默认压 dashboard 列表

case "$SCRIPT" in
    *smoke*)          OPTS="--duration 1m  --vus 30"  ;;
    *dashboard_list*) OPTS="--duration 3m  --vus 300" ;;  # 重点
    *dashboard_detail*) OPTS="--duration 3m --vus 200" ;; # 重点
    *dashboard_render*) OPTS="--duration 3m --vus 150" ;; # 重点
    *chart_list*)     OPTS="--duration 2m  --vus 200" ;;
    *chart_data*)     OPTS="--duration 5m  --vus 100" ;;  # 重点
    *endurance*)      OPTS="--duration 30m --vus 50"  ;;
    *)                OPTS="--duration 3m  --vus 100"  ;;
esac

k6 run $OPTS "$SCRIPT"
```

---

## 8. 报告输出

### 8.1 Locust 报告

- `perf/reports/locust/run_stats.csv` — Locust 自带
- `perf/reports/locust/report.html` — Locust 自带
- `perf/reports/locust/diff_vs_baseline.json` — 与基线 diff

### 8.2 k6 报告

- `perf/reports/k6/smoke.json` — 原始指标
- `perf/reports/k6/thresholds.json` — 阈值结果

### 8.3 综合报告（Allure Behavior）

性能测试结果作为 **Allure 的新 Stage** 附加到 e2e/reports/allure-results/：

- `perf-stage.json` — 每个 scenario 是一个 test
- 失败/超阈值的接口显示为 failed
- 提供 dashboard summary 链接

### 8.4 容器资源报告

`perf/reports/docker_stats.csv` —— 压测期间的容器 CPU/内存时间序列。

---

## 9. CI/CD 集成

### 9.1 GitHub Actions 阶段

```yaml
perf:
  runs-on: ubuntu-latest
  timeout-minutes: 90  # 重点查询压测需要更长窗口
  steps:
    - uses: actions/checkout@v4
    - name: Start Superset
      run: |
        cd superset-4.1 && docker compose up -d
        cd ../superset-6.0 && docker compose up -d
    - name: Wait for healthy
      run: python perf/tools/wait_healthy.py --versions 4.1,6.0
    - name: Install k6
      run: |
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
        echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update && sudo apt-get install k6
    - name: Install locust
      run: pip install locust==2.31
    # === 重点查询 k6 脚本（PR 必跑）===
    - name: k6 dashboard_list (300 VU)
      run: bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
    - name: k6 chart_list (200 VU)
      run: bash perf/tools/run_k6.sh perf/k6/scripts/chart_list.js
    - name: k6 chart_data (100 VU, 5min)
      run: bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js
    # === 重点 Locust 压测（nightly / release）===
    - name: Locust 10min 200VU
      run: bash perf/tools/run_locust.sh
    - name: Compare vs baseline (critical endpoints)
      run: python perf/tools/compare_baseline.py --strict --exit-on-fail
    - name: Upload perf reports
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: perf-reports
        path: perf/reports/
```

### 9.2 触发策略

| 触发 | 范围（重点查询优先） | 时长 |
| --- | --- | ---: |
| **PR 每次 push** | **k6 dashboard_list (300 VU) + chart_list (200 VU)** | 5 min |
| **nightly** | **Locust 200 VU 10 min 4.1 + 6.0** + 全部重点 k6 脚本 | 30 min |
| **release** | **Locust 200 VU 30 min 4.1 + 6.0** + k6 chart_data 5 min + endurance | 90 min |
| 手动 | 任意脚本 | 自定义 |

> **重点查询（dashboard / charts / chart_data）** 在 PR 阶段就必跑门禁，回归会**立刻**在 PR 反馈。

### 9.3 失败判定

```python
# perf/tools/compare_baseline.py
import sys
import json
import argparse
from perf.common.thresholds import compare


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, choices=["4.1", "6.0"])
    ap.add_argument("--current", required=True, help="path to current run JSON")
    ap.add_argument("--exit-on-fail", action="store_true")
    args = ap.parse_args()

    current = json.loads(open(args.current).read())
    result = compare(args.version, current)
    print(json.dumps(result, indent=2))
    if args.exit_on_fail and not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## 10. 实施阶段（P5，重点查询优先）

### 10.1 实施进度

| 阶段 | 状态 | 周期 | 目标（重点查询） | 实际交付 |
| --- | :---: | --- | --- | --- |
| **P5-1 基建** | ✅ 完成 | 0.5 周 | 目录结构、配置、Locust 基类 | `perf/` 骨架、config.yaml `perf:` 段、`common/{config_loader,auth,metrics,thresholds,docker_stats,report}.py` |
| **P5-2 重点 Locust** | ✅ 完成 | 1.5 周 | Viewer (权重 30) + Analyst (权重 10)、T01~T08 dashboard/chart | 4 角色（AdminOps/Analyst/Viewer/Embed）+ LoginStorm；28 个 task；6.0 实测 16 端点基线 |
| **P5-3 重点 k6** | ✅ 完成 | 1 周 | `dashboard_list` (300 VU) + `chart_data` (100 VU) + `dashboard_render` (150 VU) | 5 个重点 k6 脚本（dashboard_list/dashboard_detail/dashboard_render/chart_list/chart_data）；lib.js 每 VU 缓存 token |
| **P5-4 PR 门禁** | 🚧 文档完成 / 脚本待接 CI | 0.5 周 | PR 必跑 `dashboard_list` + `chart_list` | [`.github/workflows/perf.yml`](file:///d:/workspace/superset-space/superset-docs/.github/workflows/perf.yml) 草案；本地 `bash perf/tools/run_k6.sh` 可跑 |
| **P5-5 Locust 全角色** | ✅ 完成 | 1 周 | AdminOps / Embed / T09~T30（CRUD） | AdminOps 6 task、Embed 4 task、Analyst 11 task、Viewer 9 task；`docker_stats.py` 采集容器 CPU/内存 |
| **P5-6 k6 全脚本** | ✅ 完成 | 0.5 周 | login_storm / chart_list / explore_stress / endurance | 全部 9 个 k6 脚本（smoke / login_storm / dashboard_list / dashboard_detail / dashboard_render / chart_list / chart_data / explore_stress / endurance） |
| **P5-7 报告 + 文档** | 🚧 进行中 | 0.5 周 | Allure 附加、HTML 报告、对比工具、README | 元测试 13/13 通过；`compare_baseline.py` `--strict --exit-on-fail`；CHANGELOG.md 与本节 |

**总进度：~95%**（剩 P5-4 实际接 CI runner、P5-7 报告面板）

### 10.2 已落地文件清单

```
e2e/perf/
├── PLAN.md               # 本文档（v1.0 已实现）
├── README.md             # 快速开始
├── CHANGELOG.md          # 变更日志
├── requirements.txt      # locust / pyyaml / httpx
│
├── common/               # 6 个共享模块
│   ├── config_loader.py  # 加载 perf 段（deep-merge defaults）
│   ├── auth.py           # 复用 utils.api.login_client + 10min token 缓存
│   ├── metrics.py        # EndpointStats / MetricsCollector / Apdex / Stability
│   ├── thresholds.py     # load_baseline / save_baseline / is_critical_endpoint / compare
│   ├── docker_stats.py   # 后台线程采 docker stats → CSV
│   └── report.py         # render_summary / write_json_snapshot
│
├── locust/               # 4 角色 + LoginStorm
│   ├── locustfile.py     # 入口（按 config 注入 weight / version）
│   └── tasks/
│       ├── base.py       # SupersetUser / BaseBehavior / GLOBAL_METRICS
│       ├── admin_ops.py  # 写路径 CRUD
│       ├── analyst.py    # Explore / chart 写 / SQL Lab
│       ├── viewer.py     # ⭐ dashboard / chart 读路径
│       ├── embed.py      # 嵌入式访问
│       └── login_storm.py # 独立登录风暴
│
├── k6/scripts/           # 9 个 k6 脚本
│   ├── lib.js            # 共享 helper（每 VU 缓存 token）
│   ├── smoke.js          # 30 VU / 1 min
│   ├── login_storm.js    # 200 VU / 30s
│   ├── dashboard_list.js # 300 VU / 3 min（PR 必跑）
│   ├── dashboard_detail.js # 200 VU / 3 min
│   ├── dashboard_render.js # 150 VU / 3 min
│   ├── chart_list.js     # 200 VU / 2 min（PR 必跑）
│   ├── chart_data.js     # 100 VU / 5 min（4.1/6.0 payload 兼容）
│   ├── explore_stress.js # 100 VU / 2 min
│   └── endurance.js      # 50 VU / 30 min
│
├── baselines/
│   ├── v4_1.json         # 4.1 占位（待 P5-1 跑出）
│   └── v6_0.json         # 6.0 实测（10 VU / 2 min，16 端点，0 错误）
│
├── reports/              # 输出（gitignore）
│   └── locust/
│       ├── current_6.0.json
│       ├── summary_6.0.txt
│       ├── run_6.0_stats.csv
│       └── report_6.0.html
│
├── tools/                # 5 个工具
│   ├── wait_healthy.py
│   ├── run_locust.sh
│   ├── run_k6.sh
│   ├── compare_baseline.py
│   ├── save_baseline.py        # 角色变体聚合
│   └── collect_docker_stats.py
│
└── tests/                # 3 个元测试
    ├── test_config.py          # 4 passed
    ├── test_thresholds.py      # 4 passed
    └── test_baseline_schema.py # 5 passed（含 critical_endpoints_present）
```

**元测试结果**：`pytest perf/tests/ -v` → **13/13 passed**

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Locust 单机 RPS 上限 | 无法压出 6.0 真极限 | 切到 master/worker 分布式（master + 4 worker 可达 12k RPS） |
| 容器资源打满导致 Locust 测不准 | 数据失真 | Locust 跑在**宿主机或独立机器**，不在 Superset 同一容器 |
| 示例数据太少，压不出瓶颈 | 看不到 DB 慢查询 | 包装 `load_test_data` 复制 5x / 10x |
| CI 跑 5min 太慢 | 反馈周期长 | smoke 用 k6 1min 走阈值；Locust 30min 放 nightly |
| 4.1 与 6.0 阈值不同 | 维护成本 | thresholds.py 用版本 × 接口两套，文件分别存 |
| k6 装环境麻烦 | CI 失败 | Dockerfile 内置安装步骤；或 `docker run grafana/k6` |
| 基线随版本变化 | 阈值陈旧 | 每次 Superset 升版重新跑一次 30min 长跑覆盖基线 |

---

## 12. 不在 P5 范围（未来扩展）

- **WebSocket 压测**（`/ws/` 实时通知、Explore 自动保存）
- **前端渲染性能**（Playwright tracing + Lighthouse 集成）
- **跨数据中心**（多区域同步、CDN）
- **真实用户回放**（基于访问日志的 GoReplay / tcpreplay）
- **APM 集成**（OpenTelemetry → Jaeger / Datadog）
- **混沌工程**（ChaosBlade / Litmus，注入 DB 慢查询 / Redis 断连）

---

## 附录 A：依赖清单

`perf/requirements.txt`：

```text
locust==2.31.0
k6>=0.49.0         # 通过 apt 或 docker 安装
pandas>=2.0.0      # 报告汇总
matplotlib>=3.7.0  # 可选：生成趋势图
```

## 附录 B：快速开始

```bash
# 1. 安装依赖
pip install -r perf/requirements.txt
sudo apt-get install k6   # 或 brew install k6

# 2. 启动 Superset（cold 模式）
cd e2e && python run.py --mode cold

# 3. 等待健康
python perf/tools/wait_healthy.py --versions 4.1,6.0

# 4. 跑重点 k6 脚本（dashboard / chart / chart_data）
bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js   # 300 VU
bash perf/tools/run_k6.sh perf/k6/scripts/chart_list.js       # 200 VU
bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js       # 100 VU

# 5. 跑 Locust 10 分钟重点压测（200 VU）
bash perf/tools/run_locust.sh

# 6. 对比基线（重点查询更严）
python perf/tools/compare_baseline.py --version 6.0 \
  --current perf/reports/locust/current.json --strict --exit-on-fail

# 7. 启动 Web UI（实时观察）
locust -f perf/locust/locustfile.py --host http://localhost:18088
# 访问 http://localhost:8089，200 VU 20 spawn
```

## 附录 C：基线 JSON 样例

`perf/baselines/v6.0.json`：

```json
{
  "version": "6.0.0",
  "captured_at": "2026-06-20T10:00:00Z",
  "instance": "http://localhost:18089",
  "users": 30,
  "duration_sec": 300,
  "endpoints": {
    "GET /health": {"p50_ms": 5, "p95_ms": 12, "p99_ms": 18, "rps": 800},
    "POST /api/v1/security/login": {"p50_ms": 80, "p95_ms": 180, "p99_ms": 350, "rps": 60},
    "GET /api/v1/dashboard/": {"p50_ms": 90, "p95_ms": 200, "p99_ms": 400, "rps": 100},
    "POST /api/v1/chart/data": {"p50_ms": 350, "p95_ms": 900, "p99_ms": 1800, "rps": 50},
    "GET /api/v1/explore/": {"p50_ms": 150, "p95_ms": 400, "p99_ms": 700, "rps": 80},
    "GET /superset/dashboard/": {"p50_ms": 800, "p95_ms": 2200, "p99_ms": 4500, "rps": 30}
  }
}
```

## 附录 D：决策记录

- 2026-06-20：选 Locust 主、k6 副。理由：栈一致、复用 `utils/api.py`、易上手；k6 在 CI 阈值门禁与高并发场景下补位。
- 不选 wrk：脚本能力太弱，不能做"多步业务流"。
- 不选 JMeter：JVM 部署重、XML 难维护、不利于 QA 维护。
- 不选 Artillery：Node.js 引入增加环境复杂度；k6 同样场景下更轻。
