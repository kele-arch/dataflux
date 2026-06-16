# Dataflux 项目工程文档

> 本文档详细描述了 dataflux 项目中**每一个文件**的作用、功能、核心逻辑和调用关系，供其他模型学习理解整个工程。

---

## 一、项目概览

**项目名称：** dataflux（数据采集平台 / 数据中台）

**技术栈：**

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.12 ~ 3.13 | — |
| Web 框架 | FastAPI | 异步路由、依赖注入、自动 OpenAPI 文档 |
| ASGI 服务器 | Uvicorn | 生产级异步服务器 |
| 主数据库 | PostgreSQL 15 | 元数据 + 采集结果双库架构 |
| ORM | SQLAlchemy 2.0+ | 声明式基类，Mapped 类型注解 |
| 数据库迁移 | Alembic | 自动生成迁移脚本 |
| 数据校验 | Pydantic v2 + pydantic-settings | 请求/响应模型校验 + 自动加载 .env |
| 任务队列 | ARQ (asyncio-redis-queue) | 基于 Redis 的异步后台任务队列 |
| 定时调度 | APScheduler 3.x (AsyncIOScheduler) | Cron 定时触发器 |
| 缓存/分布式锁 | Redis 7.x | 任务排他锁、控制信号、水位线暂存 |
| 时序监控 | InfluxDB 3.x | HTTP API (/api/v3)，Line Protocol 写入 |
| 认证 | python-jose (JWT) + passlib | HS256 签名 + pbkdf2_sha256 密码哈希 |
| 加密 | PyCryptodome (AES CBC) | 请求/响应可选加密 |
| 日志 | Loguru | 双 sink（控制台 + 文件轮转） |
| 打包 | PyInstaller | 生成独立 .exe |
| 包管理 | uv | 快速依赖解析和锁文件 |

**架构模式：** 分层架构（API → Service → CRUD → Models → DB），双数据库（元数据库 `engine` + 采集落地库 `collected_engine`）。

**双引擎架构：**

| 引擎类型 | 运行时 | 技术 | 适用场景 |
|----------|--------|------|----------|
| 批处理引擎 | ARQ Worker 独立子进程 | `max_jobs=3`, 7200s 超时 | MySQL/PG/Oracle/DM/SQLServer/SQLite/MongoDB/FTP/API/SNMP/Socket |
| 流处理引擎 | FastAPI 主进程内 asyncio.Task | AIOKafkaConsumer | Kafka 常驻消费 |

**启动方式：** `python -m app.main`（自动拉起 ARQ Worker 子进程 + 所有启用的 Kafka Consumer）

---

## 二、完整目录树

```
E:\AAA-project\dataflux\
├── .env                              # 环境变量配置文件
├── .gitignore                        # Git 忽略规则
├── alembic.ini                       # Alembic 数据库迁移配置
├── CLAUDE.md                         # LLM 编码行为准则
├── pyproject.toml                    # Python 项目元数据和依赖声明
├── README.md                         # 项目说明文档（中文）
├── uv.lock                           # uv 包管理器锁文件
│
├── alembic/                          # 数据库迁移脚本目录
│   ├── env.py                        # Alembic 环境配置
│   ├── README                        # Alembic 默认说明
│   └── script.py.mako                # 迁移脚本 Mako 模板
│
├── app/                              # 主应用包
│   ├── __init__.py                   # 包标记
│   ├── main.py                       # 应用入口（FastAPI 工厂 + lifespan + ARQ Worker 子进程）
│   ├── worker.py                     # ARQ Worker 后台任务执行模块
│   ├── exceptions.py                 # 自定义异常类
│   │
│   ├── api/                          # API 路由层
│   │   └── v1/
│   │       ├── __init__.py           # v1 路由器注册（6 个子路由）
│   │       ├── datasource.py         # 数据源管理 API
│   │       ├── tsync.py              # 同步任务管理 API + Kafka 专属接口
│   │       ├── tasklog.py            # 任务执行日志 API
│   │       ├── exec_log.py           # 表级同步日志 API
│   │       ├── monitor.py            # InfluxDB 监控查询 API
│   │       └── explorer.py           # 数据探索 API（通用表查询）
│   │
│   ├── com/                          # 公共工具 / 装饰器
│   │   ├── __init__.py               # 包标记
│   │   ├── decorators.py             # retry_request + measure_time 装饰器
│   │   └── tools.py                  # 占位文件
│   │
│   ├── core/                         # 核心基础设施
│   │   ├── __init__.py               # 导出 logger、project_rootpath、hostname
│   │   ├── config.py                 # 配置管理（pydantic-settings）
│   │   ├── log.py                    # Loguru 日志配置
│   │   ├── logger_route.py           # 全局操作日志拦截器
│   │   ├── redis.py                  # 异步 Redis 连接管理
│   │   ├── arq_pool.py               # ARQ Redis 连接池管理
│   │   ├── influx_client.py          # InfluxDB 3.x HTTP 客户端
│   │   ├── mongo.py                  # MongoDB 异步连接管理（Motor）
│   │   ├── license.py                # 许可验证模块（Ed25519 签名）
│   │   └── security.py               # 密码哈希 + JWT 令牌生成
│   │
│   ├── crud/                         # CRUD 操作层
│   │   ├── __init__.py               # 包标记
│   │   ├── crud_datasource.py        # 数据源 CRUD
│   │   ├── crud_tsync.py             # 同步任务 CRUD（含仪表盘统计、run_status 判定）
│   │   ├── crud_tasklog.py           # 任务日志 CRUD
│   │   └── crud_exec_log.py          # 表级执行日志 CRUD
│   │
│   ├── db/                           # 数据库层
│   │   ├── __init__.py               # 包标记
│   │   ├── base.py                   # SQLAlchemy 声明式基类
│   │   └── session.py                # 双数据库引擎 + 会话工厂 + 依赖注入
│   │
│   ├── middleware/                    # 自定义中间件
│   │   └── __init__.py               # 中间件注册函数（当前为空）
│   │
│   ├── models/                       # SQLAlchemy ORM 模型
│   │   ├── __init__.py               # 包标记
│   │   ├── bashModel.py              # BaseModelMixin（UUID 主键 + 审计字段）
│   │   ├── dataSourceModel.py        # 数据源配置表
│   │   ├── collectTaskModel.py       # 采集任务定义表（50+ 字段）
│   │   ├── taskLogModel.py           # 任务日志 + 表级执行日志 + FTP 文件记录
│   │   ├── collectRecordModel.py     # 异构原始数据落地表
│   │   └── otherModel.py             # 系统操作日志表
│   │
│   ├── schemas/                      # Pydantic 数据模式
│   │   ├── base.py                   # 请求体自动解密基类
│   │   ├── response.py               # 统一响应模型（支持加密）
│   │   ├── datasource.py             # 数据源 Schema
│   │   ├── tsync.py                  # 同步任务 Schema（DBSyncReq 80+ 字段）
│   │   ├── tasklog.py                # 任务日志 Schema
│   │   ├── sync_execution_log.py     # 表级日志 Schema
│   │   ├── explorer.py               # 数据探索 Schema
│   │   └── collectors.py             # Kafka Producer Schema
│   │
│   ├── services/                     # 业务逻辑层
│   │   ├── __init__.py               # 包标记
│   │   ├── engine_factory.py         # 同步引擎工厂（7 种引擎路由）
│   │   ├── sync_service.py           # 异构关系型数据库同步引擎（DatabaseSyncEngine）
│   │   ├── mongo_sync_engine.py      # MongoDB 抽取引擎
│   │   ├── api_sync_engine.py        # HTTP API 采集引擎
│   │   ├── ftp_sync_engine.py        # FTP/SFTP 文件采集引擎
│   │   ├── snmp_sync_engine.py       # SNMP 采集引擎
│   │   ├── socket_sync_engine.py     # Socket 采集引擎
│   │   ├── kafka_sync_engine.py      # Kafka 常驻消费引擎
│   │   ├── kafka_manager.py          # Kafka Consumer 生命周期管理器
│   │   ├── scheduler_service.py      # APScheduler 定时调度服务
│   │   ├── task_control.py           # Redis 任务控制（暂停/取消/水位线）
│   │   ├── file_client_factory.py    # 多协议文件客户端工厂（FTP/FTPS/SFTP/SDTP）
│   │   └── dialects/                 # 数据库方言特化处理器
│   │       ├── __init__.py           # get_dialect_handler() 路由
│   │       ├── base.py               # 方言基类
│   │       ├── mysql.py              # MySQL 方言
│   │       ├── postgres.py           # PostgreSQL 方言
│   │       ├── dm.py                 # 达梦 DM 方言
│   │       ├── oracle_dialect.py     # Oracle 方言
│   │       ├── sqlserver_dialect.py  # SQL Server 方言
│   │       └── sqlite_dialect.py     # SQLite 方言
│   │
│   ├── utils/                        # 工具模块
│   │   ├── __init__.py               # 包标记
│   │   ├── encryptDecrypt.py         # AES CBC 加密/解密
│   │   ├── sorter.py                 # 排序算法实现
│   │   ├── db_helper.py              # 数据库 URL 构建 + MongoDB 集合列表
│   │   └── cron_helper.py            # Cron 表达式生成器
│   │
│   └── collectors/                   # Kafka Producer 工具
│       ├── __init__.py               # 包标记
│       ├── base.py                   # 采集器基类
│       └── kafka_producer.py         # Kafka Producer 封装
│
├── docs/                             # 文档目录
│   ├── API_FRONTEND.md               # 接口对接文档（前端视角）
│   ├── DATABASE_TABLES.md            # 数据库表结构文档
│   └── PROJECT_DOCUMENTATION.md      # 本文档
│
├── build/                            # PyInstaller 构建产物
├── dist/                             # PyInstaller 分发文件
└── ftp_files/                        # FTP 下载文件本地存储目录
```

---

## 三、逐文件详细说明

---

### 3.1 根目录配置文件

---

#### 3.1.1 `.env`

**作用：** 环境变量配置文件，由 `pydantic-settings` 的 `Settings` 类自动加载。

| 变量名 | 示例值 | 说明 |
|--------|--------|------|
| `ENV` | `development` | 运行环境标识 |
| `DB_SCHEMA` | `public` | 元数据库 schema |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:654321@localhost:5432/dataflux` | 元数据库连接串 |
| `COLLECTED_DATABASE_URL` | `postgresql+psycopg2://postgres:654321@localhost:5432/dataflux_collected` | 采集落地库连接串 |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis 连接地址 |
| `SERVER_HOST` | `0.0.0.0` | 服务监听地址 |
| `SERVER_PORT` | `8028` | 服务监听端口 |
| `LOG_LEVEL` | `info` | 日志级别 |
| `SECRET_KEY` | 50位随机字符串 | JWT 签名密钥 |
| `ALGORITHM` | `HS256` | JWT 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT 过期时间（分钟） |
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB 连接 |
| `MONGO_DB_NAME` | `dataflux` | MongoDB 默认库名 |
| `INFLUX_URL` | `http://127.0.0.1:8181` | InfluxDB 3.x 地址 |
| `INFLUX_TOKEN` | API Token | InfluxDB 认证令牌 |
| `INFLUX_DB` | `testdb` | InfluxDB 数据库名 |
| `ENABLE_DB_CHECK` | `False` | 启动时严格校验数据库 |
| `ENABLE_ENCRYPT` | `False` | AES 加密开关 |
| `ENABLE_TOKEN` | `False` | JWT Token 验证开关 |
| `ENABLE_LICENSE` | `True` | 许可验证开关 |
| `BATCH_SIZE` | `10` | 批处理大小 |
| `MONGO_BATCH_SIZE` | `100` | MongoDB 批处理大小 |
| `TIMEZONE` | `Asia/Shanghai` | 调度器时区 |
| `FTP_LOCAL_SAVE_DIR` | `ftp_files` | FTP 文件本地存储根目录 |
| `DB_POOL_SIZE` | `10` | 数据库连接池基础连接数 |
| `DB_MAX_OVERFLOW` | `20` | 连接池最大溢出数 |
| `DB_POOL_TIMEOUT` | `30` | 获取连接超时（秒） |
| `DB_POOL_RECYCLE` | `1800` | 连接回收时间（秒） |
| `DB_POOL_PRE_PING` | `True` | 使用前预检连接 |

---

#### 3.1.3 `pyproject.toml`

**作用：** Python 项目元数据和依赖声明。

**核心依赖及用途：**

| 依赖包 | 用途 |
|--------|------|
| `fastapi` | Web 框架 |
| `uvicorn[standard]` | ASGI 服务器 |
| `sqlalchemy>=2.0.18` | ORM 框架 |
| `python-dotenv` | 加载 .env |
| `pymysql` | MySQL 驱动 |
| `python-multipart` | 表单/文件上传 |
| `loguru` | 日志框架 |
| `pydantic-settings` | 配置管理 |
| `alembic` | 数据库迁移 |
| `psycopg2-binary` | PostgreSQL 驱动 |
| `python-jose[cryptography]` | JWT |
| `passlib[bcrypt]` | 密码哈希 |
| `confluent-kafka` | Kafka Producer |
| `pycryptodome` | AES 加密 |
| `redis==7.2.1` | Redis 客户端 |
| `pymssql` | SQL Server 驱动 |
| `arq` | 异步任务队列 |
| `apscheduler` | 定时调度 |
| `pymupdf` / `pymupdf4llm` | PDF 处理 |
| `pyinstaller` | 打包 exe |
| `pymongo` / `motor` | MongoDB 同步/异步驱动 |
| `python-dateutil` | 时间解析 |
| `dmPython` / `dmsqlalchemy` | 达梦 DM 驱动 |
| `pyyaml` | YAML 解析 |
| `requests` / `httpx` | HTTP 客户端 |
| `openpyxl` | Excel 解析 |
| `paramiko` | SFTP 传输 |
| `pysnmp` / `snmpsim` / `pysmi` / `ply` | SNMP 采集 |
| `aiokafka` | Kafka 异步 Consumer |
| `oracledb` | Oracle 驱动 |

---

### 3.2 应用入口

---

#### 3.2.1 `app/main.py`

**作用：** 整个应用的入口，包含 FastAPI 工厂函数、lifespan 生命周期管理、ARQ Worker 子进程启动。

**核心组件：**

##### `start_all_kafka_tasks()` — Kafka 自动拉起函数

系统启动时，JOIN 查询 `sys_collect_task LEFT JOIN sys_data_source`，找到所有 `DataSource.type="kafka"` 且 `CollectTask.status=1` 的任务，自动调用 `kafka_manager.start()` 拉起常驻 Consumer。

##### `lifespan(app: FastAPI)` — 异步上下文管理器

**启动阶段（yield 之前）：**

1. **许可验证** — 如果 `ENABLE_LICENSE=True`，调用 `check_license()` 验证 Ed25519 签名许可文件
2. **关系型数据库连接测试** — `SELECT 1`，开发环境自动 `init_db()` 建表
3. **僵尸日志清理** — 将系统重启前残留的 `pending`/`running` 状态日志标记为 `failed`
4. **Redis 连接** — `init_redis()` 异步连接
5. **MongoDB 连接** — `init_mongo()`（Motor 异步客户端）
6. **ARQ 队列池** — `init_arq_pool()`
7. **InfluxDB 连接** — `init_influx()` 连通性检测
8. **APScheduler 启动** — `scheduler.start()` + `refresh_scheduler_jobs()`
9. **Kafka 任务自动拉起** — `start_all_kafka_tasks()`

**关闭阶段（yield 之后）：**

1. 停止所有 Kafka Consumer — `kafka_manager.stop_all()`
2. 关闭调度器 — `scheduler.shutdown()`
3. 关闭 ARQ 池 — `close_arq_pool()`
4. 关闭 Redis — `close_redis()`
5. 关闭 MongoDB — `close_mongo()`（5 秒超时）
6. 关闭 InfluxDB — `close_influx()`

##### `create_app()` — FastAPI 工厂函数

1. 创建 FastAPI 实例，标题"数据采集平台"，版本 "1.0"
2. 注册 CORS 中间件（全开放）
3. 挂载静态文件目录 `/static`
4. 自定义 Swagger UI 和 ReDoc 路由
5. 挂载 v1 路由器到 `/api/v1`

##### `__main__` 入口

```python
# 1. multiprocessing.freeze_support() — 支持 PyInstaller 打包
# 2. 启动 ARQ Worker 子进程 (multiprocessing.Process, daemon=True)
# 3. 注册 atexit 清理函数
# 4. uvicorn.run(app) — 启动主服务
```

---

#### 3.2.2 `app/worker.py`

**作用：** ARQ Worker 后台任务执行模块。定义 `run_sync_job()` 函数和 `WorkerSettings` 配置。

**核心函数 `run_sync_job(ctx, task_id)`：**

```
1. 获取 Redis 分布式锁 (sync_task_lock:{task_id}, nx=True, ex=7200)
   └─ 锁已存在 → 防抖丢弃
2. 打开数据库连接，查询 CollectTask + DataSource
3. 组装 DBSyncReq（聚合 task 和 source 的所有字段）
4. 查找 /run 接口预创建的 pending TaskLog → 更新为 running
5. 线程池中执行: EngineFactory.create(req).main()
6. 处理结果:
   ├─ paused/cancelled → 更新 TaskLog 状态，提前返回
   └─ success → 更新 TaskLog + 回写水位线 + 创建 SyncExecutionLog 记录
7. finally: 释放分布式锁
```

**`WorkerSettings` 配置：**

| 配置 | 值 | 说明 |
|------|-----|------|
| `functions` | `[run_sync_job]` | 注册的任务函数 |
| `max_jobs` | `3` | 最大并发任务数 |
| `job_timeout` | `7200` | 任务硬超时 2 小时 |
| `redis_settings` | 解析自 `REDIS_URL` | ARQ 的 Redis 连接 |

---

#### 3.2.3 `app/exceptions.py`

**作用：** 自定义异常类，用于在任务执行过程中清晰区分不同的中断场景。

| 异常类 | 触发场景 | 行为 |
|--------|----------|------|
| `TaskPausedException` | 用户点击暂停 | 保存水位线到 Redis，Worker 更新日志为 `paused` |
| `TaskCancelledException` | 用户点击取消 | 不保存水位线，Worker 更新日志为 `cancelled` |

---

### 3.3 核心层 (`app/core/`)

---

#### 3.3.1 `app/core/__init__.py`

导出三个全局变量：`logger`（Loguru 实例）、`project_rootpath`（项目根目录绝对路径）、`hostname`（主机名）。

---

#### 3.3.2 `app/core/config.py`

**`Settings` 类** — 继承 `pydantic_settings.BaseSettings`，30+ 配置项，所有字段都有默认值。`.env` 中的同名变量会自动覆盖。关键配置已在上文 3.1.1 列出。

---

#### 3.3.3 `app/core/log.py`

配置 Loguru 双 sink：
- **stderr：** INFO 级别，带颜色，格式 `时间 | 级别 | 文件:行号 - 消息`
- **文件 init.log：** DEBUG 级别，10MB 轮转，保留 30 天，zip 压缩

---

#### 3.3.4 `app/core/redis.py`

管理**异步** Redis 连接的全局单例。提供 `init_redis()`、`close_redis()`、`get_redis()` 三个函数。使用 `redis.asyncio` 模块。

> **与 `task_control.py` 的区别：** 本模块的是异步客户端（`redis.asyncio`），由 FastAPI 主进程使用。`task_control.py` 使用的是**同步**客户端（`redis.Redis`），由引擎线程同步调用。

---

#### 3.3.5 `app/core/arq_pool.py`

ARQ 队列的 Redis 连接池管理。全局 `arq_pool` 实例，提供 `init_arq_pool()` 和 `close_arq_pool()`。用于 `/tsync/run` 等 API 向 Worker 下发任务（`arq_pool.enqueue_job()`）。

---

#### 3.3.6 `app/core/influx_client.py`

**`InfluxDBV3Client`** — InfluxDB 3.x 的 HTTP 客户端封装：

| 方法 | 功能 | 协议 |
|------|------|------|
| `write_line_protocol(lines)` | 写入 Line Protocol 格式数据 | POST `/api/v3/write_lp` |
| `query_sql(sql)` | 执行 SQL 查询，返回 `list[dict]` | POST `/api/v3/query_sql` |
| `ping()` | 连通性检测 | — |

全局单例 `_influx_client`，提供 `init_influx()`、`close_influx()`、`get_influx_client()`。

---

#### 3.3.7 `app/core/mongo.py`

MongoDB 异步连接管理，基于 Motor（`AsyncIOMotorClient`）。全局单例 `mongo_client`，提供 `init_mongo()`、`close_mongo()`。

---

#### 3.3.8 `app/core/license.py`

基于 Ed25519 非对称签名的许可验证模块。读取 `license.key` 文件（`payload.signature` 格式），验证：签名有效性 → 机器绑定（主板序列号/MAC）→ 有效期（支持 permanent 永久许可）。公钥硬编码在 `_EMBEDDED_PUBLIC_KEY` 中。

---

#### 3.3.9 `app/core/security.py`

密码哈希（pbkdf2_sha256）+ JWT 令牌生成（HS256 签名）。提供 `verify_password()`、`get_password_hash()`、`create_access_token()`。

---

### 3.4 数据库层 (`app/db/`)

---

#### 3.4.1 `app/db/base.py`

定义 `Base = declarative_base()`，所有 ORM 模型的根。

---

#### 3.4.2 `app/db/session.py`

**双引擎架构：**

| 引擎 | 连接的目标 | 用途 |
|------|-----------|------|
| `engine` | `DATABASE_URL` | 元数据库（sys_data_source, sys_collect_task, sys_task_log 等） |
| `collected_engine` | `COLLECTED_DATABASE_URL` | 采集落地库（所有同步引擎写入的目标） |

两者均配置了连接池（pool_size=10, max_overflow=20, recycle=1800, pre_ping=True）。

**会话工厂：**
- `SessionLocal` — 元数据库会话工厂
- `CollectedSessionLocal` — 采集库会话工厂
- `get_db()` — 元数据库 FastAPI 依赖注入
- `get_collected_db()` — 采集库 FastAPI 依赖注入
- `get_session()` — 非 FastAPI 场景的上下文管理器

**`init_db()`** — 在 `development` 模式自动 `create_all` 建表。

---

### 3.5 ORM 模型层 (`app/models/`)

---

#### 3.5.1 `app/models/bashModel.py`

**`BaseModelMixin`** — Mixin 类，提供通用字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(32) PK | 32 位 UUID hex，`generate_uuid()` 生成 |
| `create_time` | DateTime | 创建时间 |
| `update_time` | DateTime | 更新时间（onupdate 自动触发） |
| `create_by` | String(50) | 创建人 |
| `is_delete` | Integer | 软删除（0=正常, 1=删除） |

---

#### 3.5.2 `app/models/dataSourceModel.py`

**`DataSource`** — 表 `sys_data_source`。存储各类数据源连接信息。字段：`name`、`type`（11 种类型）、`host`、`port`、`db_name`、`username`、`password`、`config_json`（扩展配置）。

---

#### 3.5.3 `app/models/collectTaskModel.py`

**`CollectTask`** — 表 `sys_collect_task`。核心任务定义表，包含 **50+ 字段**：

| 分类 | 字段 |
|------|------|
| 基础 | `task_name`, `source_id`, `topic_or_table`, `status`, `remark` |
| 调度 | `schedule_type`, `schedule_value`, `schedule_cron` |
| 同步策略 | `sync_mode`, `collect_mode`, `incremental_column`, `last_watermark`, `custom_sql` |
| 表配置 | `sync_tables` (JSON), `table_mapping` (JSON) |
| 目标库 | `target_type`, `target_host`, `target_port`, `target_username`, `target_password`, `target_db_name` |
| FTP | `ftp_url`, `ftp_path`, `ftp_passive`, `file_parse`, `file_type` |
| API | `api_url`, `api_method`, `api_headers`, `api_body`, `api_extract_mode`, `api_data_path` |
| SNMP | `snmp_version`, `snmp_community`, `snmp_user`, `snmp_auth_key`, `snmp_priv_key`, `snmp_auth_protocol`, `snmp_priv_protocol`, `snmp_extract_mode`, `snmp_metric_oids`, `snmp_table_oids` |
| Socket | `socket_protocol`, `socket_command`, `socket_command_encoding`, `socket_timeout`, `socket_recv_size`, `socket_terminator`, `socket_response_format` |
| Kafka | `kafka_bootstrap_servers`, `kafka_topic`, `kafka_group_id`, `kafka_auto_offset_reset`, `kafka_batch_size`, `kafka_batch_timeout_ms`, `kafka_value_format` |

---

#### 3.5.4 `app/models/taskLogModel.py`

包含三个模型：

**`TaskLog`** — 表 `sys_task_log`。任务执行历史日志。字段：`task_id`、`task_name`（快照）、`status`（pending/running/success/failed/paused/cancelled）、`start_time`、`end_time`、`tables_synced`、`total_records`、`detail_json`（执行详情快照）、`error_msg`。

**`SyncExecutionLog`** — 表 `sync_execution_log`。每张表的同步执行记录（血缘映射流水）。字段：`log_id`（关联 TaskLog）、`task_id`、`source_table`、`target_table`、`sync_mode`、`collect_mode`、`records_count`、`cost_seconds`、`watermark`、`status`。

**`FtpFileRecord`** — 表 `ftp_file_record`。FTP 文件采集记录。字段：`task_id`、`remote_path`、`local_path`、`file_name`、`file_size`、`md5`、`file_type`、`is_parsed`、`parsed_rows`、`downloaded_at`。

---

#### 3.5.5 `app/models/collectRecordModel.py`

**`CollectRecord`** — 表 `sys_collect_record`。异构原始数据落地表（通用载体）。字段：`task_id`、`source_type`、`payload`（JSON — 完整数据载体）。

---

#### 3.5.6 `app/models/otherModel.py`

**`SysLog`** — 表 `sys_oper_log`。系统操作日志（不继承 BaseModelMixin，独立字段结构）。记录每次 API 请求的操作人、IP、参数、结果、状态。

---

### 3.6 Pydantic 数据模式 (`app/schemas/`)

---

#### 3.6.1 `app/schemas/base.py`

**`BaseDecryptReq`** — 使用 `@model_validator(mode='before')` 在数据校验之前自动 AES 解密请求体。通过 `settings.ENABLE_ENCRYPT` 控制开关。

---

#### 3.6.2 `app/schemas/response.py`

**`BaseResponse[T]`** — 统一 API 响应模型：`{code: int, msg: str, data: T}`。支持 `@model_serializer(mode='wrap')` 自动加密 `data` 字段。

---

#### 3.6.3 `app/schemas/datasource.py`

数据源 CRUD 所需的 Schema：`DataSourceBase`（11 种 Literal 类型）、`DataSourceCreateReq`、`DataSourceUpdateReq`、`DataSourceIdReq`、`DataSourcePageQueryReq`、`DataSourceOut`、`DataSourcePageOut`。

---

#### 3.6.4 `app/schemas/tsync.py`

同步任务核心 Schema，最重要的文件之一。

**`DBSyncReq`** — 数据同步请求体，包含 80+ 字段，覆盖全部 11 种数据源类型的所有参数。`db_type` 是 Literal 类型（含 sqlite）。`config_json` 用于传递 SQL Server 实例名、Oracle SID 等扩展参数。

**请求 Schema：** `TaskCreateReq`（50+ 字段）、`TaskUpdateReq`、`TaskIdReq`、`TaskStatusReq`、`TaskPageQueryReq`

**响应 Schema：** `TaskOut`（含 `run_status` 动态字段）、`TaskPageOut`、`DashboardOut`、`MonitorTrendReq`

---

#### 3.6.5 其他 Schema

| 文件 | 主要内容 |
|------|----------|
| `tasklog.py` | `LogPageQueryReq`, `TaskLogOut`, `TaskLogDetailOut`, `TaskLogPageOut` |
| `sync_execution_log.py` | `ExecLogQueryReq`, `ExecLogOut`, `ExecLogPageOut` |
| `explorer.py` | `TableListReq`, `TableColumnsReq`, `DynamicDataQueryReq`（filters + like_filters） |
| `collectors.py` | Kafka Producer 相关请求体 |

---

### 3.7 API 路由层 (`app/api/v1/`)

---

#### 3.7.1 `app/api/v1/__init__.py`

注册 6 个子路由：

```python
api_router.include_router(tsync_router)        # /tsync
api_router.include_router(datasource_router)    # /datasource
api_router.include_router(tasklog_router)       # /tasklog
api_router.include_router(exec_log_router)      # /execlog
api_router.include_router(monitor_router)       # /monitor
api_router.include_router(explorer_router)      # /explorer
```

---

#### 3.7.2 `app/api/v1/datasource.py`

**数据源管理** (`/datasource`)，7 个接口：

| 接口 | 功能 |
|------|------|
| `POST /test_connect` | 测试连接（按 type 分支：MongoDB / FTP / 通用关系型 / API/SNMP/Socket/Kafka 直接返回） |
| `POST /add` | 新增数据源 |
| `POST /update` | 修改数据源 |
| `POST /delete` | 删除数据源 |
| `POST /list` | 分页列表（支持 name 模糊、type 过滤、排序） |
| `POST /tables` | 获取表/集合列表（SQL 用 inspect，Mongo 用 list_collection_names） |
| `POST /tables/detail` | 获取表结构详情（含注释） |

---

#### 3.7.3 `app/api/v1/tsync.py`

**同步任务管理** (`/tsync`)，14 个接口：

| 接口 | 功能 | 关键逻辑 |
|------|------|----------|
| `POST /database` | 直连同库（不走任务系统） | 同步调用 sync_database_architecture_and_data |
| `POST /list` | 任务列表 | 含 run_status 动态判定（查 Redis 锁 + 最新 TaskLog） |
| `POST /add` | 新增任务 | 翻译 Cron 表达式 → 刷新调度器 |
| `POST /update` | 修改任务 | 同 add |
| `POST /delete` | 删除任务 | Kafka 任务先停 Consumer 再删 |
| `POST /change_status` | 启停切换 | Kafka 停用时强杀 Consumer |
| `POST /run` | 手动执行 | Redis 防抖 → 清理僵尸日志 → 创建 pending 占坑 → ARQ 入队 |
| `POST /pause` | 暂停 | 写 Redis `task_control:{id}` = paused |
| `POST /cancel` | 取消 | 写 Redis = cancelled |
| `POST /resume` | 恢复 | 打捞 Redis 水位线 → 回写数据库 → ARQ 自动入队 |
| `POST /clean` | 解锁卡死 | 删 Redis 锁 + 控制信号 + 僵尸日志 |
| `POST /detail` | 任务详情 | — |
| `POST /dashboard` | 仪表盘统计 | 总数/启用数/今日记录/成功率 |
| `POST /kafka/start` | 启动 Kafka Consumer | — |
| `POST /kafka/stop` | 停止 Kafka Consumer | — |
| `POST /kafka/status` | 查询 Kafka Consumer 状态 | — |
| `POST /monitor/trend` | Kafka 消费监控时序 | 从 InfluxDB 查询 consumed + elapsed_ms |

---

#### 3.7.4-3.7.6 其他路由

| 文件 | 路由前缀 | 接口 |
|------|----------|------|
| `tasklog.py` | `/tasklog` | `POST /task-list`（分页+多条件过滤）、`POST /detail`（支持 log_id 或 task_id 查询） |
| `exec_log.py` | `/execlog` | `POST /list`（按 task_id / log_id / target_table / status 过滤） |
| `monitor.py` | `/monitor` | `POST /stats`（24h 统计卡片）、`POST /trend`（耗时趋势图）、`POST /logs`（明细日志）、`POST /series/query`（动态降采样时序查询） |
| `explorer.py` | `/explorer` | `POST /tables/list`（表名搜索）、`POST /tables/columns`（表结构详情）、`POST /tables/data`（通用分页+动态条件查询） |

---

### 3.8 业务逻辑层 (`app/services/`)

---

#### 3.8.1 `app/services/engine_factory.py`

**`EngineFactory.create(req: DBSyncReq)`** — 根据 `req.db_type` 路由到对应的同步引擎：

| db_type | 引擎类 |
|---------|--------|
| `mongodb` | `MongoSyncEngine` |
| `ftp` | `FtpSyncEngine` |
| `api` | `ApiSyncEngine` |
| `snmp` | `SnmpSyncEngine` |
| `socket` | `SocketSyncEngine` |
| `mysql`, `postgresql`, `dm`, `oracle`, `sqlserver`, `sqlite` | `DatabaseSyncEngine` |

---

#### 3.8.2 `app/services/sync_service.py` — DatabaseSyncEngine

**异构关系型数据库同步引擎核心类**，负责 MySQL/PG/DM/Oracle/SQLServer/SQLite 六种关系型数据库的全量/增量同步。

**`main()` 执行流程：**

```
1. _build_sqlalchemy_url()  →  按 db_type 构建源库连接串
    ├─ MySQL:     mysql+pymysql://user:pwd@host:port/db?charset=utf8mb4
    ├─ PG:        postgresql+psycopg2://user:pwd@host:port/db
    ├─ DM:        dm+dmPython://user:pwd@host:port
    ├─ Oracle:    oracle+oracledb://user:pwd@host:port/?service_name=xxx
    ├─ SQLServer: mssql+pymssql://user:pwd@host:port/db?charset=utf8
    └─ SQLite:    sqlite:///文件绝对路径?timeout=15

2. _reflect_source_schema()  →  反射源库表结构
    ├─ DM/Oracle: 指定 schema = username.upper()
    ├─ SQLite: 全量反射后手动过滤（不支持 only 参数）
    └─ 其他: 直接 reflect(only=sync_tables)

3. _prepare_target_schema()  →  类型归一化 + 约束清洗 + 在目标库建表
    ├─ 调用 dialect_handler.normalize_type() 翻译每个列的类型
    ├─ DM/Oracle: 列名转小写
    └─ create_all(bind=target_engine)

4. _migrate_data()  →  流式读取 + 微批次写入 + 水位线追踪
    ├─ full 模式: 无条件全量 SELECT
    ├─ inc_id 模式: WHERE id > last_watermark
    ├─ inc_time 模式: WHERE update_time > last_watermark
    └─ custom_sql 模式: 执行自定义 SQL → 写入指定目标表
        ├─ 每 batch_size 条写入一次
        ├─ 每批次边界探测暂停/取消信号
        └─ 追踪每条记录的水位线
```

**关键方法：**

| 方法 | 功能 |
|------|------|
| `_build_sqlalchemy_url()` | 按 db_type 构建 SQLAlchemy 连接串 |
| `_reflect_source_schema()` | 反射源库表结构（含 DM/Oracle/SQLite 特殊处理） |
| `_prepare_target_schema()` | 方言类型归一化、约束剥离、建表 |
| `_migrate_data()` | 流式读取 + 微批次 upsert + 水位线追踪 |
| `_build_extract_query()` | 根据 collect_mode 动态生成 SELECT + WHERE |
| `_clean_row_data()` | 行数据清洗（DM/Oracle 大写匹配、LOB 读取、NOT NULL 兜底） |
| `_execute_upsert()` | PG `ON CONFLICT` 策略（insert/skip/overwrite） |
| `_check_task_status()` | 批次边界探测 Redis 暂停/取消信号 |
| `_resolve_target_name()` | 表名映射（DM/Oracle 大小写不敏感） |

---

#### 3.8.3 `app/services/mongo_sync_engine.py`

**MongoDB 抽取引擎**。支持全量、`_id` ObjectId 增量、时间戳增量三种模式。目标可以是 PG（`_id` TEXT PK + `raw_doc` JSON）或另一个 MongoDB（`ReplaceOne + upsert`）。

---

#### 3.8.4 `app/services/api_sync_engine.py`

**HTTP 接口采集引擎**。支持三种模式：
- `monitor` → 响应时间/状态码写入 InfluxDB
- `data` → 响应体按 `api_data_path` 提取后写入 PG（JSON 列）
- `both` → 两者同时

---

#### 3.8.5 `app/services/ftp_sync_engine.py`

**FTP/SFTP 文件采集引擎**。流程：多协议连接（FTP/FTPS/SFTP/SDTP）→ 流式下载（每 ~400KB 探针暂停/取消）→ MD5 去重 → 结构化解析（CSV/JSON/YAML/Excel/XML）→ 幂等写入 PG。

---

#### 3.8.6 `app/services/snmp_sync_engine.py`

**SNMP 采集引擎**（pysnmp 7.x 异步 API）。支持 v1/v2c/v3 三种版本。
- `metric` 模式：GET OID 标量值 → InfluxDB
- `info` 模式：WALK 表格 OID → 按索引聚合为行 → PG

---

#### 3.8.7 `app/services/socket_sync_engine.py`

**原生 Socket 采集引擎**。支持 TCP/UDP 协议，utf-8/hex 指令编码，json/text/hex 响应解析。监控入 InfluxDB，数据入 PG。

---

#### 3.8.8 `app/services/kafka_sync_engine.py`

**Kafka 常驻消费引擎**。基于 `AIOKafkaConsumer`：
- 手动 commit offset（写入 PG 成功后才 commit）
- 攒批写入（batch_size + batch_timeout_ms 双条件）
- 消费速率 + Lag 写入 InfluxDB
- 幂等：`topic+partition+offset` 的 MD5 作为主键
- `run(stop_event)` 由 `KafkaConsumerManager` 以 `asyncio.Task` 方式启动

---

#### 3.8.9 `app/services/kafka_manager.py`

**`KafkaConsumerManager`** — 管理所有 Kafka 常驻 Consumer 的生命周期：
- 每个 task_id 对应一个 `(asyncio.Task, asyncio.Event)` 二元组
- `start()` → 创建 `asyncio.create_task()` 运行消费循环
- `stop()` → `stop_event.set()`，优雅退出（30 秒超时后强制取消）
- `stop_all()` → 关闭所有 Consumer
- `status()` → 查询 Consumer 运行状态

---

#### 3.8.10 `app/services/scheduler_service.py`

**APScheduler 定时调度服务。**
- `AsyncIOScheduler` 实例（时区：`Asia/Shanghai`）
- `refresh_scheduler_jobs()`：读取 `sys_collect_task` 中所有 `status=1` 且 `schedule_cron` 不为空的任务，解析 Cron 表达式，注册到调度器
- `trigger_task_to_arq(task_id)`：时间一到，将 task_id 推入 ARQ 队列

---

#### 3.8.11 `app/services/task_control.py`

**Redis 任务控制服务**（同步）。使用 `redis.ConnectionPool`：

| 函数 | Redis Key | 用途 |
|------|-----------|------|
| `set_task_status()` | `task_control:{task_id}` | 写入 paused/cancelled/running |
| `get_task_status()` | 同上 | 读取当前控制状态（不存在默认 running） |
| `save_watermark()` | `task:{task_id}:watermark` | 暂停时保存断点水位线（24h 过期） |
| `get_saved_watermark()` | 同上 | 恢复时打捞水位线 |

---

#### 3.8.12 `app/services/file_client_factory.py`

多协议文件客户端工厂，`BaseFileClient` 抽象基类 + 4 个适配器：

| 适配器 | 协议 | 依赖 |
|--------|------|------|
| `FtpClientAdapter` | FTP / FTPS | `ftplib` + `ssl`（自动检测 TLS） |
| `SftpClientAdapter` | SFTP | `paramiko` SSH |
| `SdtpClientAdapter` | SDTP（预留） | 私有 SDK |

---

#### 3.8.13 `app/services/dialects/` — 方言处理器

6 个方言处理器，Strategy 模式，通过 `get_dialect_handler(db_type)` 路由：

| 处理器 | 关键归一化 |
|--------|-----------|
| `MySQLHandler` | DATETIME→DateTime, TINYINT→Integer, ENUM→String, LONGTEXT→Text |
| `PostgreSQLHandler` | ENUM→String(255) |
| `DMHandler` | VARCHAR2→String, NUMBER→Numeric, CLOB→Text, DEFAULT SYSDATE 剥离 |
| `OracleDialectHandler` | VARCHAR2→String, NUMBER→Integer/Numeric, CLOB→Text, BLOB→Binary, SYSDATE 剥离, autoincrement 剥离 |
| `SqlServerDialectHandler` | NVARCHAR→String, MONEY→Numeric, BIT→Boolean, DATETIME2→DateTime, UNIQUEIDENTIFIER→String(36), GETDATE()/NEWID() 剥离 |
| `SQLiteDialectHandler` | INT→Integer, TEXT→Text, REAL→Float, BLOB→Text, NullType→Text, CURRENT_TIMESTAMP 剥离 |

---

### 3.9 CRUD 操作层 (`app/crud/`)

---

| 模块 | 类 | 功能 |
|------|-----|------|
| `crud_datasource.py` | `CRUDDataSource` | create / get_by_id / update / delete / get_list（分页+排序+条件过滤） |
| `crud_tsync.py` | `CRUDCollectTask` | create / get_by_id / update / change_status / delete / get_list（含 run_status 判定逻辑：查 Redis 锁 + 最新 TaskLog + Kafka Manager 状态） / update_watermark / get_dashboard_data |
| `crud_tasklog.py` | `CRUDTaskLog` | get_list（分页+多条件过滤） / get_detail（支持 log_id 或 task_id） |
| `crud_exec_log.py` | `CRUDExecLog` | get_list（按 task_id/log_id/target_table/status 过滤） |

---

### 3.10 工具模块 (`app/utils/`)

---

| 文件 | 核心功能 |
|------|----------|
| `encryptDecrypt.py` | AES CBC 加密/解密（server_key + web_key 双密钥） |
| `sorter.py` | 冒泡/选择/快速排序算法（学习用途） |
| `db_helper.py` | `build_db_url()` 构建 7 种数据库的 SQLAlchemy 连接串（含 Oracle service_name/SID 切换、SQL Server 命名实例、SQLite 文件路径） + MongoDB 集合列表获取 |
| `cron_helper.py` | `generate_cron_expression()` 将 schedule_type + schedule_value 翻译为标准 Cron 表达式 |

---

### 3.11 文档 (`docs/`)

| 文件 | 内容 |
|------|------|
| `API_FRONTEND.md` | 前端接口对接文档（16 章，含所有接口的请求/响应示例、参数表、注意事项） |
| `DATABASE_TABLES.md` | 数据库表结构文档（5 张表 + 表关系图） |
| `PROJECT_DOCUMENTATION.md` | 本文档（工程全景） |

---

## 四、模块间调用关系

```
app/main.py (入口)
├── 启动 ARQ Worker 子进程
│   └── app/worker.py
│       ├── EngineFactory → 7 种引擎
│       ├── CRUD 层 → Models → DB
│       └── task_control (Redis 同步客户端)
│
├── lifespan 生命周期
│   ├── app/core/license.py (许可验证)
│   ├── app/db/session.py (双数据库引擎)
│   ├── app/core/redis.py (异步 Redis)
│   ├── app/core/mongo.py (Motor)
│   ├── app/core/arq_pool.py (ARQ 池)
│   ├── app/core/influx_client.py (InfluxDB)
│   ├── app/services/scheduler_service.py (APScheduler)
│   └── app/services/kafka_manager.py (自动拉起 Kafka)
│
├── create_app() → FastAPI
│   ├── CORS 中间件
│   └── app/api/v1/ (6 个子路由)
│       ├── /datasource → CRUDDataSource
│       ├── /tsync → CRUDCollectTask + ARQ Pool + KafkaManager
│       ├── /tasklog → CRUDTaskLog
│       ├── /execlog → CRUDExecLog
│       ├── /monitor → InfluxDB 查询
│       └── /explorer → 采集库直接查询
│
└── 关闭阶段
    ├── kafka_manager.stop_all()
    ├── scheduler.shutdown()
    ├── close_arq_pool() / close_redis()
    ├── close_mongo() / close_influx()
    └── worker_process.terminate()
```

---

## 五、核心数据流

### 5.1 一个同步任务（批处理）的完整生命周期

```
1. 前端 POST /api/v1/tsync/run  {"task_id": "xxx"}
   ↓
2. tsync.py: 校验任务存在 + 启用 → Redis 防抖检查 → 清除旧控制信号
   → 删除旧 pending 僵尸日志 → 创建 pending TaskLog → ARQ enqueue_job
   → 返回 {"log_id": "...", "status": "pending"}
   ↓
3. ARQ Worker (独立子进程) 接管
   ↓
4. worker.py run_sync_job:
   → 获取 Redis 分布式锁
   → 查询 CollectTask + DataSource
   → 组装 DBSyncReq
   → 更新 TaskLog: pending → running
   → asyncio.to_thread(EngineFactory.create(req).main())
   ↓
5. 引擎执行 (DatabaseSyncEngine 为例):
   → _build_sqlalchemy_url() 构建源库连接
   → _reflect_source_schema() 反射表结构
   → _prepare_target_schema() 方言处理 → 建表
   → _migrate_data() 流式搬运 + 批次暂停/取消探针
   ↓
6. Worker 处理结果:
   → 更新 TaskLog: status → success/failed/paused/cancelled
   → 回写 last_watermark
   → 创建 SyncExecutionLog 表级记录
   ↓
7. 释放 Redis 分布式锁
   ↓
8. 前端轮询 /tasklog/detail?log_id=xxx 获取最新状态
```

### 5.2 Kafka 流式任务的完整生命周期

```
1. 系统启动 (lifespan)
   → start_all_kafka_tasks()
   → 查所有 DataSource.type="kafka" + CollectTask.status=1
   → kafka_manager.start() 为每个创建 asyncio.Task
   ↓
2. KafkaSyncEngine.run(stop_event):
   → AIOKafkaConsumer 启动
   → while not stop_event:
       consumer.getmany(batch_size, batch_timeout_ms)
       → 攒批写入 PG (ON CONFLICT DO NOTHING 幂等)
       → consumer.commit()  # 写成功后才提交 offset
       → 写 InfluxDB 监控 (consumed + elapsed_ms)
   ↓
3. 用户操作:
   → /kafka/stop → stop_event.set() → 优雅退出（30s 超时）
   → /kafka/start → kafka_manager.start() 重新拉起
   ↓
4. 系统关闭 (lifespan yield 之后)
   → kafka_manager.stop_all() 遍历所有 Consumer 停止
```

### 5.3 应用启动完整流程

```
1. python -m app.main
   ↓
2. freeze_support() → 启动 ARQ Worker 子进程
   ↓
3. create_app():
   → FastAPI(title="数据采集平台", lifespan=...)
   → CORS / 静态文件 / 自定义 Swagger
   → 挂载 6 个子路由到 /api/v1
   ↓
4. lifespan 启动:
   ├─ 许可验证 (license.key)
   ├─ PostgreSQL 连接 → 开发模式 init_db()
   ├─ 僵尸日志清理 (pending/running → failed)
   ├─ Redis / MongoDB / ARQ Pool / InfluxDB 初始化
   ├─ APScheduler 启动 + refresh_scheduler_jobs()
   └─ start_all_kafka_tasks()
   ↓
5. uvicorn.run(app) → 开始监听请求
```

---

## 六、支持的数据库类型汇总

| db_type | 源库驱动 | 目标库 | 引擎 | 方言处理器 |
|---------|----------|--------|------|-----------|
| `mysql` | pymysql | PG | DatabaseSyncEngine | MySQLHandler |
| `postgresql` | psycopg2 | PG | DatabaseSyncEngine | PostgreSQLHandler |
| `dm` | dmPython | PG | DatabaseSyncEngine | DMHandler |
| `oracle` | oracledb | PG | DatabaseSyncEngine | OracleDialectHandler |
| `sqlserver` | pymssql | PG | DatabaseSyncEngine | SqlServerDialectHandler |
| `sqlite` | sqlite3 (内置) | PG | DatabaseSyncEngine | SQLiteDialectHandler |
| `mongodb` | pymongo | PG / MongoDB | MongoSyncEngine | — |
| `ftp` | ftplib / paramiko | PG (解析) / 本地 (下载) | FtpSyncEngine | — |
| `api` | httpx | PG + InfluxDB | ApiSyncEngine | — |
| `snmp` | pysnmp 7.x | PG + InfluxDB | SnmpSyncEngine | — |
| `socket` | socket (内置) | PG + InfluxDB | SocketSyncEngine | — |
| `kafka` | aiokafka | PG + InfluxDB | KafkaSyncEngine | — |

---

## 七、已知问题与注意事项

| 问题 | 文件 | 说明 |
|------|------|------|
| AES IV 等于密钥 | `app/utils/encryptDecrypt.py` | 密码学不安全，相同明文产生相同密文 |
| 调试 print 未清理 | `app/utils/encryptDecrypt.py` | `decrypt_to_web` 中有调试输出 |
| `get_session()` 中 `logger` 问题 | `app/db/session.py` | 之前版本存在 NameError，现已从 `app.core` import |
| 所有安全开关默认关闭 | `.env` | `ENABLE_ENCRYPT`、`ENABLE_TOKEN` 均为 False |
| ORM 模型与 Alembic 分离 | — | 元数据库表由 `init_db()` 直接 create_all；采集落地库表由引擎动态 create_all |
| `charset` 字段语义重载 | Oracle/SQL Server | Oracle 不再滥用 charset；SQL Server 改用 `config_json.instance` |
| `config_json` 参数依赖 | Oracle/SQL Server | Oracle SID 需 `config_json.sid`；SQL Server 命名实例需 `config_json.instance` |
