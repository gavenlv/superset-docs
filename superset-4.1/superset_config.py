# Superset 4.1 配置文件（通过卷挂载到容器中）
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://superset:superset@postgres:5432/superset"
# 示例数据 URI：不设的话默认用 sqlite，init/web 数据会写到 /app/superset_home/examples.db，
# 但 init 容器与 web 容器的 superset_home 互相独立，数据会丢
SQLALCHEMY_EXAMPLES_URI = "postgresql+psycopg2://superset:superset@postgres:5432/superset"
REDIS_HOST = "redis"
REDIS_PORT = 6379

# 缓存与 Celery 结果后端
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_41_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
}
DATA_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_41_data_"}
FILTER_STATE_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_41_filter_"}

# 安全配置
SECRET_KEY = "superset-4.1-secret-key-please-change-in-production"
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.core.log", "superset.charts.data.api.data"]

# 文件上传
UPLOAD_FOLDER = "/app/superset_home/uploads"
SQLLAB_CTAS_NO_LIMIT = True

# 启用 Alerts / Reports 模块（需重启容器生效）
# 不启用时 /api/v1/alert 与 /api/v1/report 端点返回 404
ENABLE_ALERTS = True
