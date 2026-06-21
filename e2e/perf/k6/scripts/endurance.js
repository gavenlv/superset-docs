// k6 endurance：50 VU / 30 min，检测内存泄漏
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || "30m",
  thresholds: {
    "http_req_failed": ["rate<0.01"],
    // 漂移检测：CI 后续用 perf/tools/compare_drift.py 对比 0~10min vs 20~30min 的 p99
  },
};

export default function () {
  const token = login();
  const url = `${BASE_URL}/api/v1/dashboard/?q=${encodeURIComponent(
    JSON.stringify({ page: 0, page_size: 25 })
  )}`;
  const res = http.get(url, { ...authHeaders(token) });
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(1);
}
