// k6 重点脚本：dashboard 详情 + charts 子列表
// 端点：GET /api/v1/dashboard/{id} + GET /api/v1/dashboard/{id}/charts
// 默认 200 VU / 3 min
//
// 6.0 路径：/api/v1/dashboard/{id}/charts（无尾斜杠）
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 200),
  duration: __ENV.DURATION || "3m",
  thresholds: {
    "http_req_duration{name:dashboard_detail}": ["p(95)<350", "p(99)<700"],
    "http_req_duration{name:dashboard_charts}": ["p(95)<350", "p(99)<700"],
    "http_req_failed": ["rate<0.005"],
  },
};

function pickId(arr) {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)].id;
}

export default function () {
  const token = login();
  const listUrl = `${BASE_URL}/api/v1/dashboard/?q=${encodeURIComponent(
    JSON.stringify({ page: 0, page_size: 25 })
  )}`;
  const list = http.get(listUrl, {
    ...authHeaders(token),
    tags: { name: "dashboard_list_warm" },
  });
  const items = list.json("result") || [];
  if (items.length === 0) {
    sleep(1);
    return;
  }
  const id = pickId(items);
  if (!id) {
    sleep(1);
    return;
  }
  const detail = http.get(`${BASE_URL}/api/v1/dashboard/${id}`, {
    ...authHeaders(token),
    tags: { name: "dashboard_detail" },
  });
  check(detail, { "detail 200": (r) => r.status === 200 });

  // 6.0: 不带尾斜杠
  const charts = http.get(`${BASE_URL}/api/v1/dashboard/${id}/charts`, {
    ...authHeaders(token),
    tags: { name: "dashboard_charts" },
  });
  check(charts, { "charts 200": (r) => r.status === 200 });
  sleep(0.2);
}
