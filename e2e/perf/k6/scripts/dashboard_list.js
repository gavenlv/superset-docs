// k6 重点脚本：dashboard 列表高并发
// 目标端点：GET /api/v1/dashboard/?q=...
// 默认 300 VU / 3 min
//
// 用法：
//   SUPERSET_URL=http://localhost:18089 k6 run perf/k6/scripts/dashboard_list.js
//
// VU / duration 通过 CLI 覆盖：
//   k6 run --vus 300 --duration 3m perf/k6/scripts/dashboard_list.js
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 300),
  duration: __ENV.DURATION || "3m",
  thresholds: {
    // 重点查询：p95 < 250ms，error < 0.5%
    "http_req_duration{name:dashboard_list}": ["p(95)<250", "p(99)<500"],
    "http_req_failed{name:dashboard_list}": ["rate<0.005"],
    "http_reqs": ["rate>100"],  // 至少 100 RPS
  },
};

export default function () {
  // 每个 VU 启动时登录一次
  const token = login();
  const url = `${BASE_URL}/api/v1/dashboard/?q=${encodeURIComponent(
    JSON.stringify({ page: 0, page_size: 25 })
  )}`;
  const res = http.get(url, {
    ...authHeaders(token),
    tags: { name: "dashboard_list" },
  });
  check(res, {
    "status 200": (r) => r.status === 200,
    "has result[]": (r) => Array.isArray(r.json("result")),
  });
  sleep(0.1);
}
