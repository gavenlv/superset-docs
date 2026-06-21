"""Locust 主入口：组合 4 个角色（AdminOps / Analyst / Viewer / Embed）。

权重（与 PLAN.md 一致）：
- AdminOps 1
- Analyst 10
- Viewer 30  ⭐ 重点
- Embed 8

启动：
    locust -f perf/locust/locustfile.py --host http://localhost:18088

带参数：
    locust -f perf/locust/locustfile.py --host http://localhost:18088 \\
        --users 200 --spawn-rate 20 --run-time 10m --headless \\
        --csv=perf/reports/locust/run --html=perf/reports/locust/report.html
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 让 e2e 根目录可被 import（utils / config）
_E2E_ROOT = Path(__file__).resolve().parents[2]
if str(_E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(_E2E_ROOT))

from perf.common.config_loader import get_perf_config  # noqa: E402
from perf.locust.tasks.admin_ops import AdminOpsUser  # noqa: E402
from perf.locust.tasks.analyst import AnalystUser  # noqa: E402
from perf.locust.tasks.viewer import ViewerUser  # noqa: E402
from perf.locust.tasks.embed import EmbedUser  # noqa: E402


def _apply_config() -> None:
    """从环境变量 + config.yaml 应用 weight / target version。"""
    target_version = os.environ.get("PERF_TARGET_VERSION", "6.0")
    cfg = get_perf_config()
    rw = cfg.get("role_weights", {})

    classes = {
        "admin_ops": AdminOpsUser,
        "analyst": AnalystUser,
        "viewer": ViewerUser,
        "embed": EmbedUser,
    }
    for role, cls in classes.items():
        cls.superset_version = target_version
        cls.weight = rw.get(role, 1)


_apply_config()


