// k6 共享 helper：登录获取 JWT、共享 base URL、每 VU 缓存 token。
// 用法：import { login, authHeaders, BASE_URL } from "./lib.js";
//
// 多用户：
// - 通过 K6_USERS_JSON 环境变量传入 JSON 数组（每项 {username,password,role}）
// - 例：K6_USERS_JSON='[{"username":"v1","password":"p"},{"username":"v2","password":"p"}]'
// - 不传则回退到单 admin 用户
// - 每 VU 用 (VU-1) % pool_size 选用户 → round-robin 均匀分布
import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.SUPERSET_URL || "http://localhost:18089";
const DEFAULT_USERNAME = __ENV.SUPERSET_USER || "admin";
const DEFAULT_PASSWORD = __ENV.SUPERSET_PASSWORD || "admin";

// 进程级 token 池（避免每轮都登录）
const _tokenPool = {};

// 解析 K6_USERS_JSON，得出用户池（[{username, password, role}]）
function _parseUserPool() {
  const raw = __ENV.K6_USERS_JSON;
  if (!raw) {
    return [{ username: DEFAULT_USERNAME, password: DEFAULT_PASSWORD, role: "admin" }];
  }
  try {
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr) || arr.length === 0) {
      return [{ username: DEFAULT_USERNAME, password: DEFAULT_PASSWORD, role: "admin" }];
    }
    return arr;
  } catch (e) {
    fail(`K6_USERS_JSON parse error: ${e.message}`);
    return [{ username: DEFAULT_USERNAME, password: DEFAULT_PASSWORD, role: "admin" }];
  }
}

const _users = _parseUserPool();

export function pickUser(vuId) {
  // 每 VU 绑定一个用户（round-robin，VU=1 → users[0]，VU=2 → users[1] ...）
  const idx = (vuId - 1) % _users.length;
  return _users[idx];
}

function _acquireToken(username, password) {
  const url = `${BASE_URL}/api/v1/security/login`;
  const payload = JSON.stringify({
    username: username,
    password: password,
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
    fail(`login failed for user ${username}: status=${res.status} body=${res.body}`);
  }
  return res.json("access_token");
}

// 每 VU 缓存一次 token（10 分钟 TTL），不每轮都登录。
function _getVUToken(force = false) {
  const vu = __VU;
  const user = pickUser(vu);
  const cacheKey = `vu-${vu}`;
  const now = Date.now();
  if (
    !force &&
    _tokenPool[cacheKey] &&
    now - _tokenPool[cacheKey].ts < 10 * 60 * 1000
  ) {
    return _tokenPool[cacheKey].token;
  }
  const token = _acquireToken(user.username, user.password);
  _tokenPool[cacheKey] = { token, ts: now, user: user.username };
  return token;
}

export function login() {
  // 第一次会有多个 VU 一起登录的尖峰（可接受），后续每 VU 复用。
  return _getVUToken();
}

export function currentUsername() {
  return pickUser(__VU).username;
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
