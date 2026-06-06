# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/arq_pool.py
# @Created: 2026/6/6 10:05
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: ARQ 的 Redis 连接池管理, 提供全局可用的连接池实例, 并在应用启动时初始化, 在关闭时清理资源
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings

# 全局的 ARQ Redis 连接池
arq_pool = None


async def init_arq_pool():
    global arq_pool
    # 动态解析 .env 中的 REDIS_URL
    parsed = urlparse(settings.REDIS_URL)
    arq_pool = await create_pool(RedisSettings(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip('/')) if parsed.path else 0
    ))


async def close_arq_pool():
    global arq_pool
    if arq_pool:
        await arq_pool.close()
