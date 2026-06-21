# Jenkins 性能测试运行指南

> 配套 [Jenkinsfile](../../../../Jenkinsfile)（项目根），与 [`.github/workflows/perf.yml`](file:///d:/workspace/superset-space/superset-docs/.github/workflows/perf.yml) 镜像。

## 1. 架构总览

```
                    ┌─────────────────────┐
                    │   GitHub / 手动     │
                    │  (webhook / UI)     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Jenkins Controller │
                    │  (Pipeline as Code) │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────────┐
        │  Agent 1 │   │  Agent 2 │   │ Superset 容器│
        │ perf-    │   │ perf-    │   │ (4.1 + 6.0)  │
        │ runner-A │   │ runner-B │   └──────────────┘
        └──────────┘   └──────────┘
```

**关键决策**：

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 流水线 | Pipeline as Code（Jenkinsfile） | 与 GitHub Actions 一致，版本化 |
| Agent | 专用 `perf-runner` 标签 | 避免与 E2E/UI agent 争资源 |
| Superset 启动位置 | Agent 本地 docker compose | 减少网络跳数，模拟真实部署 |
| 档位 | pr-gate / nightly / release / smoke | 与 GHA 同结构，按需调度 |
| 并发 | `disableConcurrentBuilds()` | 防止多构建撞 Superset 容器 |

## 2. 前置准备

### 2.1 Jenkins 插件清单

```
pipeline-stage-view
workflow-aggregator          # Pipeline 核心
git                          # 4.x+
docker-workflow              # 可选，本 Jenkinsfile 用 shell 而非 plugin
ws-cleanup                   # cleanup 阶段用
AnsiColor                    # 日志彩色
```

### 2.2 Agent 节点要求

- 操作系统：Ubuntu 22.04 LTS（推荐）或 20.04
- CPU：≥ 8 核（Locust + Superset 同时跑）
- 内存：≥ 16 GB
- 磁盘：≥ 50 GB（压测报告 + 容器镜像）
- Docker：≥ 24.0
- 标签：`perf-runner && linux && docker`
- 必须能 `docker compose` 拉起 `superset-4.1` / `superset-6.0` 容器

### 2.3 Agent 初始化脚本（首次配置）

```bash
# 1. 装 docker（如果 agent 是裸机）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker jenkins

# 2. 装 python 工具链
sudo apt-get install -y python3-pip python3-venv

# 3. 装 k6
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 \
    --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb https://dl.k6.io/deb stable main" | \
    sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install -y k6

# 4. 验证
docker --version
k6 version
python3 --version
```

### 2.4 凭据与权限

- **Git 拉取**：Jenkins → Credentials → System → Global credentials → 添加 `git` 类型凭据（Username + Password 或 SSH Key）
- **Superset 启动**：Jenkins 用户加入 `docker` 组（见 2.3 步骤 1）

## 3. 创建 Pipeline Job

### 3.1 UI 创建

1. Jenkins 首页 → **New Item**
2. 输入名称 `superset-perf`
3. 类型选 **Pipeline**
4. 点 OK
5. 在配置页：
   - **Build Triggers**：根据需要勾选
     - ☑ GitHub hook trigger for GITScm polling（接 PR webhook）
     - ☑ Poll SCM（H/30 * * * *，作为兜底）
   - **Pipeline**：
     - Definition：**Pipeline script from SCM**
     - SCM：**Git**
     - Repository URL：`https://github.com/<org>/superset-docs.git`
     - Credentials：选你创建的 git 凭据
     - Branch Specifier：`*/main`（或 `*/develop`）
     - Script Path：**`Jenkinsfile`**

### 3.2 Jenkinsfile in Repo

> 已交付：[Jenkinsfile](../../../../Jenkinsfile)（项目根）

### 3.3 参数说明

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `MODE` | `nightly` | `pr-gate`=轻量 / `nightly`=标准 / `release`=大压 / `smoke`=最小 |
| `SUPERSET_VERSION` | `6.0` | `4.1` / `6.0` / `both`（nightly/release 可 both） |
| `DURATION_MIN` | `10` | Locust 持续时间（分钟） |
| `USERS` | `200` | Locust 并发用户数 |

## 4. 触发方式

### 4.1 手动触发（最直接）

1. 进入 `superset-perf` job
2. 左侧 **Build with Parameters**
3. 选 `MODE` / `SUPERSET_VERSION` / `DURATION_MIN` / `USERS`
4. 点 **Build**

### 4.2 定时触发（nightly）

Jenkinsfile 已用 `cron` 在 GHA 里跑。Jenkins 这边需要在 job 配置里加：

- **Build Triggers** → ☑ **Build periodically**
- Schedule：`0 2 * * *`（每天 02:00 UTC = 北京时间 10:00）

### 4.3 Webhook 触发（PR gate）

#### GitHub

1. 仓库 → Settings → Webhooks → Add webhook
2. Payload URL：`https://<jenkins>/github-webhook/`
3. Content type：`application/json`
4. Events：`Pull requests` + `Push`
5. Jenkins job 勾选 **GitHub hook trigger for GITScm polling**

#### GitLab

1. 项目 → Settings → Webhooks
2. URL：`https://<jenkins>/project/superset-perf`
3. Trigger：**Merge request events** + **Push events**
4. Jenkins 装 **GitLab Plugin** 后用 **GitLab connection** 触发

## 5. 运行档位详解

### 5.1 `pr-gate`（PR 必跑门禁）

- **目标**：5 分钟反馈周期，验证重点查询不退化
- **跑什么**：
  - 元测试（13 个）
  - k6 `dashboard_list` (300 VU / 3 min)
  - k6 `chart_list` (200 VU / 2 min)
- **不跑**：Locust（避免 PR 阶段跑 10 min）
- **不对比基线**：pr-gate 阶段没新基线产生
- **期望时长**：~6 min

### 5.2 `nightly`（每晚标准压测）

- **目标**：完整跑 4.1 + 6.0 的 Locust + 重点 k6 全部，对比基线
- **跑什么**：
  - 元测试
  - Locust 10 min × {4.1, 6.0}（如 `SUPERSET_VERSION=both`）
  - k6 `chart_data` (5 min) + `dashboard_detail` (3 min) + `dashboard_render` (3 min)
  - 基线对比（strict）
  - 容器资源采集
- **期望时长**：~30 min

### 5.3 `release`（发布前大压）

- **目标**：release 前 30 min × {4.1, 6.0} 长跑
- **跑什么**：与 nightly 相同，但 Locust 改 30 min（手动调 `DURATION_MIN=30`）
- **期望时长**：~80 min

### 5.4 `smoke`（开发自验）

- **目标**：本地改动后快速验证 pipeline 可执行
- **跑什么**：仅 pr-gate 的 k6（不跑 Locust）
- **期望时长**：~6 min

## 6. 报告与产物

### 6.1 Jenkins 内置产物

Jenkinsfile `post.always.archiveArtifacts` 会保留：

```
e2e/perf/reports/locust/
├── current_6.0.json          # Locust 快照
├── summary_6.0.txt           # 表格化汇总
├── run_6.0_stats.csv         # Locust 原生
├── report_6.0.html           # Locust 原生 HTML
└── docker_stats_6.0.csv      # 容器 CPU/内存时间序列
e2e/perf/reports/k6/
├── dashboard_list.json       # k6 原生 JSON 输出
├── chart_list.json
└── ...
```

下载方式：构建页 → **Build Artifacts** → 选 build 编号 → 下载 zip

### 6.2 关键指标速查

压测结束后 Jenkins Console Output 末尾会打印 `summary_*.txt`：

```
GET /api/v1/dashboard/             204 req  p50=313.5ms p95=831.8ms p99=1243.7ms
POST /api/v1/chart/data            156 req  p50=85.6ms  p95=245.4ms p99=419.3ms
GET /api/v1/dashboard/{id}        151 req  p50=60.0ms  p95=224.2ms p99=309.6ms
```

### 6.3 趋势看板（可选）

- **方案 A（简单）**：在 Jenkins 装 **Plot Plugin**，把 `summary_*.txt` 画成时序图
- **方案 B（推荐）**：把 `current_*.json` + `docker_stats_*.csv` 推到 InfluxDB，用 Grafana 看
- **方案 C（最简）**：每次构建后跑 `compare_baseline.py` 把 violation 写到 Jenkins 的 JUnit 报告里

## 7. 失败判定与处理

### 7.1 三种失败模式

| 模式 | 含义 | Jenkins 状态 | 处理 |
| --- | --- | :---: | --- |
| 元测试失败 | 配置/基线/schema 不对 | ❌ FAILURE | 看 Console Output，pytest 输出会指明 |
| k6 阈值失败 | p95 > 阈值 / error > 阈值 | ❌ FAILURE | k6 会打印 breached thresholds |
| Locust 基线超阈值 | p95 +20% 重点 / +50% 普通 | ❌ FAILURE（`--exit-on-fail`） | 看 compare_baseline 输出 |

### 7.2 常见问题

#### Q1: `docker compose` 找不到
```
A: agent 没装 docker-compose v2。装 plugin：
   sudo apt-get install docker-compose-plugin
   或用 docker-compose v1：`pip install docker-compose`
```

#### Q2: k6 安装失败（keyserver 超时）
```
A: 公司内网环境。把 k6 改成 docker 跑：
   docker run --rm -i grafana/k6 run - <perf/k6/scripts/dashboard_list.js
   或提前在 agent 上传 k6 二进制到 /usr/local/bin/k6
```

#### Q3: Locust 报 GBK 错误（仅 Windows agent）
```
A: Jenkinsfile 已设 PYTHONUTF8=1 / PYTHONIOENCODING=utf-8。
   Linux agent 不会触发，但保留以防万一。
```

#### Q4: Superset 启动慢，wait_healthy 超时
```
A: 加 wait_healthy 的 --timeout 到 600（10 min）：
   python3 e2e/perf/tools/wait_healthy.py --timeout 600
   cold 模式首次启动 4.1 + 6.0 通常 3-5 min
```

#### Q5: 报告没上传
```
A: 检查 Jenkinsfile archiveArtifacts 路径是否与实际生成路径一致。
   加 allowEmptyArchive: true（已加）防止因空目录失败。
```

## 8. 与 GitHub Actions 的对照

| 维度 | GHA | Jenkins |
| --- | --- | --- |
| 流水线定义 | `.github/workflows/perf.yml` | `Jenkinsfile` |
| 触发 | `on:` YAML 段 | `Build Triggers` UI + Jenkinsfile `when` |
| 矩阵 | `strategy.matrix` | `script { }` + `parallel` |
| 产物 | `actions/upload-artifact` | `archiveArtifacts` |
| Secrets | Repository secrets | Credentials + env |
| 缓存 | `actions/cache` | `cache` 插件（当前未用，agent 干净起步） |
| PR 反馈 | PR comment + check | Jenkinsfile post（无 PR 集成） |

**两套并存策略**：
- 内部 CI 用 Jenkins（资源可控）
- 开源 PR 用 GHA（社区友好）
- 流水线逻辑镜像，调试成本低

## 9. 安全注意事项

1. **不要在 Jenkinsfile 里硬编码密码**（Superset admin 凭据从 `e2e/config/config.yaml` 读，CI 里通过环境变量覆盖）
2. **agent 之间不共享文件系统**（用 `WORKSPACE` env 区分）
3. **disableConcurrentBuilds** 已开，防止撞 Superset
4. **post.cleanup** 会关容器，避免资源泄漏
5. **k6 / Locust 不要跑在 Superset 容器内**，必须在独立 agent 上

## 10. 快速检查清单

新建 Jenkins job 后跑一次 smoke 模式自检：

- [ ] Agent 节点标签匹配（`perf-runner && linux && docker`）
- [ ] Git 凭据可拉到代码
- [ ] docker compose 能起 `superset-4.1` / `superset-6.0`
- [ ] k6 已装（`k6 version`）
- [ ] Python 依赖能装（`pip install -r e2e/requirements.txt -r e2e/perf/requirements.txt`）
- [ ] 元测试通过（13/13）
- [ ] `MODE=smoke` 跑通（k6 dashboard_list + chart_list 不超阈值）
- [ ] 报告 artifact 能下载
- [ ] 失败时 Console Output 能看到 `compare_baseline` 的 violation 列表

通过以上 9 项即可投入正式使用。
