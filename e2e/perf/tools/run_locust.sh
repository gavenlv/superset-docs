#!/usr/bin/env bash
# Locust 启动脚本：默认 200 VU / 10 min，重点压 dashboard / charts / chart_data
# 支持多环境 (E2E_ENV) 和多用户池（自动从 config 读）。
#
# 用法：
#   bash perf/tools/run_locust.sh                                # dev 6.0
#   E2E_ENV=sit bash perf/tools/run_locust.sh                    # SIT 6.0
#   PERF_TARGET_VERSION=4.1 bash perf/tools/run_locust.sh        # 4.1
#   bash perf/tools/run_locust.sh --web                          # 启动 Web UI
#   USERS=500 SPAWN_RATE=50 bash perf/tools/run_locust.sh        # 调整并发
#
# Windows 注意：locust 在 Windows 上读取 pyproject.toml 时会因为 GBK 解码失败，
# 请确保在跑此脚本前 export PYTHONUTF8=1（或在 CI 里设置）。
set -euo pipefail
cd "$(dirname "$0")/../.."

# Windows 兼容：locust 的 configargparse 用系统默认编码（GBK）读 pyproject.toml
# 会失败。强制 UTF-8 模式让 Python 用 utf-8 解码。
export PYTHONUTF8=${PYTHONUTF8:-1}
export PYTHONIOENCODING=${PYTHONIOENCODING:-utf-8}

PERF_TARGET_VERSION="${PERF_TARGET_VERSION:-6.0}"
E2E_ENV="${E2E_ENV:-dev}"
USERS="${USERS:-200}"
SPAWN_RATE="${SPAWN_RATE:-20}"
RUN_TIME="${RUN_TIME:-10m}"
HOST="${PERF_HOST:-}"

# E2E_ENV 决定默认 host（如未显式 PERF_HOST）
if [[ -z "$HOST" ]]; then
    case "$PERF_TARGET_VERSION" in
        4.1) HOST=$(python -c "
import os
os.environ.setdefault('E2E_ENV', '$E2E_ENV')
from config.settings import CONFIG
for i in CONFIG.instances:
    if i.name == '4.1':
        print(i.base_url); break
") ;;
        6.0) HOST=$(python -c "
import os
os.environ.setdefault('E2E_ENV', '$E2E_ENV')
from config.settings import CONFIG
for i in CONFIG.instances:
    if i.name == '6.0':
        print(i.base_url); break
") ;;
        *)   echo "unknown version: $PERF_TARGET_VERSION"; exit 1 ;;
    esac
fi

# 等待健康（带 env）
python perf/tools/wait_healthy.py --versions "$PERF_TARGET_VERSION" --env "$E2E_ENV" --timeout 300

# 打印多用户池概览
python -c "
import os
os.environ.setdefault('E2E_ENV', '$E2E_ENV')
from config.settings import CONFIG
print(f'[run_locust] env={CONFIG.env} target=$PERF_TARGET_VERSION host=$HOST')
print('[run_locust] user_pool:')
for role, users in CONFIG.user_pool.items():
    print(f'  {role:>8}  ({len(users)} users): {[u.username for u in users]}')
"

REPORTS_DIR="perf/reports/locust"
mkdir -p "$REPORTS_DIR"

if [[ "${1:-}" == "--web" ]]; then
    echo "Starting Locust Web UI at http://localhost:8089"
    PERF_TARGET_VERSION="$PERF_TARGET_VERSION" \
        locust -f perf/locust/locustfile.py --host "$HOST"
else
    echo "Locust headless: $USERS VU / spawn $SPAWN_RATE / $RUN_TIME / host=$HOST"
    PERF_TARGET_VERSION="$PERF_TARGET_VERSION" \
        locust -f perf/locust/locustfile.py \
            --host "$HOST" \
            --users "$USERS" --spawn-rate "$SPAWN_RATE" --run-time "$RUN_TIME" \
            --headless \
            --csv="$REPORTS_DIR/run_$PERF_TARGET_VERSION" \
            --html="$REPORTS_DIR/report_$PERF_TARGET_VERSION.html"
fi
