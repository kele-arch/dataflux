# -- coding: utf-8 --
# @Author: 胡H
# @File: app/worker.py
# @Created: 2026/6/6 10:07
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Worker 后台任务执行模块: 由 ARQ Worker 调度执行具体的业务逻辑
import asyncio
import time
from datetime import datetime
from urllib.parse import urlparse
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.crud.crud_tsync import crud_task
from app.models.dataSourceModel import DataSource
from app.models.taskLogModel import TaskLog
from app.services.sync_service import DatabaseSyncEngine
from app.core import logger
from app.schemas.tsync import DBSyncReq

async def run_sync_job(ctx, task_id: str):
    """
    数据同步独立后台任务: 由 arq Worker 调度执行
    """
    db = SessionLocal()
    start_time = time.time()

    try:
        logger.info(f"Worker 开始处理数据同步任务: task_id={task_id}")

        # 获取任务配置
        task = crud_task.get_by_id(db, task_id)
        if not task:
            logger.error(f"同步任务 {task_id} 不存在！")
            return

        # 查数据源
        source = db.execute(
            select(DataSource).where(DataSource.id == task.source_id)
        ).scalar_one_or_none()
        if not source:
            logger.error(f"数据源不存在: {task.source_id}")
            return
        db_name = getattr(source, "db_name", None) or (source.config_json or {}).get("db_name")
        if not db_name:
            logger.error(f"数据源缺少 db_name")
            return

        # 拼装 DBSyncReq (引擎唯一识别的 Schema)
        sync_req = DBSyncReq(
            task_id=task.id,
            db_type=source.type,
            host=source.host,
            port=source.port,
            username=source.username,
            password=source.password,
            db_name=db_name,
            target_table=task.topic_or_table,
            sync_tables=task.sync_tables,
            sync_mode=task.sync_mode,
            collect_mode=task.collect_mode,
            incremental_column=task.incremental_column,
            last_watermark=task.last_watermark,
            custom_sql=task.custom_sql
        )

        # 创建 TaskLog 记录运行状态
        task_log = TaskLog(
            task_id=task.id,
            task_name=task.task_name,
            status="running",
            start_time=datetime.now()
        )
        db.add(task_log)
        db.commit()

        # 在线程池中执行同步
        def _execute():
            engine = DatabaseSyncEngine(req=sync_req)  # 移除 db 参数 , 使用默认引擎
            return engine.main()

        result = await asyncio.to_thread(_execute)

        # 更新 TaskLog + 水位线
        new_watermark = result.get("new_watermark")
        if new_watermark:
            task.last_watermark = str(new_watermark)

        task_log.status = "success"
        task_log.end_time = datetime.now()
        task_log.tables_synced = result.get("tables_synced", 0)
        task_log.total_records = result.get("total_records", 0)
        db.commit()

        logger.info(f"Worker 同步完成: {task_id}, 耗时 {int(time.time() - start_time)}s")

    except asyncio.CancelledError:
        logger.error(f"Worker 超时被杀: {task_id}")
    except Exception as e:
        logger.error(f"Worker 同步失败: {task_id}, Error: {e}")
        try:
            task_log.status = "failed"
            task_log.end_time = datetime.now()
            task_log.error_msg = str(e)[:2000]
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


# 解析 Redis 配置
parsed_redis = urlparse(settings.REDIS_URL)
arq_redis_settings = RedisSettings(
    host=parsed_redis.hostname or 'localhost',
    port=parsed_redis.port or 6379,
    password=parsed_redis.password,
    database=int(parsed_redis.path.lstrip('/')) if parsed_redis.path else 0
)


# Arq 启动配置项
class WorkerSettings:
    functions = [run_sync_job]
    redis_settings = arq_redis_settings
    # 同步任务极度消耗数据库连接池,建议并发不要太大
    max_jobs = 3
    # 防止任务假死, 设置一个合理的硬超时时间（2 小时）
    job_timeout = 7200