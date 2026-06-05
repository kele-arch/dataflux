# -- coding: utf-8 --
# @Author: 胡H
# @File: app/db/session.py
# @Created: 2025/11/19 10:41
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from typing import Generator
from sqlalchemy.engine import Engine
from app.core import logger

DATABASE_URL = settings.database_url

engine: Engine = create_engine(
    DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)  # Session 工厂


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session():
    """ 供 mqtt 回调 / 普通函数使用的 session 上下文管理器 """
    # session = global_vars.SessionLocal()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作异常，已回滚: {e}")
        raise
    finally:
        session.close()


def init_db():
    """ 初始化表
    :return:
    """
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)
