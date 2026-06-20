"""各子目录的 conftest.py 入口：暴露 Playwright fixtures。"""
# 把 fixtures 文件显式 re-import，让 pytest 能发现
from fixtures.playwright_fixtures import (  # noqa: F401
    browser,
    context,
    logged_in_page,
    page,
    playwright,
)
