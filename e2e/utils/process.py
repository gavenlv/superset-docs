"""工具函数集合。"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 600,
    check: bool = True,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """运行子进程并打印日志。"""
    logger.info("$ %s (cwd=%s)", " ".join(cmd), cwd or ".")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    if proc.stdout:
        logger.debug("stdout: %s", proc.stdout[-2000:])
    if proc.stderr:
        logger.debug("stderr: %s", proc.stderr[-2000:])
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
        )
    return proc


def wait_for_http_ok(
    url: str,
    *,
    timeout: float = 300.0,
    interval: float = 2.0,
    expected_status: int = 200,
    session=None,
) -> float:
    """轮询 HTTP URL 直到返回预期状态码或超时。返回等待秒数。"""
    import httpx

    deadline = time.time() + timeout
    last_err: Exception | None = None
    sess = session or httpx.Client(timeout=10.0, follow_redirects=True)
    start = time.time()
    while time.time() < deadline:
        try:
            r = sess.get(url)
            if r.status_code == expected_status:
                logger.info("HTTP %s -> %d (took %.1fs)", url, r.status_code, time.time() - start)
                return time.time() - start
            logger.debug("HTTP %s -> %d, retrying", url, r.status_code)
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.debug("HTTP %s err: %s, retrying", url, e)
        time.sleep(interval)
    raise TimeoutError(
        f"HTTP {url} did not return {expected_status} within {timeout}s. Last err: {last_err}"
    )


def get_container_state(container: str) -> str:
    """获取 docker 容器状态。返回 'running' / 'exited' / 'not found' 等。"""
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", container],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return "not found"
    return proc.stdout.strip()


def filter_containers(containers: Iterable[str], state: str = "running") -> list[str]:
    """过滤出指定状态的容器。"""
    out = []
    for c in containers:
        if get_container_state(c) == state:
            out.append(c)
    return out
