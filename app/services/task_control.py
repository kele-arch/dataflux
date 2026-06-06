# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/task_control.py
# @Created: 2026/6/6 10:40
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务控制服务
# 提供接口让 Worker 在执行任务时, 能够查询当前任务的状态 (运行中/暂停/取消) 以及保存和获取任务的水位线 (watermark), 以支持增量同步等功能. 任务状态和水位线信息存储在 Redis 中, 以便快速访问和过期管理

import redis
from app.core.config import settings

sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

TASK_RUNNING = "running"
TASK_PAUSED = "paused"
TASK_CANCELLED = "cancelled"


def set_task_status(task_id: str, status: str, ex: int = 86400):
    sync_redis.set(f"task:{task_id}:status", status, ex=ex)


def get_task_status(task_id: str) -> str:
    return sync_redis.get(f"task:{task_id}:status") or TASK_RUNNING


def save_watermark(task_id: str, watermark):
    if watermark is not None:
        sync_redis.set(f"task:{task_id}:watermark", str(watermark), ex=86400)


def get_saved_watermark(task_id: str):
    return sync_redis.get(f"task:{task_id}:watermark")
