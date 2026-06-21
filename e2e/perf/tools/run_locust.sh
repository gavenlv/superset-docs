#!/usr/bin/env bash
# Locust 启动脚本：默认 200 VU / 10 min，重点压 dashboard / charts / chart_data
#
# 用法：
#   bash perf/tools/run_locust.sh                          # 默认 6.0
#   PERF_TARGET_VERSION=4.1 bash perf/tools/run_locust.sh  # 压 4.1
#   bash perf/tools/run_locust.sh --web                    # 启动 Web UI
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
HOST="${PERF_HOST:-}"
case "$PERF_TARGET_VERSION" in
    4.1) HOST="${HOST:-http://localhost:18088}" ;;
    6.0) HOST="${HOST:-http://localhost:18089}" ;;
    *)   echo "unknown version: $PERF_TARGET_VERSION"; exit 1 ;;
esac

# 等待健康
python perf/tools/wait_healthy.py --versions "$PERF_TARGET_VERSION" --timeout 300

REPORTS_DIR="perf/reports/locust"
mkdir -p "$REPORTS_DIR"

if [[ "${1:-}" == "--web" ]]; then
    echo "Starting Locust Web UI at http://localhost:8089 (host=$HOST)"
    PERF_TARGET_VERSION="$PERF_TARGET_VERSION" \
        locust -f perf/locust/locustfile.py --host "$HOST"
else
    echo "Locust headless: 200 VU / 10 min / host=$HOST"
    PERF_TARGET_VERSION="$PERF_TARGET_VERSION" \
        locust -f perf/locust/locustfile.py \
            --host "$HOST" \
            --users 200 --spawn-rate 20 --run-time 10m \
            --headless \
            --csv="$REPORTS_DIR/run_$PERF_TARGET_VERSION" \
            --html="$REPORTS_DIR/report_$PERF_TARGET_VERSION.html"
fi

