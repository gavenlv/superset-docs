// k6 重点脚本：dashboard HTML 页面渲染
// 端点：GET /superset/dashboard/{id}/
// 默认 150 VU / 3 min
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 150),
  duration: __ENV.DURATION || "3m",
  thresholds: {
    "http_req_duration{name:dashboard_render}": ["p(95)<3000", "p(99)<5000"],
    "http_req_failed{name:dashboard_render}": ["rate<0.005"],
  },
};

export default function () {
  const token = login();
  const list = http.get(
    `${BASE_URL}/api/v1/dashboard/?q=${encodeURIComponent(
      JSON.stringify({ page: 0, page_size: 25 })
    )}`,
    { ...authHeaders(token), tags: { name: "list_warm" } }
  );
  const items = list.json("result") || [];
  if (items.length === 0) {
    sleep(1);
    return;
  }
  const id = items[Math.floor(Math.random() * items.length)].id;
  const res = http.get(`${BASE_URL}/superset/dashboard/${id}/`, {
    ...authHeaders(token),
    tags: { name: "dashboard_render" },
  });
  check(res, { "html 200": (r) => r.status === 200 });
  sleep(0.5);
}
