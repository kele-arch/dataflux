# -- coding: utf-8 --
# @Author: 胡H
# @File: app/main.py
# @Created: 2025/11/19 10:03
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: man!!!
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.redis import close_redis, init_redis
from app.db.session import init_db, engine
from app.core.config import settings
from app.core import logger
from app.middleware import init_middlewares


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ 后端启动前与启动后的工作
    :param app:
    :return:
    """
    # SQL 数据库
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.success(f"关系SQL 连接成功 | 地址:{settings.DATABASE_URL}")

        # 开发环境下自动建表
        if settings.ENV == "development":
            init_db()

    except Exception as e:
        if settings.ENABLE_DB_CHECK:
            logger.error(f"关系SQL 连接失败! 错误: {e}")
            raise  # 终止启动
        else:
            logger.warning(f"关系SQL 连接失败, 已忽略. 错误: {e}")

    # Redis
    try:
        await init_redis()
        logger.success(f"Redis 连接成功 | 地址:{settings.REDIS_URL}")
    except Exception as e:
        if settings.ENABLE_DB_CHECK:
            logger.error(f"Redis 连接失败! 错误: {e}")
            raise  # 终止启动
        else:
            logger.warning(f"Redis 连接失败, 已忽略. 错误: {e}")

    logger.success("verification-support 工程初始化完成")

    yield  # <- 应用开始运行.  yield 之后的代码会在应用关闭时执行
    # 关闭前如果有资源要释放可以写这里(例如关闭数据库连接、Redis 连接等)

    await close_redis()  # 关闭 Redis 连接
    logger.info('程序执行结束')


def create_app() -> FastAPI:
    app = FastAPI(title="Form Service", version="0.1", lifespan=lifespan)

    # 中间件配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 前端地址 -> ["http://localhost:3000"]
        allow_credentials=True,  # 允许前端携带 Cookie
        allow_methods=["*"],  # 允许的 HTTP 请求方法列表 -> GET POST PUT...
        allow_headers=["*"],  # 允许的 HTTP 请求头列表 -> Content-Type Authorization...
    )
    init_middlewares(app)  # 注册中间件

    # 把 v1 的所有路由挂到 /api/v1
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    # uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)  # 正常环境使用这个
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)  # 打包 exe 使用这个
