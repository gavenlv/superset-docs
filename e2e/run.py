"""E2E 测试运行入口。

用法:
    python run.py                                  # 复用现有服务，跑全部 smoke
    python run.py --mode cold                      # 冷启动
    python run.py --mode cold --browser firefox    # 冷启动 + firefox
    python run.py -k auth                          # 只跑 auth 标记
    python run.py --allure                         # 跑完生成 allure report
    python run.py --instance 4.1                  # 只跑 4.1
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 让根目录可被 import
E2E_ROOT = Path(__file__).resolve().parent
if str(E2E_ROOT) not in sys.path:
    sys.path.insert(0, str(E2E_ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Superset E2E runner")
    p.add_argument("--mode", choices=["cold", "reuse"], default="reuse",
                   help="cold=冷启动; reuse=复用现有服务（默认）")
    p.add_argument("--browser", choices=["chromium", "firefox", "webkit"],
                   default="chromium")
    p.add_argument("--headed", action="store_true", help="有头模式（默认 headless）")
    p.add_argument("--instance", choices=["4.1", "6.0", "all"], default="all")
    p.add_argument("-k", "--keyword", help="传给 pytest -k 过滤用例")
    p.add_argument("-m", "--marker", help="只跑指定 marker，例如 smoke")
    p.add_argument("--reruns", type=int, default=2)
    p.add_argument("--timeout", type=int, default=120, help="单用例超时（秒）")
    p.add_argument("--no-cleanup", action="store_true",
                   help="cold 模式下测试结束后不清理容器")
    p.add_argument("--allure", action="store_true", help="跑完后生成 allure HTML 报告")
    p.add_argument("--install-browsers", action="store_true",
                   help="先安装 playwright 浏览器再跑")
    p.add_argument("--no-deps", action="store_true",
                   help="跳过 pip install -r requirements.txt")
    p.add_argument("--pytest-args", nargs=argparse.REMAINDER,
                   help="透传给 pytest 的额外参数")
    return p.parse_args()


def ensure_python_deps() -> None:
    print(">> ensuring python deps ...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
        cwd=str(E2E_ROOT),
        check=True,
    )


def ensure_browsers() -> None:
    print(">> installing playwright browsers ...")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=str(E2E_ROOT),
        check=True,
    )


def build_pytest_cmd(args: argparse.Namespace) -> list[str]:
    cmd: list[str] = [sys.executable, "-m", "pytest"]
    if args.keyword:
        cmd += ["-k", args.keyword]
    if args.marker:
        cmd += ["-m", args.marker]
    # 选择 instance
    if args.instance != "all":
        # 用 -k 过滤
        existing_k = None
        if args.keyword:
            existing_k = args.keyword
        k = f'superset_instance and "{args.instance}" in {args.instance}'
        cmd += ["-k", k if not existing_k else f"({existing_k}) and {k}"]
    # 重试 / 超时（覆盖 config 默认）
    cmd += [f"--reruns={args.reruns}", "--reruns-delay=3", f"--timeout={args.timeout}"]
    if args.pytest_args:
        cmd += list(args.pytest_args)
    return cmd


def generate_allure_report() -> int:
    results_dir = E2E_ROOT / "reports" / "allure-results"
    report_dir = E2E_ROOT / "reports" / "allure-report"
    if not results_dir.exists() or not any(results_dir.iterdir()):
        print("!! no allure-results found, skip report generation")
        return 1
    print(">> generating allure HTML report ...")
    if report_dir.exists():
        shutil.rmtree(report_dir)
    # 优先用 allure CLI，没有则尝试 npx
    if shutil.which("allure"):
        return subprocess.call(
            ["allure", "generate", str(results_dir), "-o", str(report_dir), "--clean"]
        )
    print("!! allure CLI not found in PATH; install via: npm i -g allure-commandline")
    return 1


def main() -> int:
    args = parse_args()
    # 注入环境变量
    os.environ["E2E_MODE"] = args.mode
    os.environ["E2E_BROWSER"] = args.browser
    os.environ["E2E_HEADLESS"] = "0" if args.headed else "1"
    os.environ["E2E_CLEANUP"] = "0" if args.no_cleanup else "1"
    os.environ["E2E_RERUNS"] = str(args.reruns)

    if not args.no_deps:
        ensure_python_deps()
    if args.install_browsers:
        ensure_browsers()

    cmd = build_pytest_cmd(args)
    print(">> running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(E2E_ROOT))
    rc = proc.returncode

    if args.allure:
        generate_allure_report()
    return rc


if __name__ == "__main__":
    sys.exit(main())
