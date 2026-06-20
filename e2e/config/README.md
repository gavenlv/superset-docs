# config/

E2E 测试全局配置。

## 文件

| 文件           | 职责                                                |
| -------------- | --------------------------------------------------- |
| `config.yaml`  | 默认配置（模式、浏览器、实例列表等）                |
| `settings.py`  | `Config` 数据类 + 从 yaml / env 构造 `TestConfig`   |

## 优先级

```
环境变量 (.env 或 shell)  >  config.yaml
```

## 自定义实例

修改 `config.yaml` 的 `instances` 列表，每个实例需要：

| 字段                 | 说明                                         |
| -------------------- | -------------------------------------------- |
| `name`               | 标识符（用于 fixture 与 Allure label）        |
| `version`            | 版本号（写入 Allure environment）            |
| `base_url`           | 浏览器访问入口                                |
| `compose_dir`        | 相对 `e2e/` 的 docker-compose 目录           |
| `postgres_container` | PostgreSQL 容器名（用于 `docker exec` 直查） |
| `redis_container`    | Redis 容器名（可选）                          |

## 环境变量

详见 [`../README.md`](../README.md#环境变量优先级最高)。
