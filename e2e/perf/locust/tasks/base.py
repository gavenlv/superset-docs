"""Locust SupersetUser 基类 + 共享的 TaskSet 基类。

- SupersetUser: 登录并预热 ID 缓存
- BaseBehavior: TaskSet 基类，提供 _timed_request / _get_dashboard_id 等 helper
"""
from __future__ import annotations

import random
import time
from typing import Any

from locust import HttpUser, task, between, events
from locust import TaskSet

from perf.common.auth import get_cached_token
from perf.common.metrics import MetricsCollector


# 全局 metrics 聚合（被各 user 共享）
GLOBAL_METRICS = MetricsCollector()


class BaseBehavior(TaskSet):
    """所有角色 Behavior 的基类（TaskSet）。

    提供：
    - _timed_request(method, path, **): 走 locust client + 自动写入 GLOBAL_METRICS
    - _get_dashboard_id / _get_chart_id / _get_dataset_id: 从 user 预热缓存取 ID
    """

    def _timed_request(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        json: Any = None,
        params: Any = None,
    ) -> tuple[int, float]:
        """发请求并把指标写入 GLOBAL_METRICS。

        返回 (status_code, latency_ms)。
        """
        url = path
        start = time.perf_counter()
        status = 0
        success = False
        try:
            resp = self.client.request(
                method,
                url,
                json=json,
                params=params,
                name=name or f"{method} {path}",
            )
            status = resp.status_code
            success = 200 <= status < 400
        except Exception:  # noqa: BLE001
            success = False
        latency_ms = (time.perf_counter() - start) * 1000
        GLOBAL_METRICS.record(name or f"{method} {path}", latency_ms, success)
        return status, latency_ms

    def _get_dashboard_id(self) -> int | None:
        ids = getattr(self.user, "_dashboard_ids", []) or []
        if not ids:
            return None
        return random.choice(ids)

    def _get_chart_id(self) -> int | None:
        ids = getattr(self.user, "_chart_ids", []) or []
        if not ids:
            return None
        return random.choice(ids)

    def _get_dataset_id(self) -> int | None:
        ids = getattr(self.user, "_dataset_ids", []) or []
        if not ids:
            return None
        return random.choice(ids)


class SupersetUser(HttpUser):
    """所有 Locust 用户的基类。"""

    abstract = True
    wait_time = between(0.5, 2.0)

    # 由 locustfile 注入的版本（"4.1" / "6.0"）
    superset_version: str = "6.0"

    def on_start(self) -> None:
        """登录并初始化。"""
        token = get_cached_token(self.host)
        self.client.headers.update({"Authorization": f"Bearer {token}"})

        # 缓存常用 ID（dashboard / chart），避免每次都查
        self._dashboard_ids: list[int] = []
        self._chart_ids: list[int] = []
        self._dataset_ids: list[int] = []
        self._prime_ids()

    def _prime_ids(self) -> None:
        """拉一次列表，缓存 ID。失败不阻塞（用空列表继续）。"""
        for ep, attr in [
            ("/api/v1/dashboard/", "_dashboard_ids"),
            ("/api/v1/chart/", "_chart_ids"),
            ("/api/v1/dataset/", "_dataset_ids"),
        ]:
            try:
                r = self.client.get(
                    ep,
                    params={"q": '{"page":0,"page_size":50}'},
                    name=f"GET {ep}  (prime)",
                    catch_response=True,
                )
                if r.status_code == 200:
                    body = r.json()
                    result = body.get("result", [])
                    ids = [x["id"] for x in result if isinstance(x, dict) and "id" in x][:50]
                    setattr(self, attr, ids)
                    r.success()
            except Exception:  # noqa: BLE001
                pass

    # ---- 心率任务（每个 user 都跑）----
    @task(1)
    def health(self) -> None:
        # 心率不走 metrics（避免 baseline 噪声）
        self.client.get("/health", name="GET /health")


@events.test_stop.add_listener
def _on_test_stop(environment, **kwargs) -> None:  # noqa: ARG001
    """压测结束：把全局指标写到 reports。"""
    from pathlib import Path
    from perf.common.config_loader import get_perf_config
    from perf.common.report import render_summary, write_json_snapshot

    cfg = get_perf_config()
    reports_dir = Path(cfg.get("reports_dir", "perf/reports"))
    target_version = "6.0"  # 默认写 6.0；CI 可通过环境变量覆盖
    out_dir = reports_dir / "locust"
    write_json_snapshot(
        GLOBAL_METRICS.snapshot(),
        out_dir / f"current_{target_version}.json",
    )
    summary = render_summary(GLOBAL_METRICS.snapshot())
    (out_dir / f"summary_{target_version}.txt").write_text(
        summary, encoding="utf-8"
    )
    print("\n" + summary)

