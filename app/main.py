# -- coding: utf-8 --
# @Author: 胡H
# @File: app/main.py
# @Created: 2025/11/19 10:03
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: man!!!

import asyncio
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.mongo import init_mongo, close_mongo
from app.core.influx_client import init_influx, close_influx
from app.core.redis import close_redis, init_redis
from app.db.session import init_db, engine
from app.core.config import settings
from app.core import logger
from app.middleware import init_middlewares
from app.core.arq_pool import init_arq_pool, close_arq_pool
from app.services.scheduler_service import scheduler, refresh_scheduler_jobs


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

    try:
        await init_mongo()
    except Exception as e:
        if settings.ENABLE_DB_CHECK:
            raise  # 终止启动
        else:
            logger.warning("MongoDB 连接失败, 已忽略启动中断.")

    # 队列 Redis 池 (专门负责下发 ARQ 任务)
    try:
        await init_arq_pool()
        logger.success("ARQ 队列池连接成功")
    except Exception as e:
        logger.error(f"ARQ 队列池连接失败! 错误: {e}")

    # InfluxDB 时序监控数据库
    try:
        await init_influx()
    except Exception as e:
        logger.warning(f"InfluxDB 初始化失败, 监控写入将静默跳过: {e}")

    # 启动 APScheduler 定时器大脑
    try:
        scheduler.start()
        refresh_scheduler_jobs()  # 首次启动把数据库里的任务刷入内存
        logger.success("APScheduler 定时调度系统已启动")
    except Exception as e:
        logger.error(f"调度系统启动失败! 错误: {e}")

    logger.success("dataflux 工程初始化完成")

    yield  # <- 应用开始运行.  yield 之后的代码会在应用关闭时执行
    # 关闭前如果有资源要释放可以写这里(例如关闭数据库连接、Redis 连接等)

    logger.info("正在执行资源释放并关机...")
    # 停掉定时器
    if scheduler.running:
        scheduler.shutdown()
        logger.info("调度系统已关闭")

    # 关闭两个 Redis 连接池
    await close_arq_pool()
    await close_redis()

    try:
        await asyncio.wait_for(close_mongo(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("MongoDB 关闭超时, 强制跳过")

    await close_influx()

    logger.info('程序执行结束')


def create_app() -> FastAPI:
    app = FastAPI(title="dataflux", version="0.1", lifespan=lifespan)

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


def run_arq_worker():
    """ 子进程入口: 运行 Arq Worker """
    import asyncio
    from arq.worker import run_worker
    from app.worker import WorkerSettings

    # 因为是在新进程里，需要新建一个独立的事件循环
    asyncio.run(run_worker(WorkerSettings))


if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    import atexit

    # 帮助 Windows 打包成 exe 后能正确启动子进程，防止无限递归爆炸
    multiprocessing.freeze_support()

    logger.info("准备启动 FastAPI 主服务与 Arq Worker 独立进程...")

    # 在后台启动 Arq Worker 子进程
    worker_process = multiprocessing.Process(target=run_arq_worker, daemon=True)
    worker_process.start()
    logger.success(f"Arq 后台 Worker 进程已启动! (PID: {worker_process.pid})")


    # 注册退出清理函数
    def cleanup_worker():
        """ 确保主进程被干掉时, 带走 Worker 孤儿进程 """
        logger.info("正在安全关闭 Arq Worker 子进程...")
        worker_process.terminate()
        worker_process.join(timeout=3)  # 等待最多 3 秒让它处理后事
        if worker_process.is_alive():  # 超时仍未退出则强制击杀
            worker_process.kill()
        logger.info("Arq Worker 进程已成功退出.")


    atexit.register(cleanup_worker)

    # 启动 Uvicorn 主进程
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)
