"""验证 thresholds 判定逻辑（不依赖网络）。"""
from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.thresholds import compare, is_critical_endpoint  # noqa: E402


def _mock_baseline():
    """提供一个固定的基线用于阈值测试。"""
    return {
        "version": "6.0",
        "endpoints": {
            "GET /api/v1/dashboard/": {
                "count": 100,
                "failures": 0,
                "error_rate_pct": 0.0,
                "p50_ms": 100.0,
                "p95_ms": 200.0,
                "p99_ms": 400.0,
            },
            "POST /api/v1/chart/data": {
                "count": 100,
                "failures": 0,
                "error_rate_pct": 0.0,
                "p50_ms": 100.0,
                "p95_ms": 200.0,
                "p99_ms": 400.0,
            },
        },
    }


def _current(p95: float, err: float = 0.0) -> dict:
    return {
        "endpoints": {
            "GET /api/v1/dashboard/": {"p95_ms": p95, "error_rate_pct": err},
            "POST /api/v1/chart/data": {"p95_ms": p95, "error_rate_pct": err},
        }
    }


def test_critical_endpoint_match():
    assert is_critical_endpoint("GET /api/v1/dashboard/")
    assert is_critical_endpoint("GET /api/v1/dashboard/123")
    assert is_critical_endpoint("POST /api/v1/chart/data")
    assert not is_critical_endpoint("GET /api/v1/dataset/")


def test_critical_p95_within_threshold_passes():
    with patch("perf.common.thresholds.load_baseline", return_value=_mock_baseline()):
        # +10% < warn 15% → pass
        result = compare("6.0", _current(220), critical_only=True)
        assert result["passed"]
        assert result["critical_violations"] == []


def test_critical_p95_over_critical_threshold_fails():
    with patch("perf.common.thresholds.load_baseline", return_value=_mock_baseline()):
        # +25% > 15% → critical fail（_current 包含 2 个端点）
        result = compare("6.0", _current(250), critical_only=True)
        assert not result["passed"]
        assert len(result["critical_violations"]) == 2  # dashboard + chart/data


def test_critical_error_rate_fails():
    with patch("perf.common.thresholds.load_baseline", return_value=_mock_baseline()):
        # p95 没爆，但 error rate 0.8% > 0.5% → fail
        result = compare("6.0", _current(200, err=0.8), critical_only=True)
        assert not result["passed"]
