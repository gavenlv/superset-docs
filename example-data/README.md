# example-data

Superset 官方示例数据集，由 4.1 / 6.0 两个版本共享，挂载到 init 容器后通过 `load_examples_init.py` 完全离线加载。

## 目录

- [包含文件](#包含文件)
- [数据源](#数据源)
- [挂载与加载机制](#挂载与加载机制)
- [4.1 vs 6.0 加载方式](#41-vs-60-加载方式)
- [新增数据集](#新增数据集)
- [License](#license)

## 包含文件

数据集来自 `apache-superset/examples-data` 仓库，原样拷贝：

| 文件                                       | 类型      | 行数（约） | 用途示例                                |
| ------------------------------------------ | --------- | ---------- | --------------------------------------- |
| `airports.csv.gz`                          | CSV       | 28k        | 地图（美国机场）                        |
| `bart-lines.json.gz`                       | GeoJSON   | —          | 地图叠加（湾区 BART）                   |
| `birth_france_data_for_country_map.csv`    | CSV       | —          | 国家地图（法国出生数据）                |
| `birth_names.csv` / `birth_names.json.gz`  | CSV/JSON  | 200k       | 时间序列 / 桑基图（婴儿姓名）           |
| `birth_names2.json.gz`                     | JSON      | —          | 多格式时间序列                          |
| `countries.json.gz`                        | GeoJSON   | —          | 国家边界                                |
| `energy.json.gz`                           | JSON      | —          | 多系列 / 雷达图（能源结构）             |
| `flight_data.csv.gz`                       | CSV       | —          | 航班热力图 / 日历图                     |
| `long_lat.csv`                             | CSV       | —          | 散点图（经纬度测试）                    |
| `multiformat_time_series.json.gz`          | JSON      | —          | 多格式时间序列                          |
| `paris_iris.json.gz`                       | GeoJSON   | —          | 地理（巴黎街区）                        |
| `random_time_series.json.gz`               | JSON      | —          | 随机时间序列                            |
| `san_francisco.csv.gz`                     | CSV       | —          | 旧金山地理                              |
| `sf_population.json.gz`                    | JSON      | —          | 旧金山人口（多层级）                    |
| `tutorial_flights.csv`                     | CSV       | —          | 教程数据（航班）                        |
| `unicode_utf8_unixnl_test.csv`             | CSV       | —          | Unicode 编码测试                        |
| `datasets/examples/slack/*`                | CSV       | —          | Slack 多表（channels / messages 等）    |
| `datasets/examples/covid_vaccines.csv`     | CSV       | —          | COVID-19 疫苗数据                       |
| `datasets/examples/fcc_survey_2018.csv.gz` | CSV       | 200k       | FCC 调查                                |
| `datasets/examples/sales.csv`              | CSV       | —          | 销售数据（6.0 中图表 ID 修复涉及）       |
| `datasets/examples/unicode_test.csv`       | CSV       | —          | Unicode 边界测试                        |
| `datasets/examples/video_game_sales.csv`   | CSV       | 16k        | 视频游戏销量                            |

## 数据源

上游仓库：https://github.com/apache-superset/examples-data

本目录拷贝的是 `master` 分支快照，未自动同步。如需更新：

```bash
cd example-data
# 方式 1：整库同步（注意会覆盖本目录）
# git clone --depth=1 https://github.com/apache-superset/examples-data.git _upstream
# rsync -a --delete _upstream/ ./
# rm -rf _upstream

# 方式 2：手动 curl 单个文件
curl -L -o birth_names.csv \
  https://raw.githubusercontent.com/apache-superset/examples-data/master/birth_names.csv
```

## 挂载与加载机制

`docker-compose.yml` 中：

```yaml
services:
  superset-init:
    volumes:
      - ./superset_config.py:/app/superset_config.py:ro
      - ./pythonpath:/app/pythonpath:ro
      - ../example-data:/app/local_samples:ro  # 关键
```

环境变量：

```yaml
SUPERSET_LOCAL_SAMPLES_DIR: "/app/local_samples"
SUPERSET_EXAMPLES_BASE_URL: "https://raw.githubusercontent.com/apache-superset/examples-data/master/"
EXAMPLES_DB_URI: "postgresql+psycopg2://superset:superset@postgres:5432/superset"
```

init 容器中 [`load_examples_init.py`](../superset-4.1/pythonpath/load_examples_init.py) 的关键步骤：

1. 修复 `examples` 数据库的 `sqlalchemy_uri` 指向 PostgreSQL
2. 覆盖 `superset.examples.helpers.BASE_URL` 与 `get_example_url`，让 `superset load_examples` 优先从本地加载
3. 修复 `SqlaTable.schema`（从 SQLite 默认 `main` → PostgreSQL 默认 `public`）
4. 调用 `load_examples_run` 加载全部示例
5. 6.0 额外修复图表 `query_context.datasource.id` 不一致问题

## 4.1 vs 6.0 加载方式

| 维度         | 4.1                                    | 6.0                                            |
| ------------ | -------------------------------------- | ---------------------------------------------- |
| 协议         | `file://` URL                          | `http://localhost:18099/`（本地 HTTP 服务）    |
| 原因         | `get_example_url` 不做 URL 校验        | `marshmallow.fields.URL()` 强制 `http(s)://`   |
| 镜像要求     | 任意                                   | 必须 `user: root`（写 venv）                   |
| 图表修复     | 不需要                                 | 自动对齐 `query_context.datasource.id`         |

6.0 在 init 容器内启动 HTTP 服务（端口 18099）来"欺骗"校验器，详见 [`superset-6.0/README.md`](../superset-6.0/README.md#示例数据加载机制)。

## 新增数据集

如需增加自定义示例：

1. 把文件放到本目录根或 `datasets/examples/` 子目录
2. 在 [`../superset-4.1/pythonpath/load_examples_init.py`](../superset-4.1/pythonpath/load_examples_init.py) 中追加注册逻辑（参考现有 `slack/` 目录）
3. 重新 `docker compose down -v && up -d`

## License

数据遵循上游 Apache 2.0 许可（参见 [`NOTICE`](./NOTICE)）。其中部分英国数据基于 [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)。
