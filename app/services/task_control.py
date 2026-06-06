# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/task_control.py
# @Created: 2026/6/6 17:07
# @LastModified: 2026/6/5
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务控制服务 (Redis 懒加载连接池)
# 提供任务状态控制 (暂停/取消/恢复) 和水位线存储

import redis
from app.core.config import settings

# ConnectionPool 在导入时不会发起 Socket 连接, 消除启动崩溃风险
redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

TASK_RUNNING = "running"
TASK_PAUSED = "paused"
TASK_CANCELLED = "cancelled"


def _get_redis():
    """按需获取 Redis 实例"""
    return redis.Redis(connection_pool=redis_pool)


def set_task_status(task_id: str, status: str, ex: int = 86400):
    """设置任务运行状态标记, 24 小时自动过期防死锁"""
    _get_redis().set(f"task_control:{task_id}", status, ex=ex)


def get_task_status(task_id: str) -> str:
    """获取任务当前控制状态, 不存在则默认为 running"""
    return _get_redis().get(f"task_control:{task_id}") or TASK_RUNNING


def save_watermark(task_id: str, watermark):
    """保存断点水位线, 24 小时自动过期"""
    if watermark is not None:
        _get_redis().set(f"task:{task_id}:watermark", str(watermark), ex=86400)


def get_saved_watermark(task_id: str):
    """获取已保存的断点水位线"""
    return _get_redis().get(f"task:{task_id}:watermark")
