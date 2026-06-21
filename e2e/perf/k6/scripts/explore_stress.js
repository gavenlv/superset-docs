// k6 explore 加载
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 100),
  duration: __ENV.DURATION || "2m",
  thresholds: {
    "http_req_failed": ["rate<0.01"],
    "http_req_duration": ["p(95)<1500"],
  },
};

export default function () {
  const token = login();
  const headers = authHeaders(token);
  const list = http.get(
    `${BASE_URL}/api/v1/chart/?q=${encodeURIComponent(
      JSON.stringify({ page: 0, page_size: 50 })
    )}`,
    { ...headers, tags: { name: "list_warm" } }
  );
  const items = list.json("result") || [];
  if (items.length === 0) {
    sleep(1);
    return;
  }
  const id = items[Math.floor(Math.random() * items.length)].id;
  const res = http.get(`${BASE_URL}/api/v1/explore/?slice_id=${id}`, {
    ...headers,
    tags: { name: "explore" },
  });
  check(res, { "200": (r) => r.status === 200 });
  sleep(0.2);
}
