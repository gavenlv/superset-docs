"""LoginStorm：独立 locustfile，仅做登录 / CSRF / refresh。

用法：
    locust -f perf/locust/tasks/login_storm.py --host http://localhost:18088

CI 触发：手动 / 容量规划场景。
"""
from __future__ import annotations

import time

from locust import HttpUser, task, between

from perf.common.auth import login_client, admin_creds


class LoginStormUser(HttpUser):
    """只跑登录的高并发用户。"""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        # 不在 on_start 登录，让 task 里每次都新登录
        pass

    @task
    def login(self) -> None:
        creds = admin_creds()
        start = time.perf_counter()
        try:
            r = self.client.post(
                "/api/v1/security/login",
                json={
                    "username": creds["username"],
                    "password": creds["password"],
                    "provider": "db",
                    "refresh": True,
                },
                name="POST /api/v1/security/login  (storm)",
            )
            elapsed = (time.perf_counter() - start) * 1000
            if r.status_code == 200 and "access_token" in (r.json() or {}):
                self.environment.events.request_success.fire(
                    request_type="POST",
                    name="POST /api/v1/security/login  (storm)",
                    response_time=elapsed,
                    response_length=len(r.content),
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="POST",
                    name="POST /api/v1/security/login  (storm)",
                    response_time=elapsed,
                    response_length=len(r.content),
                    exception=Exception(f"status={r.status_code}"),
                )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter() - start) * 1000
            self.environment.events.request_failure.fire(
                request_type="POST",
                name="POST /api/v1/security/login  (storm)",
                response_time=elapsed,
                response_length=0,
                exception=exc,
            )
