# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/redis.py
# @Created: 2026/2/9 11:21
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Redis 连接管理
import redis.asyncio as redis
from app.core.config import settings

# 全局 Redis 客户端实例
redis_client: redis.Redis = None


async def init_redis():
    """初始化 Redis 连接"""
    global redis_client
    # print(f" 正在连接 Redis: {settings.REDIS_URL} ...")
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True  # 自动将 bytes 转为 str
        )
        await redis_client.ping()
        # print("Redis 连接成功")
    except Exception as e:
        # print(f"Redis 连接失败: {e}")
        raise e


async def close_redis():
    """关闭 Redis 连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        # print("Redis 连接已关闭")


async def get_redis() -> redis.Redis:
    """依赖注入获取 Redis 客户端"""
    return redis_client
