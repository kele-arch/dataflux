# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/kafka_manager.py
# @Created: 2026/6/13 11:48
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Kafka Consumer 常驻任务管理器 start/stop/status

import asyncio
from app.core import logger
from app.models.collectTaskModel import CollectTask
from app.schemas.tsync import DBSyncReq
from app.services.kafka_sync_engine import KafkaSyncEngine


def _build_kafka_req(task: CollectTask) -> DBSyncReq:
    """
    将 CollectTask 转换为 Kafka 引擎所需的 DBSyncReq
    Kafka 任务的连接信息直接存在 task.kafka_bootstrap_servers, 
    不依赖 DataSource(数据库类数据源才需要host/port/账号密码)
    """
    return DBSyncReq(
        task_id=task.id,
        db_type="kafka",

        # DBSyncReq 里这几个是必填字段, Kafka场景用不到, 给空值占位
        host="",
        port=0,
        username="",
        password="",
        db_name="",

        target_table=task.topic_or_table,

        kafka_bootstrap_servers=task.kafka_bootstrap_servers,
        kafka_topic=task.kafka_topic,
        kafka_group_id=task.kafka_group_id,
        kafka_auto_offset_reset=task.kafka_auto_offset_reset,
        kafka_batch_size=task.kafka_batch_size,
        kafka_batch_timeout_ms=task.kafka_batch_timeout_ms,
        kafka_value_format=task.kafka_value_format,
    )


class KafkaConsumerManager:
    """
    管理所有 Kafka 任务的常驻 Consumer 协程
    每个 task_id 对应一个 (asyncio.Task, asyncio.Event) 二元组
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    async def start(self, req: DBSyncReq):
        task_id = str(req.task_id)

        if self.is_running(task_id):
            logger.warning(f"[{task_id}] Kafka Consumer 已在运行, 跳过启动")
            return False

        stop_event = asyncio.Event()
        engine = KafkaSyncEngine(req)

        async def _wrapped():
            try:
                await engine.run(stop_event)
            except Exception as e:
                logger.error(f"[{task_id}] Kafka Consumer 异常退出: {e}")
            finally:
                self._tasks.pop(task_id, None)
                self._stop_events.pop(task_id, None)

        task = asyncio.create_task(_wrapped())
        self._tasks[task_id] = task
        self._stop_events[task_id] = stop_event

        logger.info(f"[{task_id}] Kafka Consumer 任务已创建")
        return True

    async def stop(self, task_id: str, timeout: int = 30) -> bool:
        if not self.is_running(task_id):
            logger.warning(f"[{task_id}] Kafka Consumer 未在运行")
            return False

        stop_event = self._stop_events.get(task_id)
        if stop_event:
            stop_event.set()  # 通知消费循环优雅退出

        task = self._tasks.get(task_id)
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[{task_id}] Kafka Consumer 停止超时, 强制取消")
            task.cancel()

        return True

    async def stop_all(self):
        for task_id in list(self._tasks.keys()):
            await self.stop(task_id)

    def status(self, task_id: str) -> str:
        return "running" if self.is_running(task_id) else "stopped"


# 全局单例
kafka_manager = KafkaConsumerManager()
