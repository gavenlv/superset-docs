# tests/health/

Superset Web / API 基础健康检查，是 `smoke` marker 的核心子集。

## 用例

| 测试                                | 标记            | 验证内容                                |
| ----------------------------------- | --------------- | --------------------------------------- |
| `test_health_endpoint`              | `health smoke`  | `GET /health` 返回 `200 OK`             |
| `test_login_api`                    | `health smoke`  | `POST /api/v1/security/login` 成功     |
| `test_login_page_loads`             | `health smoke`  | 登录页 UI 加载（兼容 4.1 SSR / 6.0 SPA） |

## 运行

```bash
# 仅 health
python run.py -m health

# 4.1 的 health
python run.py --instance 4.1 -m health
```

## 失败常见原因

- `health_endpoint` 失败：服务未启动或健康检查未通过
- `login_api` 失败：admin 凭据错误（检查 `EXAMPLES_DB_URI` 与 init 容器日志）
- `login_page_loads` 失败：通常是 `superset-init` 未完成（examples 未加载），前端 SPA 加载变慢
