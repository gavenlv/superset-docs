#!/usr/bin/env bash
# k6 启动脚本：根据脚本名自动选择 VU / duration。
# 支持多环境 (E2E_ENV) 和多用户池 (K6_USERS_JSON 自动从 config 读取)。
#
# 用法：
#   # 默认 dev 环境，单 admin
#   bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
#
#   # 切到 sit 环境
#   E2E_ENV=sit bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
#
#   # 多用户：自动从 e2e/config/config.<env>.yaml 的 user_pool.viewer 拉
#   bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js --multi-user viewer
set -euo pipefail
cd "$(dirname "$0")/../.."

SCRIPT="${1:-perf/k6/scripts/dashboard_list.js}"
shift || true

# 多用户模式：--multi-user <role> 自动从 user_pool.<role> 拉凭据
MULTI_USER_ROLE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --multi-user)
            MULTI_USER_ROLE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

E2E_ENV="${E2E_ENV:-dev}"
PERF_TARGET_VERSION="${PERF_TARGET_VERSION:-6.0}"
case "$PERF_TARGET_VERSION" in
    4.1) HOST="${PERF_HOST:-http://localhost:18088}" ;;
    6.0) HOST="${PERF_HOST:-http://localhost:18089}" ;;
esac

# 等待健康
python perf/tools/wait_healthy.py --versions "$PERF_TARGET_VERSION" --env "$E2E_ENV" --timeout 300

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

# 构造 K6_USERS_JSON
if [[ -n "$MULTI_USER_ROLE" ]]; then
    K6_USERS_JSON=$(python -c "
import json
from config.settings import CONFIG
users = CONFIG.users_for_role('$MULTI_USER_ROLE')
print(json.dumps([{'username': u.username, 'password': u.password, 'role': u.role} for u in users]))
")
    echo "[run_k6] multi-user mode: role=$MULTI_USER_ROLE, count=$(echo "$K6_USERS_JSON" | python -c 'import json,sys; print(len(json.load(sys.stdin)))')"
    export K6_USERS_JSON
fi

mkdir -p perf/reports/k6
echo "[run_k6] env=$E2E_ENV target=$PERF_TARGET_VERSION host=$HOST"
echo "k6 $OPTS  $SCRIPT"

SUPERSET_URL="$HOST" \
VUS="$(echo $OPTS | sed -n 's/.*--vus \([0-9]*\).*/\1/p')" \
DURATION="$(echo $OPTS | sed -n 's/.*--duration \([^ ]*\).*/\1/p')" \
    k6 run "$SCRIPT" \
        --out json=perf/reports/k6/$(basename "$SCRIPT" .js).json
