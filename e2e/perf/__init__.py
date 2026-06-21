"""Superset 性能测试套件。

- locust/  : Locust 主场景（4 角色 + 30 任务）
- k6/      : k6 高并发专项脚本（重点查询门禁）
- common/  : 跨框架通用工具（auth/metrics/thresholds/docker_metrics）
- baselines/ : 基线 JSON（git 跟踪）
- reports/ : 压测报告输出（gitignore）
- tools/   : 启动脚本和基线对比工具
- tests/   : 元测试（pytest 验证脚本/基线/schema）
"""
