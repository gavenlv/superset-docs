// k6 登录风暴：200 VU 集中登录
// 端点：POST /api/v1/security/login
// 默认 200 VU / 30s
import http from "k6/http";
import { check } from "k6";
import { BASE_URL } from "./lib.js";

const USERNAME = __ENV.SUPERSET_USER || "admin";
const PASSWORD = __ENV.SUPERSET_PASSWORD || "admin";

export const options = {
  vus: Number(__ENV.VUS || 200),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    "http_req_duration{name:login_storm}": ["p(95)<1500"],
    "http_req_failed{name:login_storm}": ["rate<0.005"],
  },
};

export default function () {
  const url = `${BASE_URL}/api/v1/security/login`;
  const body = JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
    provider: "db",
    refresh: true,
  });
  const res = http.post(url, body, {
    headers: { "Content-Type": "application/json" },
    tags: { name: "login_storm" },
  });
  check(res, {
    "status 200": (r) => r.status === 200,
    "has access_token": (r) => (r.json("access_token") || "") !== "",
  });
}
