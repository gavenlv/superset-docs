// k6 重点脚本：POST /api/v1/chart/data ⭐⭐ 最重
// 默认 100 VU / 5 min
// 阈值：p95 < 2000ms，error < 1%
//
// 4.1 用 slice_id 格式；6.0 用 datasource+queries 格式。
// 通过 SUPERSET_VERSION（4.1|6.0，默认 6.0）自动切换。
import http from "k6/http";
import { check, sleep } from "k6";
import { login, authHeaders, BASE_URL } from "./lib.js";

const SUPERSET_VERSION = __ENV.SUPERSET_VERSION || "6.0";

export const options = {
  vus: Number(__ENV.VUS || 100),
  duration: __ENV.DURATION || "5m",
  thresholds: {
    "http_req_duration{name:chart_data}": ["p(95)<2000", "p(99)<4000"],
    "http_req_failed{name:chart_data}": ["rate<0.01"],
  },
};

function pickChartId(arr) {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)].id;
}

// 跨版本 payload：6.0 用 datasource+queries；4.1 用 slice_id
function buildChartDataBody(sliceId) {
  if (SUPERSET_VERSION === "4.1") {
    return JSON.stringify({
      slice_id: sliceId,
      result_type: "full",
      result_format: "json",
      force: false,
    });
  }
  return JSON.stringify({
    datasource: { id: sliceId, type: "table" },
    queries: [
      {
        columns: [],
        metrics: [],
        row_limit: 5,
        orderby: [],
        filters: [],
        extras: {},
      },
    ],
  });
}

export default function () {
  const token = login();
  const url = `${BASE_URL}/api/v1/chart/?q=${encodeURIComponent(
    JSON.stringify({ page: 0, page_size: 50 })
  )}`;
  const list = http.get(url, {
    ...authHeaders(token),
    tags: { name: "chart_list_warm" },
  });
  const items = list.json("result") || [];
  const cid = pickChartId(items);
  if (!cid) {
    sleep(1);
    return;
  }
  const body = buildChartDataBody(cid);
  const res = http.post(`${BASE_URL}/api/v1/chart/data`, body, {
    ...authHeaders(token),
    tags: { name: "chart_data" },
  });
  check(res, { "chart_data 200": (r) => r.status === 200 });
  sleep(0.2);
}
