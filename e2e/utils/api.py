"""测试中复用的 API helper：登录、CSRF、wrapper。"""
from __future__ import annotations

import json
import urllib.parse
from typing import Any

import httpx

from config.settings import CONFIG


def login_client(base_url: str) -> tuple[httpx.Client, str]:
    """登录并返回带 cookie 的 client + JWT。"""
    client = httpx.Client(base_url=base_url, timeout=15.0)
    r = client.post(
        "/api/v1/security/login",
        json={
            "username": CONFIG.admin_username,
            "password": CONFIG.admin_password,
            "provider": "db",
            "refresh": True,
        },
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    return client, token


def csrf_token(client: httpx.Client, token: str) -> str:
    """获取 CSRF token（写操作需要）。"""
    r = client.get(
        "/api/v1/security/csrf_token/",
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()["result"]


def auth_headers(token: str, *, csrf: str = "") -> dict[str, str]:
    """统一 header。csrf 为空时不加 X-CSRFToken。"""
    h = {"Authorization": f"Bearer {token}"}
    if csrf:
        h["X-CSRFToken"] = csrf
    return h


def write_headers(token: str) -> dict[str, str]:
    """CSRF + JWT 写操作 headers。"""
    return {"Authorization": f"Bearer {token}", "X-CSRFToken": "1"}


def unwrap(body: Any) -> Any:
    """Superset API 单对象返回：拆出对象本体。

    兼容以下格式：
    - 6.0 GET: `{"id": N, "result": {...}}` → 返回 result
    - 4.1 GET: `{"id": N, "result": {...}, ...}` → 返回 result
    - 6.0 GET 嵌套: `{"result": {"id": N, ...}}` (无顶层 id) → 返回 result
    - 4.1 CREATE: `{"data": {...}}` → 返回 data
    - list: `{"result": [list], "count": N}` → 返回 result 列表（调用方一般用 ['result']）
    """
    if not isinstance(body, dict):
        return body
    # 顶层同时有 result + id（4.1/6.0 旧 GET）→ 返回 result
    if "result" in body and "id" in body:
        return body["result"]
    # 顶层只有 result，且内层是 dict（id 在 result 内部）→ 返回 result
    if "result" in body and isinstance(body["result"], dict):
        return body["result"]
    # 顶层只有 result list → 返回 result
    if "result" in body:
        return body["result"]
    if "data" in body and isinstance(body["data"], dict):
        return body["data"]
    return body


def extract_id(body: Any) -> int | None:
    """从 create 返回中提取 id。"""
    if not isinstance(body, dict):
        return None
    if "id" in body:
        return body["id"]
    for key in ("result", "data"):
        if key in body and isinstance(body[key], dict) and "id" in body[key]:
            return body[key]["id"]
    return None


def page_q(page: int = 0, page_size: int = 100) -> str:
    """分页参数。"""
    return urllib.parse.quote(json.dumps({"page": page, "page_size": page_size}))


# Column / metric 字段的只读子集，PUT 时需要剔除
_READONLY_COLUMN_FIELDS = {
    "changed_on", "created_on", "changed_by", "created_by",
    "uuid", "id", "is_active", "type_generic",
}
_READONLY_METRIC_FIELDS = {
    "changed_on", "created_on", "changed_by", "created_by",
    "uuid", "id", "is_active",
}


def clean_columns(cols: list[dict]) -> list[dict]:
    """去掉 column payload 中的只读字段，方便 PUT。"""
    out = []
    for c in cols:
        cleaned = {k: v for k, v in c.items() if k not in _READONLY_COLUMN_FIELDS}
        # 旧 col 不要带 id（避免 unique 校验），但 col_name 留作标识
        cleaned.pop("id", None)
        out.append(cleaned)
    return out


def clean_metrics(metrics: list[dict]) -> list[dict]:
    """去掉 metric payload 中的只读字段。"""
    out = []
    for m in metrics:
        cleaned = {k: v for k, v in m.items() if k not in _READONLY_METRIC_FIELDS}
        cleaned.pop("id", None)
        out.append(cleaned)
    return out
