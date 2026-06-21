// k6 smoke：30 VU / 1 min，覆盖 dashboard/chart/dataset 主要读接口
// CI 门禁基础
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

export const options = {
  vus: Number(__ENV.VUS || 30),
  duration: __ENV.DURATION || "1m",
  thresholds: {
    "http_req_failed": ["rate<0.01"],
    "http_req_duration": ["p(95)<800"],
  },
};

export default function () {
  const token = login();
  const headers = authHeaders(token);
  const cases = [
    { name: "smoke_dashboard_list", url: `${BASE_URL}/api/v1/dashboard/` },
    { name: "smoke_chart_list", url: `${BASE_URL}/api/v1/chart/` },
    { name: "smoke_dataset_list", url: `${BASE_URL}/api/v1/dataset/` },
    { name: "smoke_me", url: `${BASE_URL}/api/v1/me/` },
    { name: "smoke_health", url: `${BASE_URL}/health` },
  ];
  for (const c of cases) {
    const res = http.get(c.url, { ...headers, tags: { name: c.name } });
    check(res, { "status 2xx": (r) => r.status >= 200 && r.status < 400 });
  }
  sleep(1);
}
