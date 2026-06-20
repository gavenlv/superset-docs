# Superset 6.0 配置文件（通过卷挂载到容器中）
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://superset:superset@postgres:5432/superset"
# 示例数据 URI：不设的话默认 sqlite，init/web 数据会写到 /app/superset_home/examples.db，
# 但 init 容器与 web 容器的 superset_home 互相独立，数据会丢
SQLALCHEMY_EXAMPLES_URI = "postgresql+psycopg2://superset:superset@postgres:5432/superset"
REDIS_HOST = "redis"
REDIS_PORT = 6379

# Celery broker 与 results 后端
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# 缓存配置
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_60_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
}
DATA_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_60_data_"}
FILTER_STATE_CACHE_CONFIG = {**CACHE_CONFIG, "CACHE_KEY_PREFIX": "superset_60_filter_"}

# 安全配置
SECRET_KEY = "superset-6.0-secret-key-please-change-in-production"
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = ["superset.views.core.log", "superset.charts.data.api.data"]

# 文件上传
UPLOAD_FOLDER = "/app/superset_home/uploads"
SQLLAB_CTAS_NO_LIMIT = True

# 6.0 特性
ENABLE_TEMPLATE_PROCESSING = True
TALISMAN_ENABLED = False
