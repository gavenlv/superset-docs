#!/usr/bin/env bash
# k6 启动脚本：根据脚本名自动选择 VU / duration。
#
# 用法：
#   bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
#   bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js
set -euo pipefail
cd "$(dirname "$0")/../.."

SCRIPT="${1:-perf/k6/scripts/dashboard_list.js}"
PERF_TARGET_VERSION="${PERF_TARGET_VERSION:-6.0}"
case "$PERF_TARGET_VERSION" in
    4.1) HOST="${PERF_HOST:-http://localhost:18088}" ;;
    6.0) HOST="${PERF_HOST:-http://localhost:18089}" ;;
esac

# 等待健康
python perf/tools/wait_healthy.py --versions "$PERF_TARGET_VERSION" --timeout 300

# 选 VU / duration
case "$SCRIPT" in
    *smoke*)            OPTS="--vus 30  --duration 1m"  ;;
    *dashboard_list*)   OPTS="--vus 300 --duration 3m"  ;;
    *dashboard_detail*) OPTS="--vus 200 --duration 3m"  ;;
    *dashboard_render*) OPTS="--vus 150 --duration 3m"  ;;
    *chart_list*)       OPTS="--vus 200 --duration 2m"  ;;
    *chart_data*)       OPTS="--vus 100 --duration 5m"  ;;
    *login_storm*)      OPTS="--vus 200 --duration 30s" ;;
    *endurance*)        OPTS="--vus 50  --duration 30m" ;;
    *explore_stress*)   OPTS="--vus 100 --duration 2m"  ;;
    *)                  OPTS="--vus 100 --duration 3m"  ;;
esac

mkdir -p perf/reports/k6
echo "k6 $OPTS  $SCRIPT  (host=$HOST)"

SUPERSET_URL="$HOST" \
VUS="$(echo $OPTS | sed -n 's/.*--vus \([0-9]*\).*/\1/p')" \
DURATION="$(echo $OPTS | sed -n 's/.*--duration \([^ ]*\).*/\1/p')" \
    k6 run "$SCRIPT" \
        --out json=perf/reports/k6/$(basename "$SCRIPT" .js).json
