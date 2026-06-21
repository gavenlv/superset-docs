"""Locust 任务模块。

- base       : SupersetUser 基类（登录、CSRF、端点 ID 缓存）
- admin_ops  : AdminOps 角色（写路径 CRUD）
- analyst    : Analyst 角色（Edit Explore / chart CRUD / SQL Lab）
- viewer     : Viewer 角色（**重点**：dashboard / chart 读路径）
- embed      : Embed 角色（嵌入式访问）
- login_storm: 独立 locustfile（登录风暴）
"""
