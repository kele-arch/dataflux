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
from app.models.taskLogModel import TaskLog, SyncExecutionLog
from app.services.engine_factory import EngineFactory
from app.core import logger
from app.schemas.tsync import DBSyncReq


async def run_sync_job(ctx, task_id: str):
    """
    数据同步独立后台任务: 由 arq Worker 调度执行 (附带 Redis 分布式排他锁)
    """
    # 从 ARQ 上下文中提取异步 Redis 客户端
    redis = ctx['redis']
    lock_key = f"sync_task_lock:{task_id}"

    # 获取分布式锁 (nx=True 防止并发覆盖, ex=7200 设置 2 小时硬过期防死锁)
    acquired = await redis.set(lock_key, "locked", nx=True, ex=7200)
    if not acquired:
        logger.warning(f"防抖拦截: 任务 [{task_id}] 正在执行中, 已静默丢弃本次重复下发指令！")
        return

    logger.info(f"任务 [{task_id}] 成功获取分布式锁, 准备启动同步流程...")

    # 提前声明变量, 防止在 try 块抛异常后 finally 找不到报错
    db = None
    task_log = None
    start_time = time.time()

    try:
        db = SessionLocal()  # 拿到锁之后, 再真正开启数据库连接
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
            table_mapping=task.table_mapping,
            sync_mode=task.sync_mode,
            collect_mode=task.collect_mode,
            incremental_column=task.incremental_column,
            last_watermark=task.last_watermark,
            custom_sql=task.custom_sql,
            target_type=task.target_type or "postgresql",
            target_host=(task.target_host or source.host) if task.target_type == "mongodb" else None,
            target_port=(task.target_port or source.port) if task.target_type == "mongodb" else None,
            target_username=(task.target_username or source.username) if task.target_type == "mongodb" else None,
            target_password=(task.target_password or source.password) if task.target_type == "mongodb" else None,
            target_db_name=(task.target_db_name or settings.MONGO_DB_NAME) if task.target_type == "mongodb" else None
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
            engine = EngineFactory.create(sync_req)  # 一行搞定路由
            return engine.main()

        result = await asyncio.to_thread(_execute)

        # 获取真实运行状态
        job_status = result.get("status", "success")

        # 如果被中断或取消, 立刻更新日志并安全退出
        if job_status in ["paused", "cancelled"]:
            task_log.status = job_status
            task_log.end_time = datetime.now()
            task_log.error_msg = result.get("message", f"任务已响应中断指令: {job_status}")
            db.commit()
            logger.warning(f"任务 [{task_id}] 提前终止, 状态更新为: {job_status}")
            return

        # 更新 TaskLog + 水位线
        new_watermark = result.get("new_watermark")
        old_watermark = task.last_watermark
        if new_watermark:
            task.last_watermark = str(new_watermark)

        # 组装执行详情快照
        detail_json = {
            "sync_mode": sync_req.sync_mode,
            "collect_mode": sync_req.collect_mode,
            "incremental_column": sync_req.incremental_column,
            "source_type": sync_req.db_type,
            "source_db": sync_req.db_name,
            "watermark_before": old_watermark,
            "watermark_after": str(new_watermark) if new_watermark else None,
            "tables": result.get("table_details", [])
        }

        # 构建表级执行日志（映射流水）
        table_details = result.get("table_details", [])
        execution_logs = []
        for detail in table_details:
            execution_logs.append(SyncExecutionLog(
                log_id=task_log.id,
                task_id=task.id,
                source_table=detail.get("name", "unknown"),
                target_table=detail.get("target_name", detail.get("name", "unknown")),
                sync_mode=sync_req.sync_mode,
                collect_mode=sync_req.collect_mode,
                records_count=detail.get("records", 0),
                cost_seconds=detail.get("cost_seconds", 0),
                watermark=detail.get("high_watermark"),
                status="success"
            ))

        if execution_logs:
            db.add_all(execution_logs)

        task_log.status = "success"

        task_log.end_time = datetime.now()
        task_log.tables_synced = result.get("tables_synced", 0)
        task_log.total_records = result.get("total_records", 0)
        task_log.detail_json = detail_json
        db.commit()

        logger.info(f"Worker 同步完成: {task_id}, 耗时 {int(time.time() - start_time)}s")

    except asyncio.CancelledError:
        logger.error(f"Worker 超时被杀: {task_id}")
        if task_log and db:
            task_log.status = "failed"
            task_log.end_time = datetime.now()
            task_log.error_msg = "任务超时被强杀"
            db.commit()

    except Exception as e:
        logger.error(f"Worker 同步失败: {task_id}, Error: {e}")
        if task_log and db:
            try:
                task_log.status = "failed"
                task_log.end_time = datetime.now()
                task_log.error_msg = str(e)[:2000]
                db.commit()
            except Exception:
                db.rollback()

    finally:
        # 关闭数据库连接
        if db:
            db.close()

        # 安全释放分布式锁 (无论报错与否, 确保锁被回收)
        await redis.delete(lock_key)
        logger.info(f"任务 [{task_id}] 已安全释放排他锁")


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
