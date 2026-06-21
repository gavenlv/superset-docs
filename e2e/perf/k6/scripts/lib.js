// k6 共享 helper：登录获取 JWT、共享 base URL、每 VU 缓存 token。
// 用法：import { login, authHeaders, BASE_URL } from "./lib.js";
import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.SUPERSET_URL || "http://localhost:18089";
const USERNAME = __ENV.SUPERSET_USER || "admin";
const PASSWORD = __ENV.SUPERSET_PASSWORD || "admin";

// 进程级 token 池（避免每轮都登录）
const _tokenPool = {};

function _acquireToken(force = false) {
  if (!force && _tokenPool.__token) return _tokenPool.__token;
  const url = `${BASE_URL}/api/v1/security/login`;
  const payload = JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
    provider: "db",
    refresh: true,
  });
  const params = { headers: { "Content-Type": "application/json" } };
  const res = http.post(url, payload, params);
  const ok = check(res, {
    "login status 200": (r) => r.status === 200,
    "login has access_token": (r) => (r.json("access_token") || "") !== "",
  });
  if (!ok) {
    fail(`login failed: status=${res.status} body=${res.body}`);
  }
  _tokenPool.__token = res.json("access_token");
  return _tokenPool.__token;
}

// 每 VU 缓存一次 token（10 分钟 TTL），不每轮都登录。
function _getVUToken() {
  const vu = __VU;
  const now = Date.now();
  if (
    _tokenPool[vu] &&
    now - _tokenPool[vu].ts < 10 * 60 * 1000
  ) {
    return _tokenPool[vu].token;
  }
  const token = _acquireToken();
  _tokenPool[vu] = { token, ts: now };
  return token;
}

export function login() {
  // 第一次会有多个 VU 一起登录的尖峰（可接受），后续每 VU 复用。
  return _getVUToken();
}

export function authHeaders(token) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  };
}

export { BASE_URL };
