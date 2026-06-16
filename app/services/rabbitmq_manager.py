# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/rabbitmq_manager.py
# @Created: 2026/6/16 21:49
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: RabbitMQ Consumer 常驻任务管理器

import asyncio
from app.core import logger
from app.schemas.tsync import DBSyncReq
from app.services.rabbitmq_sync_engine import RabbitMQSyncEngine
from app.models.collectTaskModel import CollectTask


class RabbitMQConsumerManager:

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    async def start(self, req: DBSyncReq) -> bool:
        task_id = str(req.task_id)
        if self.is_running(task_id):
            # 可能是 stop_event 已设置、旧 Task 正在清理中的状态——等它结束
            old_stop = self._stop_events.get(task_id)
            if old_stop and old_stop.is_set():
                old_task = self._tasks.get(task_id)
                if old_task:
                    try:
                        await asyncio.wait_for(old_task, timeout=5)
                    except (asyncio.TimeoutError, Exception):
                        old_task.cancel()
                self._tasks.pop(task_id, None)
                self._stop_events.pop(task_id, None)
            else:
                logger.warning(f"[{task_id}] RabbitMQ Consumer 已在运行，跳过启动")
                return False

        stop_event = asyncio.Event()
        engine = RabbitMQSyncEngine(req)

        async def _wrapped():
            try:
                await engine.run(stop_event)
            except Exception as e:
                logger.error(f"[{task_id}] RabbitMQ Consumer 异常退出: {e}")
            finally:
                self._tasks.pop(task_id, None)
                self._stop_events.pop(task_id, None)

        task = asyncio.create_task(_wrapped())
        self._tasks[task_id] = task
        self._stop_events[task_id] = stop_event

        logger.info(f"[{task_id}] RabbitMQ Consumer 任务已创建")
        return True

    async def stop(self, task_id: str, timeout: int = 10) -> bool:
        if not self.is_running(task_id):
            logger.warning(f"[{task_id}] RabbitMQ Consumer 未在运行")
            return False

        stop_event = self._stop_events.get(task_id)
        if stop_event:
            stop_event.set()

        # 不等待、不 cancel——aio_pika 的 connection.close() 在关闭时可能卡住，
        # 强行 wait_for + cancel 只会让 loop.run_until_complete() 永远等不到返回。
        # 进程退出时 OS 自然会回收底层连接。
        return True

    async def stop_all(self):
        for task_id in list(self._tasks.keys()):
            await self.stop(task_id)

    def status(self, task_id: str) -> str:
        if not self.is_running(task_id):
            return "stopped"
        # stop_event 已设置 = 正在优雅退出中 = 前端应显示为已停止
        stop_event = self._stop_events.get(task_id)
        if stop_event and stop_event.is_set():
            return "stopped"
        return "running"


def _build_rabbitmq_req(task: CollectTask) -> DBSyncReq:
    """将 CollectTask 转换为 RabbitMQ 引擎所需的 DBSyncReq"""
    return DBSyncReq(
        task_id=task.id,
        db_type="rabbitmq",
        host=task.mq_host or "",
        port=task.mq_port or 5672,
        username="guest",
        password="guest",
        db_name="",
        target_table=task.topic_or_table,
        mq_host=task.mq_host,
        mq_port=task.mq_port,
        mq_vhost=task.mq_vhost,
        mq_queue=task.mq_queue,
        mq_exchange=task.mq_exchange,
        mq_exchange_type=task.mq_exchange_type,
        mq_routing_key=task.mq_routing_key,
        mq_durable=bool(task.mq_durable),
        mq_prefetch_count=task.mq_prefetch_count,
        mq_batch_size=task.mq_batch_size,
        mq_batch_timeout_ms=task.mq_batch_timeout_ms,
        mq_value_format=task.mq_value_format,
    )


rabbitmq_manager = RabbitMQConsumerManager()
