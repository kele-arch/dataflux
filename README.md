<picture>
  <source media="(prefers-color-scheme: dark)" srcset="static/logo-dark.svg">
  <img alt="Dataflux" src="static/logo.svg" height="80">
</picture>

# Dataflux — 一站式异构数据采集平台

<p>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.12_|_3.13-3776AB?logo=python&logoColor=white"></a>
  <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.103+-009688?logo=fastapi"></a>
  <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-supported-2496ED?logo=docker&logoColor=white"></a>
  <a href="https://github.com/hh-macro/dataflux"><img alt="Stars" src="https://img.shields.io/github/stars/hh-macro/dataflux?color=ea580c"></a>
</p>

**Dataflux** 是一个轻量级、插件化的异构数据采集与同步平台。支持 **12 种数据源**，提供任务调度、增量采集、分布式执行、流式消费、数据生命周期管理等完整能力。

📦 **前端仓库：**[dataflux-web][frontend]

---

## 支持的数据源

| 类型 | 引擎模式 | 支持的数据源 |
|------|---------|-------------|
| 🗄️ 关系型数据库 | 批处理 | MySQL, PostgreSQL, Oracle, DM(达梦), SQL Server, SQLite |
| 🍃 NoSQL | 批处理 | MongoDB |
| 📁 文件系统 | 批处理 | FTP / FTPS / SFTP / SDTP |
| ☁️ 对象存储 | 批处理 | 阿里云 OSS / AWS S3 / MinIO (S3 兼容) |
| 🌐 HTTP API | 批处理 | 任意 RESTful API |
| 🔧 网络协议 | 批处理 | SNMP v1/v2c/v3, TCP/UDP Socket |
| 📨 消息队列 | **流式常驻** | Kafka, MQTT, RabbitMQ |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (Vue 3)                         │
│              https://github.com/hh-macro/dataflux-web     │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP REST API
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI 主进程                           │
│  ┌───────────┐  ┌────────────┐  ┌───────────────┐       │
│  │  路由层   │  │  中间件    │  │  Swagger /docs │       │
│  └─────┬─────┘  └────────────┘  └───────────────┘       │
│        │                                                  │
│  ┌─────▼──────────────────────────────────────────┐      │
│  │              Service 层                          │      │
│  │  ┌──────┐ ┌───────┐ ┌──────┐ ┌──────────┐     │      │
│  │  │ 同步 │ │ 调度  │ │ 清理 │ │ 流式管理 │     │      │
│  │  │ 引擎 │ │ 服务  │ │ 服务 │ │(Kafka/   │     │      │
│  │  │(12种)│ │(Cron) │ │(DLM) │ │ MQTT/Rab)│     │      │
│  │  └──────┘ └───────┘ └──────┘ └──────────┘     │      │
│  └───────────────────────────────────────────────┘      │
│        │                                                  │
│  ┌─────▼──────┐  ┌──────────┐  ┌──────────────┐        │
│  │ PostgreSQL │  │  Redis   │  │  InfluxDB     │        │
│  │(元数据+    │  │(队列+锁  │  │(监控时序)    │        │
│  │ 采集落地)  │  │ +控制)   │  │              │        │
│  └───────────┘  └──────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────┘
                           │
                  ┌────────▼────────┐
                  │  ARQ Worker     │
                  │  (独立子进程)    │
                  │  max_jobs=3     │
                  └─────────────────┘
```

**核心设计：** 任务定义存 PostgreSQL → 调度放 APScheduler 内存 → 执行放 ARQ Worker 子进程 → Redis 仅做队列和分布式锁。

---

## 快速开始

### 前置依赖

- Python **3.12** 或 **3.13**
- PostgreSQL **15+**
- Redis **7+**
- （可选）MongoDB、InfluxDB — 仅特定数据源需要

### 1. 克隆仓库

```bash
git clone https://github.com/hh-macro/dataflux.git
cd dataflux
```

### 2. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少修改以下项：

```env
DATABASE_URL=postgresql+psycopg2://postgres:你的密码@localhost:5432/dataflux
COLLECTED_DATABASE_URL=postgresql+psycopg2://postgres:你的密码@localhost:5432/dataflux_collected
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=请生成一个足够长的随机字符串
ENABLE_TOKEN=False       # 开发环境建议关闭登录验证
ENABLE_LICENSE=False     # 开发环境建议关闭许可验证
```

> 完整配置项说明见 [`.env.example`][env-example]。

### 4. 创建数据库

```sql
CREATE DATABASE dataflux;
CREATE DATABASE dataflux_collected;
```

### 5. 启动服务

```bash
python -m app.main
```

服务启动后访问：

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8028/docs` | Swagger API 文档 |
| `http://127.0.0.1:8028/redoc` | ReDoc 文档 |

### Docker 部署

```bash
# 构建镜像
docker build -t dataflux:latest .

# 启动
docker-compose up -d
```

---

## 核心功能

### 🔄 异构数据同步

- **自动类型归一化：** 6 种关系型数据库列类型自动翻译为 PostgreSQL 兼容类型
- **冲突策略：** `overwrite` 覆盖 / `skip` 跳过 / `insert` 纯新增
- **流式搬运：** 微批次读写，支持大表，不会 OOM

### ⏱️ 增量采集

| 模式 | 适用场景 | 水位线 |
|------|---------|--------|
| `full` | 全量同步 | — |
| `inc_id` | 自增主键 | `WHERE id > last_watermark` |
| `inc_time` | 时间戳列 | `WHERE update_time > last_watermark` |
| `custom_sql` | 自定义提取 | 用户 SQL |

### 📅 任务调度

| 调度类型 | schedule_type | schedule_value 示例 |
|---------|--------------|-------------------|
| 不调度 | `none` | — |
| 标准 Cron | `cron` | `"0 2 * * *"` |
| 固定间隔 | `interval_min` | `"30"` (分钟) |
| 每天 | `daily` | `"02:30"` |
| 每周 | `weekly` | `"3 08:00"` (周三 8 点) |

### 🎛️ 任务控制

- **暂停 / 取消 / 恢复** — 任意批次边界响应，不丢数据
- **断点续传：** 暂停时水位线持久化到 Redis，恢复后自动回写继续
- **分布式锁：** Redis 排他锁防止重复执行
- **卡死解锁：** `POST /tsync/unlock` 强制清理锁和僵尸日志

### 📨 流式消费

Kafka / MQTT / RabbitMQ 三种消息队列以**常驻 asyncio.Task** 方式运行：

- 攒批写入 PG，满批或超时触发
- **手动 ACK：** 写库成功后才 commit offset，确保零丢失
- 消费速率写入 InfluxDB，前端实时监控

### 🧹 数据生命周期管理（DLM）

- **手动清理：** `truncate` / `drop` / `by_days` / `by_count` 四种模式
- **定时自动清理：** 配置 `clean_cron`，APScheduler 到点触发 ARQ Worker 执行
- **联动清理：** 表数据 + 文件记录 + 本地缓存文件，一键扫清

### 📊 双层日志

- **任务级：** `sys_task_log` — 每次执行的状态、条数、耗时、错误信息
- **表级：** `sync_execution_log` — 每张表的源/目标表名、记录数、水位线快照（血缘映射）

---

## 项目结构

```
dataflux/
├── app/
│   ├── main.py                    # 入口（FastAPI + ARQ Worker 子进程）
│   ├── worker.py                  # ARQ Worker（同步 + 清理 job）
│   ├── exceptions.py              # 自定义异常（暂停/取消）
│   ├── api/v1/                    # 路由层（6 个路由模块，22+ 接口）
│   ├── models/                    # ORM 模型（6 张表）
│   ├── schemas/                   # Pydantic 请求/响应模型
│   ├── crud/                      # 数据库操作层
│   ├── services/                  # 业务逻辑层
│   │   ├── sync_service.py        # 关系型数据库同步引擎
│   │   ├── mongo_sync_engine.py   # MongoDB 同步引擎
│   │   ├── api_sync_engine.py     # HTTP API 采集引擎
│   │   ├── ftp_sync_engine.py     # FTP/SFTP 文件采集引擎
│   │   ├── oss_sync_engine.py     # OSS/S3 对象存储采集引擎
│   │   ├── snmp_sync_engine.py    # SNMP 采集引擎
│   │   ├── socket_sync_engine.py  # Socket 采集引擎
│   │   ├── kafka_sync_engine.py   # Kafka 常驻消费引擎
│   │   ├── mqtt_sync_engine.py    # MQTT 常驻订阅引擎
│   │   ├── rabbitmq_sync_engine.py# RabbitMQ 常驻消费引擎
│   │   ├── clean_service.py       # 数据生命周期管理服务
│   │   ├── scheduler_service.py   # APScheduler 调度（采集+清理）
│   │   ├── task_control.py        # Redis 任务控制（暂停/取消/水位线）
│   │   ├── engine_factory.py      # 引擎工厂（12 种路由）
│   │   ├── file_client_factory.py # 多协议文件客户端工厂
│   │   ├── kafka_manager.py       # Kafka Consumer 生命周期管理
│   │   ├── mqtt_manager.py        # MQTT Consumer 生命周期管理
│   │   ├── rabbitmq_manager.py    # RabbitMQ Consumer 生命周期管理
│   │   └── dialects/              # 数据库方言处理器（6 种）
│   ├── core/                      # 基础设施（配置、日志、Redis、安全、InfluxDB、MongoDB）
│   ├── db/                        # 双数据库引擎 + 会话管理
│   └── utils/                     # 工具（AES 加密、Cron 生成、连接串构建）
├── docs/                          # 文档
│   ├── PROJECT_DOCUMENTATION.md   # 工程全景文档
│   ├── API_FRONTEND.md            # 接口对接文档（前端视角）
│   └── DATABASE_TABLES.md         # 数据库表结构文档
├── alembic/                       # 数据库迁移
├── static/                        # 静态资源（Swagger UI）
├── .env.example                   # 环境变量模板
├── docker-compose.yml             # Docker Compose 单服务
├── docker-compose-all.yml         # Docker Compose 全家桶（含 PG/Redis/Mongo/InfluxDB）
├── Dockerfile                     # 多阶段构建
├── pyproject.toml                 # 项目元数据 + 依赖声明
└── LICENSE                        # MIT License
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | 异步路由，自动 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 (Mapped) | 声明式基类，双库架构 |
| 数据库 | PostgreSQL 15 | 元数据库 + 采集落地库 |
| 迁移 | Alembic | 自动生成迁移脚本 |
| 缓存/锁 | Redis 7 | 分布式锁 + 任务状态控制 + 水位线暂存 |
| 任务队列 | ARQ | 基于 Redis 的异步后台队列 |
| 调度 | APScheduler 3.x | Cron 定时触发 |
| 时序监控 | InfluxDB 3.x | Line Protocol 写入，SQL 查询 |
| 文档存储 | MongoDB | Motor 异步驱动 |
| 认证 | JWT + passlib | HS256 签名 + pbkdf2_sha256 哈希 |
| 日志 | Loguru | 双 sink（控制台 + 文件轮转） |

---

## 文档

| 文档 | 说明 |
|------|------|
| [工程全景文档][project-doc] | 逐文件详解、架构图、数据流、模块调用关系 |
| [接口对接文档][api-doc] | 每个接口的请求/响应示例、参数表、注意事项 |
| [数据库表结构][db-doc] | 表字段说明、关系图 |
| [清理服务测试指南][clean-test] | DLM 功能的手动测试步骤 |

---

## 前端

配套前端项目：[**dataflux-web**][frontend]（Vue 3 + Element Plus）


[frontend]: https://github.com/hh-macro/dataflux-web
[license]: LICENSE
[contributing]: CONTRIBUTING.md
[env-example]: .env.example
[project-doc]: docs/PROJECT_DOCUMENTATION.md
[api-doc]: docs/API_FRONTEND.md
[db-doc]: docs/DATABASE_TABLES.md
[clean-test]: docs/CLEAN_SERVICE_TEST.md

