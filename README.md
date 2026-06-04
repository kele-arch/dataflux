# 说明

## 一、快速开始

### 1.  环境要求

- Python 3.12 
- pip 或 uv 包管理器
- PostgreSQL 15 数据库
- Redis 服务(可选)

### 2.  安装依赖

**使用 `uv` 包管理器 (推荐)：**

```
pip install uv
```

```
uv sync
```

**使用 pip：**

```
pip install -r requirements.txt
```

### 3. 环境配置

创建 `.env` 文件，配置必要的环境变量：

```yaml
ENV=development

# 数据库连接配置
DATABASE_URL=postgresql+psycopg2://postgres:123456@localhost:5432/verification01
# 数据库模式(不写默认public)
DB_SCHEMA=verification

# 安全秘钥
SECRET_KEY=abc123xyz456def789ghi012jkl345mno678pqr901stu234vwx567yz

# 是否启用加密(不写默认启动)
ENABLE_ENCRYPT=false

# 是否启动token验证(不写默认启动)
ENABLE_TOKEN=false

# Redis 配置(可自选)
REDIS_URL=redis://127.0.0.1:6379/6

# 服务端配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8026
LOG_LEVEL=info
```

### 4. 数据库迁移

可选择使用 `alembic` 或者  导入 `.sql`

### 5. 启动应用

使用包的方式启动

```
python -m app.main
```



## 二、其他文档说明

pass

## 文件打包

```bash
pyinstaller -n "verification" -D --add-data ".env;." --hidden-import="uvicorn.logging" --hidden-import="uvicorn.loops.auto" --hidden-import="uvicorn.protocols.http.auto" --hidden-import="uvicorn.protocols.websockets.auto" --hidden-import="uvicorn.lifespan.on" --hidden-import="psycopg2" --hidden-import="passlib.handlers.bcrypt" --hidden-import="passlib.handlers.pbkdf2" --collect-submodules="uvicorn" --noconfirm app/main.py
```

## 架构

```bash
Init-FastApi/
├─ alembic/                       # 迁移配置
├─ app/
│  ├─ __init__.py
│  ├─ main.py                     # 程序入口
│  ├─ com/                        # 单功能工具/装饰器等
│  │   └─ __init__.py
│  ├─ core/                       # 核心配置和安全
│  │   ├─ __init__.py
│  │   ├─ config.py               # 配置文件
│  │   ├─ log.py                  # 日志配置
│  │   └─ security.py             # JWT/权限控制
│  ├─ api/
│  │   └─ v1/
│  │       ├─ __init__.py
│  │       └─ forms.py            # 路由
│  ├─ models/
│  │   ├─ __init__.py
│  │   └─ form.py                 # ORM 模型
│  ├─ schemas/
│  │   └─ form.py                 # Pydantic 模型
│  ├─ crud/
│  │   ├─ __init__.py
│  │   └─ form_crud.py            # 数据库操作逻辑
│  ├─ db/
│  │   ├─ __init__.py
│  │   ├─ base.py                 # Base ORM
│  │   └─ session.py              # 数据库会话
│  ├─ utils/
│  │   └─ __init__.py             # 公共工具类
│  └─ middleware/                 # 自定义中间件
│  │   └─ __init__.py
│  ├─ services                    # services层
├─ tests/                         # 测试目录
├─ .env 
├─ .gitignore
├─ alembic.ini
├─ pyproject.toml
├─ uv.lock
└─ README.md
```

**启用**

```
uvicorn app.main:app --reload
# 或直接：
python -m app.main
```

## alembic使用

安装

```bash
uv add alembic
```

初始化

```bash
alembic init alembic
```

**修改 `env.py` 文件**

```python
from logging.config import fileConfig
import sys
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 Alembic 能找到 app 目录（非常关键）
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载日志配置
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 引入你的 Base（所有 ORM 模型）
from app.db.base import Base  # 你项目的 Base 类汇总
from app.core.config import settings  # 读取数据库连接
from app.models import chat, user

# 让 Alembic 知道模型信息，用于自动迁移
target_metadata = Base.metadata

# 替换 sqlalchemy.url 为 .env 中配置  
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True  # 自动识别字段类型变化
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 自动识别字段类型变化
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**alembic.ini 设置数据库连接**

一般改 `sqlalchemy.url = %(DATABASE_URL)s` 即可

```python
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
path_separator = os
sqlalchemy.url = %(DATABASE_URL)s

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

生成迁移脚本(自动分析 ORM)

```bash
alembic revision --autogenerate -m "init tables"
```

应用迁移(建表)

```bash
alembic upgrade head
```

**修改 ORM 如何更新？**

- 生成脚本

```bash
alembic revision --autogenerate -m "描述"
```

- 更新表

```bash
alembic upgrade head
```

**数据表回滚**

```bash
alembic downgrade -1  # 回滚上一版
```

```bash
alembic downgrade <目标版本号>
```
