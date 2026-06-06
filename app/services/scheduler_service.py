# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/scheduler_service.py
# @Created: 2026/6/6 10:06
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 调度服务: 负责根据数据库中的定时任务配置, 使用 APScheduler 定时触发任务执行. 任务触发后, 将任务 ID 推入 ARQ 队列, 由 Worker 后台执行真正的业务逻辑.

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.session import SessionLocal
from app.core import arq_pool as arq_module
from app.core import logger
from app.models.collectTaskModel import CollectTask

# 初始化 AsyncIOScheduler
scheduler = AsyncIOScheduler()


async def trigger_task_to_arq(task_id: str):
    """
    时间一到, 不执行业务, 直接把 task_id 扔进 ARQ 队列 
    """
    if arq_module.arq_pool:
        # 'run_sync_job' 是要在 worker 里注册的函数名
        await arq_module.arq_pool.enqueue_job('run_sync_job', task_id)
        logger.info(f"定时器触发: 任务 [{task_id}] 已推入 ARQ 执行队列")
    else:
        logger.error("ARQ 连接池未初始化, 无法下发任务")


def refresh_scheduler_jobs():
    """
    读取数据库最新配置, 更新调度器
    """
    db = SessionLocal()
    try:
        # 清空现有的所有调度任务 (暴力但最安全、防内存泄漏的做法)
        scheduler.remove_all_jobs()

        # 查找所有启用且配置了 cron 的任务
        stmt = select(CollectTask).where(
            CollectTask.status == 1,
            CollectTask.schedule_cron.isnot(None),
            CollectTask.schedule_cron != ""
        )
        tasks = db.execute(stmt).scalars().all()

        count = 0
        for task in tasks:
            try:
                # 解析 crontab 表达式 (例如: "0 2 * * *")
                trigger = CronTrigger.from_crontab(task.schedule_cron)

                # 将任务添加到调度器, 指定 id 方便追踪
                scheduler.add_job(
                    trigger_task_to_arq,
                    trigger=trigger,
                    args=[task.id],
                    id=f"job_{task.id}",
                    replace_existing=True
                )
                count += 1
            except Exception as e:
                logger.error(f"任务 [{task.id}] 的 Cron 表达式解析失败: {e}")

        logger.info(f"调度器刷新完成, 当前共有 {count} 个活跃定时任务")
    finally:
        db.close()
