# Dataflux

异构数据源同步平台，支持 MySQL / PostgreSQL 跨库同步，提供任务调度、增量采集、分布式执行等能力。

## 技术栈

- **框架：** FastAPI + Uvicorn
- **数据库：** PostgreSQL (SQLAlchemy 2.0 + Alembic)
- **缓存/锁：** Redis
- **队列：** ARQ (异步任务队列)
- **调度：** APScheduler (Cron 定时调度)
- **认证：** JWT + pbkdf2_sha256

## 快速开始

```bash
# 1. 安装依赖
uv sync          # 或 pip install -r requirements.txt

# 2. 配置 .env
cp .env.example .env   # 编辑数据库连接、Redis、密钥等

# 3. 启动 (自动建表)
python -m app.main
```

服务默认运行在 `http://127.0.0.1:8011`，API 文档访问 `/docs`。

## 项目结构

```
app/
├── main.py                  # 入口 (FastAPI + ARQ Worker 子进程)
├── api/v1/                  # 路由层
│   ├── tsync.py             # 同步任务管理 (CRUD + 执行 + 调度)
│   ├── datasource.py        # 数据源管理 (CRUD + 连接测试 + 表结构)
│   ├── tasklog.py           # 任务执行日志
│   └── exec_log.py          # 表级同步日志 (血缘映射)
├── models/                  # ORM 模型
│   ├── bashModelMixin       # UUID 主键 + 审计字段基类
│   ├── collectTaskModel     # 同步任务表
│   ├── dataSourceModel      # 数据源配置表
│   ├── taskLogModel         # 任务日志 + 表级执行日志
│   └── otherModel           # 系统操作日志
├── schemas/                 # Pydantic 请求/响应模型
├── crud/                    # 数据库操作层
├── services/                # 业务逻辑层
│   ├── sync_service.py      # 同步引擎 (反射 → 类型归一化 → 流式搬运)
│   ├── scheduler_service.py # APScheduler 定时调度
│   ├── task_control.py      # 任务状态控制 (暂停/取消/恢复)
│   └── dialects/            # 数据库方言处理器 (MySQL/PG 类型映射)
├── core/                    # 基础设施 (配置、日志、Redis、安全)
├── db/                      # 数据库引擎和会话管理
├── utils/                   # 工具类 (AES加密、DB连接构建、Cron生成)
└── worker.py                # ARQ Worker (分布式锁 + 同步执行 + 日志写入)
```

## 核心功能

任务定义放 PostgreSQL，调度放 APScheduler 内存，执行放 ARQ Worker，Redis 只做队列和锁

| 功能 | 说明 |
|------|------|
| 异构同步 | MySQL ↔ PostgreSQL 跨库同步，自动类型归一化 |
| 增量采集 | 支持自增列、时间戳两种增量模式 + 水位线记录 |
| 冲突策略 | overwrite(覆盖) / skip(跳过) / insert(纯新增) |
| 任务调度 | Cron / 固定间隔 / 每天 / 每周 五种调度模式 |
| 分布式锁 | Redis 排他锁防止重复执行 |
| 任务控制 | 支持暂停、取消、恢复正在运行的任务 |
| 自定义SQL | 支持自定义提取 SQL 同步到指定目标表 |
| 操作日志 | 任务级 + 表级双层日志，含策略、条数、水位线快照 |

## Alembic 迁移

```bash
alembic revision --autogenerate -m "描述"   # 生成迁移脚本
alembic upgrade head                          # 执行迁移
alembic downgrade -1                          # 回滚一步
```

## 打包 exe

```bash
pyinstaller --clean --noupx -n "dataflux" -D --add-data ".env;." --hidden-import="uvicorn.logging" --hidden-import="uvicorn.loops.auto" --hidden-import="uvicorn.protocols.http.auto" --hidden-import="uvicorn.protocols.websockets.auto" --hidden-import="uvicorn.lifespan.on" --hidden-import="psycopg2" --hidden-import="passlib.handlers.bcrypt" --hidden-import="passlib.handlers.pbkdf2" --hidden-import="redis" --hidden-import="redis.asyncio" --hidden-import="redis.connection" --hidden-import="redis.connection_pool" --hidden-import="arq" --hidden-import="arq.connections" --hidden-import="arq.worker" --hidden-import="arq.jobs" --hidden-import="apscheduler.schedulers.asyncio" --hidden-import="apscheduler.triggers.cron" --hidden-import="apscheduler.jobstores.memory" --hidden-import="jose.jwt" --hidden-import="jose.exceptions" --hidden-import="pydantic_settings" --hidden-import="loguru" --hidden-import="sqlalchemy.dialects.postgresql" --hidden-import="sqlalchemy.dialects.mysql" --collect-submodules="uvicorn" --collect-submodules="arq" --collect-submodules="apscheduler" --collect-all fastapi --collect-all starlette --collect-all redis --collect-all arq --exclude-module="hiredis" --noconfirm app/main.py
```

```bash
pyinstaller --clean --noupx -n "dataflux" -D --noconfirm --add-data ".env;." --add-data "static;static" --hidden-import="psycopg2" --hidden-import="passlib.handlers.bcrypt" --hidden-import="passlib.handlers.pbkdf2" --hidden-import="jose.jwt" --hidden-import="jose.exceptions" --hidden-import="loguru" --hidden-import="sqlalchemy.dialects.postgresql" --hidden-import="sqlalchemy.dialects.mysql" --collect-all fastapi --collect-all starlette --collect-all uvicorn --collect-all pydantic --collect-all pydantic_settings --collect-all redis --collect-all arq --collect-all apscheduler --collect-all aio_pika --copy-metadata aio_pika --copy-metadata aiormq --copy-metadata pydantic --copy-metadata fastapi --exclude-module="hiredis" app/main.py
```

​	
