"""验证 baselines/*.json 字段完整。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_E2E_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_DIR = _E2E_ROOT / "perf" / "baselines"

REQUIRED_KEYS = {"version", "endpoints"}


@pytest.mark.parametrize("version", ["4.1", "6.0"])
def test_baseline_exists(version: str) -> None:
    safe = version.replace(".", "_")
    p = _BASELINE_DIR / f"v{safe}.json"
    assert p.exists(), f"missing baseline: {p}"


@pytest.mark.parametrize("version", ["4.1", "6.0"])
def test_baseline_schema(version: str) -> None:
    safe = version.replace(".", "_")
    p = _BASELINE_DIR / f"v{safe}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for k in REQUIRED_KEYS:
        assert k in data, f"missing key {k!r} in {p}"
    assert isinstance(data["endpoints"], dict)
    # 每个端点至少有 p95_ms
    for ep, vals in data["endpoints"].items():
        assert "p95_ms" in vals, f"endpoint {ep!r} missing p95_ms"


def test_critical_endpoints_present() -> None:
    """重点查询白名单对应的端点都在 6.0 基线里。"""
    p = _BASELINE_DIR / "v6_0.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    import re
    method_paths = set()
    for k in data["endpoints"].keys():
        if " " in k:
            m, path = k.split(" ", 1)
            # 标准化：去掉尾斜杠，便于跨版本匹配
            method_paths.add((m, path.rstrip("/")))
    # 重点白名单（method, path-without-trailing-slash）
    must_have = [
        ("GET", "/api/v1/dashboard/"),
        ("GET", "/api/v1/dashboard/{id}"),
        ("GET", "/api/v1/dashboard/{id}/charts"),
        ("GET", "/api/v1/dashboard/{id}/datasets"),
        ("GET", "/superset/dashboard/{id}/"),
        ("GET", "/api/v1/chart/"),
        ("GET", "/api/v1/chart/{id}"),
        ("POST", "/api/v1/chart/data"),
    ]
    for m, p_ in must_have:
        target = p_.rstrip("/")
        # 直接匹配
        if (m, target) in method_paths:
            continue
        # 模板 {xxx} 当作 [^/]+
        regex = re.escape(target).replace(r"\{[^}]+\}", r"[^/]+") + r"$"
        ok = any(re.match(regex, mp) for mm, mp in method_paths if mm == m)
        assert ok, f"critical endpoint {m} {p_} missing from baseline"

