# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/mqtt_manager.py
# @Created: 2026/6/16 9:57
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: MQTT Consumer 常驻任务管理器

import asyncio
from app.core import logger
from app.schemas.tsync import DBSyncReq
from app.services.mqtt_sync_engine import MqttSyncEngine
from app.models.collectTaskModel import CollectTask


class MqttConsumerManager:
    """
    管理所有 MQTT 任务的常驻订阅协程
    每个 task_id 对应一个 (asyncio.Task, asyncio.Event) 二元组
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    async def start(self, req: DBSyncReq) -> bool:
        task_id = str(req.task_id)
        if self.is_running(task_id):
            # stop_event 已设置 = 旧 Task 正在清理中 → 等它结束再启动新的
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
                logger.warning(f"[{task_id}] MQTT Consumer 已在运行, 跳过启动")
                return False

        stop_event = asyncio.Event()
        engine = MqttSyncEngine(req)

        async def _wrapped():
            try:
                await engine.run(stop_event)
            except Exception as e:
                logger.error(f"[{task_id}] MQTT Consumer 异常退出: {e}")
            finally:
                self._tasks.pop(task_id, None)
                self._stop_events.pop(task_id, None)

        task = asyncio.create_task(_wrapped())
        self._tasks[task_id] = task
        self._stop_events[task_id] = stop_event

        logger.info(f"[{task_id}] MQTT Consumer 任务已创建")
        return True

    async def stop(self, task_id: str, timeout: int = 10) -> bool:
        if not self.is_running(task_id):
            logger.warning(f"[{task_id}] MQTT Consumer 未在运行")
            return False

        stop_event = self._stop_events.get(task_id)
        if stop_event:
            stop_event.set()

        # 不等待、不 cancel——aiomqtt 的 __aexit__ 在 Windows 上会卡在
        # paho-mqtt 的同步 socket 清理里, CancelledError 投递不进去, 
        # 强行 wait_for + cancel 只会让 loop.run_until_complete() 永远等不到返回. 
        # 进程退出时 OS 自然会回收底层连接和线程. 
        return True

    async def stop_all(self):
        for task_id in list(self._tasks.keys()):
            await self.stop(task_id)

    def status(self, task_id: str) -> str:
        if not self.is_running(task_id):
            return "stopped"
        stop_event = self._stop_events.get(task_id)
        if stop_event and stop_event.is_set():
            return "stopped"
        return "running"


def _build_mqtt_req(task: CollectTask) -> DBSyncReq:
    """将 CollectTask 转换为 MQTT 引擎所需的 DBSyncReq"""
    return DBSyncReq(
        task_id=task.id,
        db_type="mqtt",
        host=task.mqtt_broker or "",
        port=task.mqtt_port or 1883,
        username="",
        password="",
        db_name="",
        target_table=task.topic_or_table,
        mqtt_broker=task.mqtt_broker,
        mqtt_port=task.mqtt_port,
        mqtt_topic=task.mqtt_topic,
        mqtt_client_id=task.mqtt_client_id,
        mqtt_qos=task.mqtt_qos,
        mqtt_clean_session=bool(task.mqtt_clean_session),
        mqtt_use_tls=bool(task.mqtt_use_tls),
        mqtt_keepalive=task.mqtt_keepalive,
        mqtt_batch_size=task.mqtt_batch_size,
        mqtt_batch_timeout_ms=task.mqtt_batch_timeout_ms,
        mqtt_value_format=task.mqtt_value_format,
    )


mqtt_manager = MqttConsumerManager()
