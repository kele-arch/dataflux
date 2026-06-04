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
from app.models import *

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
