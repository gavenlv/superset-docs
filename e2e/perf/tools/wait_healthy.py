"""等待 Superset 4.1 / 6.0 / 指定实例 /health 返回 200。

支持多环境（通过 E2E_ENV 切换）：

用法：
    # 默认 dev 环境
    python perf/tools/wait_healthy.py --versions 4.1,6.0
    # 切到 sit
    E2E_ENV=sit python perf/tools/wait_healthy.py --versions 6.0 --timeout 300
    # 显式传 env
    python perf/tools/wait_healthy.py --versions 6.0 --env sit
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

# 让 e2e 根目录可被 import
_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from config.settings import CONFIG, current_env, reload_config  # noqa: E402
from perf.common.config_loader import get_target_instance  # noqa: E402


def wait_one(version: str, timeout: int = 300) -> bool:
    inst = get_target_instance(version)
    base_url = inst["base_url"]
    deadline = time.time() + timeout
    print(f"[wait_healthy] {version} ({base_url}) env={CONFIG.env} ...", flush=True)
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=5.0)
            if r.status_code == 200:
                print(f"[wait_healthy] {version} OK ({base_url})", flush=True)
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    print(f"[wait_healthy] {version} TIMEOUT after {timeout}s", flush=True)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--versions", default="4.1,6.0", help="comma-separated versions to wait"
    )
    ap.add_argument("--timeout", type=int, default=300, help="seconds per version")
    ap.add_argument(
        "--env",
        default=None,
        help=f"environment ({' / '.join(['dev', 'sit', 'uat', 'prod'])})",
    )
    args = ap.parse_args()

    # 切换环境（如指定）
    if args.env:
        os.environ["E2E_ENV"] = args.env
        reload_config(args.env)
    else:
        print(f"[wait_healthy] active env = {current_env()}", flush=True)

    versions = [v.strip() for v in args.versions.split(",") if v.strip()]
    failed = []
    for v in versions:
        if not wait_one(v, args.timeout):
            failed.append(v)
    if failed:
        print(f"[wait_healthy] FAILED: {failed}", flush=True)
        return 1
    print("[wait_healthy] all healthy", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
