# -- coding: utf-8 --
# @Author: 胡H
# @File: app/main.py
# @Created: 2025/11/19 10:03
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: man!!!

import os
import sys
import asyncio

from app.services.rabbitmq_manager import _build_rabbitmq_req, rabbitmq_manager

# region 解决 Windows 平台 asyncio 事件循环兼容问题
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )
# endregion

from app.services.mqtt_manager import mqtt_manager

# region 解除高并发线程池限制
os.environ["ANYIO_MAX_THREADS"] = "150"  # 强制扩大 FastAPI 底层同步线程池
# endregion

import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.mongo import init_mongo, close_mongo
from app.core.influx_client import init_influx, close_influx
from app.core.redis import close_redis, init_redis
from app.db.session import init_db, engine, SessionLocal
from app.core.config import settings
from app.core import logger, project_rootpath
from app.middleware import init_middlewares
from app.core.arq_pool import init_arq_pool, close_arq_pool
from app.services.scheduler_service import scheduler, refresh_scheduler_jobs
from app.services.kafka_manager import kafka_manager, _build_kafka_req


async def start_all_kafka_tasks():
    """
    启动所有状态为 1 的 Kafka 任务
    """
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.models.collectTaskModel import CollectTask
    from app.models.dataSourceModel import DataSource
    from app.schemas.tsync import DBSyncReq
    from app.core import logger

    db = SessionLocal()
    try:
        # 通过 JOIN 关联 DataSource 表,过滤 DataSource.type == 'kafka'
        results = db.execute(
            select(CollectTask, DataSource)
            .join(DataSource, CollectTask.source_id == DataSource.id)
            .where(
                DataSource.type == "kafka",
                CollectTask.status == 1
            )
        ).all()

        for task, source in results:
            req = DBSyncReq(
                task_id=task.id,
                db_type="kafka",
                host=source.host if source else "",
                port=source.port if source else 0,
                username="", password="", db_name="",
                target_table=task.topic_or_table,
                kafka_bootstrap_servers=task.kafka_bootstrap_servers,
                kafka_topic=task.kafka_topic,
                kafka_group_id=task.kafka_group_id,
                kafka_auto_offset_reset=task.kafka_auto_offset_reset,
                kafka_batch_size=task.kafka_batch_size,
                kafka_batch_timeout_ms=task.kafka_batch_timeout_ms,
                kafka_value_format=task.kafka_value_format,
            )
            await kafka_manager.start(req)
            logger.info(f"启动时自动拉起 Kafka 任务: {task.id} ({task.kafka_topic})")

    except Exception as e:
        logger.error(f"启动自动拉起 Kafka 任务失败: {e}")
    finally:
        db.close()


async def start_all_mqtt_tasks():
    """
    启动所有状态为 1 的 MQTT 任务
    """
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.models.collectTaskModel import CollectTask
    from app.models.dataSourceModel import DataSource
    from app.services.mqtt_manager import mqtt_manager, _build_mqtt_req
    from app.core import logger

    db = SessionLocal()
    try:
        # 必须关联 sys_data_source 表过滤 type,因为 CollectTask 没有物理的 db_type 字段
        tasks = db.execute(
            select(CollectTask)
            .join(DataSource, CollectTask.source_id == DataSource.id)
            .where(
                DataSource.type == "mqtt",
                CollectTask.status == 1
            )
        ).scalars().all()

        for task in tasks:
            req = _build_mqtt_req(task)
            await mqtt_manager.start(req)
            logger.info(f"启动时自动拉起 MQTT 任务: {task.id} ({task.mqtt_topic})")
    finally:
        db.close()


async def start_all_rabbitmq_tasks():
    """
    启动所有状态为 1 的 RabbitMQ 任务
    """
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.models.collectTaskModel import CollectTask
    from app.models.dataSourceModel import DataSource

    db = SessionLocal()
    try:
        # JOIN DataSource 过滤类型（沿用 Kafka/MQTT 的修复方式）
        tasks = db.execute(
            select(CollectTask)
            .join(DataSource, CollectTask.source_id == DataSource.id)
            .where(
                DataSource.type == "rabbitmq",
                CollectTask.status == 1
            )
        ).scalars().all()

        for task in tasks:
            req = _build_rabbitmq_req(task)
            await rabbitmq_manager.start(req)
            logger.info(f"启动时自动拉起 RabbitMQ 任务: {task.id} ({task.mq_queue})")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ 后端启动前与启动后的工作
    :param app:
    :return:
    """
    logger.info(r"""
    ================================================================================

    ██████╗  █████╗ ████████╗█████╗ ███████╗██╗     ██╗   ██╗██╗  ██╗
    ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔════╝██║     ██║   ██║╚██╗██╔╝
    ██║  ██║███████║   ██║   ███████║█████╗  ██║     ██║   ██║ ╚███╔╝ 
    ██║  ██║██╔══██║   ██║   ██╔══██║██╔══╝  ██║     ██║   ██║ ██╔██╗ 
    ██████╔╝██║  ██║   ██║   ██║  ██║██║     ███████╗╚██████╔╝██╔╝ ██╗
    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝

                                  数 据 采 集 平 台

    ================================================================================
    """)

    # region 许可验证
    if settings.ENABLE_LICENSE:
        from app.core.license import check_license
        if not check_license():
            logger.error("许可验证未通过，程序终止启动")
            import sys
            sys.exit(1)
    # endregion
    # 记录启动开始时间
    start_time = time.time()
    start_dt = datetime.now()
    logger.info(f"平台开始启动 | 时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} | 时间戳: {start_time:.3f}")

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

    # 系统启动时自动清洗因宕机残留的僵尸日志 (pending/running → failed)
    try:
        from app.models.taskLogModel import TaskLog as _TaskLog
        from sqlalchemy import update as _update
        _db = SessionLocal()
        _result = _db.execute(
            _update(_TaskLog)
            .where(_TaskLog.status.in_(["pending", "running"]))
            .values(status="failed", end_time=datetime.now(),
                    error_msg="系统重启，未正常结束的任务被自动判定为异常终止")
        )
        _db.commit()
        if _result.rowcount > 0:
            logger.warning(f"发现并清理了 {_result.rowcount} 条因服务重启卡死的僵尸任务日志")
        _db.close()
    except Exception as e:
        logger.warning(f"僵尸任务清洗失败(已忽略): {e}")

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

    # 启动时自动拉起 Kafka 任务
    try:
        await start_all_kafka_tasks()
    except Exception as e:
        logger.error(f"Kafka 常驻任务拉起失败! (已安全跳过,后续任务可能无法启动): {e}")

    # 启动时自动拉起 MQTT 任务
    try:
        await start_all_mqtt_tasks()
    except Exception as e:
        logger.error(f"MQTT 常驻任务拉起失败! (已安全跳过,后续任务可能无法启动): {e}")

    # 启动时自动拉起 RabbitMQ 任务
    try:
        await start_all_rabbitmq_tasks()
    except Exception as e:
        logger.error(f"RabbitMQ 常驻任务拉起失败! (已安全跳过,后续任务可能无法启动): {e}")

    # yield 前记录启动完成时间
    end_time = time.time()
    elapsed = end_time - start_time
    logger.success(
        f"dataflux 工程初始化完成 | 启动耗时: {elapsed:.2f}s | 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    yield  # <- 应用开始运行.  yield 之后的代码会在应用关闭时执行
    # 关闭前如果有资源要释放可以写这里(例如关闭数据库连接、Redis 连接等)

    # 关闭 Kafka 任务
    await kafka_manager.stop_all()

    # 关闭 MQTT 任务
    await mqtt_manager.stop_all()

    # 关闭 RabbitMQ 任务
    await rabbitmq_manager.stop_all()

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
    app = FastAPI(title="数据采集平台", version="1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    # 中间件配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 前端地址 -> ["http://localhost:3000"]
        allow_credentials=True,  # 允许前端携带 Cookie
        allow_methods=["*"],  # 允许的 HTTP 请求方法列表 -> GET POST PUT...
        allow_headers=["*"],  # 允许的 HTTP 请求头列表 -> Content-Type Authorization...
    )
    init_middlewares(app)  # 注册中间件

    app.mount("/static", StaticFiles(directory=Path(project_rootpath, "static")), name="static")  # 挂载静态文件目录

    # 自定义 Swagger UI 路由
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="自定义接口文档",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
            swagger_favicon_url="/static/favicon.png",
        )

    # 自定义 ReDoc 路由
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title="自定义接口文档",
            redoc_js_url="/static/redoc.standalone.js",
            redoc_favicon_url="/static/favicon.png",
        )

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
    # uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)
    uvicorn.run(
        app=app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
        loop="none"  # 禁用 uvicorn 内置的事件循环管理, 完全接管事件循环的创建和运行 (为了兼容 Windows)
    )

    # # 启动 Uvicorn 主进程
    # # 完全绕开 uvicorn.run() 的封装魔法,手动接管事件循环
    # config = uvicorn.Config(app=app, host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)
    # server = uvicorn.Server(config)
    #
    # if sys.platform == "win32":
    #     logger.info("检测到 Windows 环境，强制注入 SelectorEventLoop...")
    #     loop = asyncio.SelectorEventLoop()
    #     asyncio.set_event_loop(loop)
    #     try:
    #         loop.run_until_complete(server.serve())
    #     finally:
    #         loop.close()
    # else:
    #     logger.info("检测到非 Windows 环境, 使用标准 asyncio.run 启动...")
    #     asyncio.run(server.serve())
