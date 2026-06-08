# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/mongo.py
# @Created: 2026/3/31 21:21
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: MongoDB 异步连接管理

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core import logger


class MongoDBClient:
    """ 用于存放 client 和 db 实例 """
    client: AsyncIOMotorClient = None
    db = None


mongo_client = MongoDBClient()


async def init_mongo():
    """ 初始化 MongoDB 连接 """
    try:
        mongo_client.client = AsyncIOMotorClient(
            settings.MONGO_URL,
            serverSelectionTimeoutMS=5000,  # 连接服务器的超时时间, 单位毫秒
            connectTimeoutMS=60000,  # 建立连接的超时时间, 单位毫秒
            socketTimeoutMS=60000  # 套接字读写的超时时间, 单位毫秒
        )  # 建立连接
        # 指定默认使用的数据库
        mongo_client.db = mongo_client.client[settings.MONGO_DB_NAME]

        # 触发一次 ping 测试连通性 (AsyncIOMotorClient 是懒加载的)
        await mongo_client.client.admin.command('ping')

        logger.success(f"MongoDB 连接成功 | 地址:{settings.MONGO_URL} | 数据库:{settings.MONGO_DB_NAME}")
    except Exception as e:
        logger.error(f"MongoDB 连接失败: {e}")
        raise e


async def close_mongo():
    """关闭 MongoDB 连接"""
    if mongo_client.client:
        mongo_client.client.close()
        # logger.info("MongoDB 连接已安全断开")
