// k6 重点脚本：chart 列表高并发
// 端点：GET /api/v1/chart/?q=...
// 默认 200 VU / 2 min
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 200),
  duration: __ENV.DURATION || "2m",
  thresholds: {
    "http_req_duration{name:chart_list}": ["p(95)<300", "p(99)<600"],
    "http_req_failed": ["rate<0.005"],
  },
};

export default function () {
  const token = login();
  const url = `${BASE_URL}/api/v1/chart/?q=${encodeURIComponent(
    JSON.stringify({ page: 0, page_size: 50 })
  )}`;
  const res = http.get(url, {
    ...authHeaders(token),
    tags: { name: "chart_list" },
  });
  check(res, {
    "status 200": (r) => r.status === 200,
    "has result[]": (r) => Array.isArray(r.json("result")),
  });
  sleep(0.1);
}
