# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/task_operations.py
# @Created: 2026/7/28 11:50
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务预检、数据预览、水位线、补数与失败重试接口

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import arq_pool as arq_module
from app.core import logger
from app.crud.crud_tsync import crud_task
from app.db.session import get_db
from app.models.dataSourceModel import DataSource
from app.models.taskLogModel import TaskLog
from app.schemas.response import BaseResponse
from app.schemas.task_operations import (
    BackfillReq,
    RetryFailedReq,
    TaskOperationReq,
    TaskPreviewReq,
    WatermarkResetReq,
)
from app.services.task_preflight import task_preflight_service


router = APIRouter(prefix="/tsync", tags=["任务预检与恢复"])


def _get_task_and_source(db: Session, task_id: str):
    task = crud_task.get_by_id(db, task_id)
    if not task:
        return None, None
    source = db.execute(
        select(DataSource).where(DataSource.id == task.source_id)
    ).scalar_one_or_none()
    return task, source


async def _queue_available(task_id: str) -> tuple[bool, str]:
    if arq_module.arq_pool is None:
        return False, "系统队列服务未就绪"
    if await arq_module.arq_pool.exists(f"sync_task_lock:{task_id}"):
        return False, "任务正在执行中，不能重复入队"
    if await arq_module.arq_pool.exists(f"sync_enqueue_lock:{task_id}"):
        return False, "任务正在入队中，请勿重复操作"
    return True, ""


async def _enqueue_task(
    db: Session,
    task,
    operation: str,
    context: dict | None = None,
) -> tuple[bool, str, TaskLog | None]:
    available, message = await _queue_available(task.id)
    if not available:
        return False, message, None
    if task.status == 0:
        return False, "任务处于停用状态，无法执行", None

    enqueue_key = f"sync_enqueue_lock:{task.id}"
    reserved = await arq_module.arq_pool.set(enqueue_key, "1", nx=True, ex=600)
    if not reserved:
        return False, "任务正在入队中，请勿重复操作", None

    pending_log = TaskLog(
        task_id=task.id,
        task_name=task.task_name,
        status="pending",
        start_time=datetime.now(),
        detail_json={"operation": operation, **(context or {})},
    )
    enqueued = False
    try:
        db.add(pending_log)
        db.commit()
        db.refresh(pending_log)
        await arq_module.arq_pool.set(f"task_control:{task.id}", "running", ex=86400)
        job = await arq_module.arq_pool.enqueue_job("run_sync_job", task.id)
        if job is None:
            raise RuntimeError("ARQ 拒绝了入队请求")
        enqueued = True
        return True, "任务已进入执行队列", pending_log
    except Exception as exc:
        db.rollback()
        if pending_log.id:
            try:
                failed_log = db.get(TaskLog, pending_log.id)
                if failed_log:
                    failed_log.status = "failed"
                    failed_log.end_time = datetime.now()
                    failed_log.error_msg = f"入队失败: {exc}"
                    db.commit()
            except Exception:
                db.rollback()
        logger.error(f"任务 [{task.id}] {operation} 入队失败: {exc}")
        await arq_module.arq_pool.delete(f"task_control:{task.id}")
        return False, f"入队失败: {exc}", pending_log
    finally:
        if not enqueued:
            await arq_module.arq_pool.delete(enqueue_key)


@router.post("/validate", summary="任务配置预检", response_model=BaseResponse)
async def validate_task(req: TaskOperationReq, db: Session = Depends(get_db)):
    task, source = _get_task_and_source(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    if not source:
        return BaseResponse(code=0, msg="任务关联的数据源不存在")

    result = await asyncio.to_thread(task_preflight_service.validate, task, source)
    return BaseResponse(
        code=1 if result["valid"] else 0,
        data=result,
        msg="预检通过" if result["valid"] else "预检未通过",
    )


@router.post("/preview", summary="任务源数据预览", response_model=BaseResponse)
async def preview_task(req: TaskPreviewReq, db: Session = Depends(get_db)):
    task, source = _get_task_and_source(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    if not source:
        return BaseResponse(code=0, msg="任务关联的数据源不存在")

    try:
        result = await asyncio.to_thread(
            task_preflight_service.preview,
            task,
            source,
            req.table_name,
            req.limit,
        )
        return BaseResponse(
            code=1 if result.get("supported") else 0,
            data=result,
            msg="预览成功" if result.get("supported") else result.get("message", "该类型暂不支持预览"),
        )
    except Exception as exc:
        logger.error(f"任务 [{req.task_id}] 数据预览失败: {exc}")
        return BaseResponse(code=0, msg=f"预览失败: {str(exc)}")


@router.post("/watermark/get", summary="查询任务水位线", response_model=BaseResponse)
def get_watermark(req: TaskOperationReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    return BaseResponse(
        data={
            "task_id": task.id,
            "collect_mode": task.collect_mode,
            "incremental_column": task.incremental_column,
            "last_watermark": task.last_watermark,
        },
        msg="获取成功",
    )


@router.post("/watermark/reset", summary="重置任务水位线", response_model=BaseResponse)
async def reset_watermark(req: WatermarkResetReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    if task.collect_mode not in ("inc_id", "inc_time"):
        return BaseResponse(code=0, msg="只有 inc_id/inc_time 增量任务支持重置水位线")
    available, message = await _queue_available(task.id)
    if not available:
        return BaseResponse(code=0, msg=message)

    old_watermark = task.last_watermark
    new_watermark = (req.watermark or "").strip() or None
    task.last_watermark = new_watermark
    db.commit()
    if arq_module.arq_pool is not None:
        await arq_module.arq_pool.delete(f"task:{task.id}:watermark")

    return BaseResponse(
        data={
            "task_id": task.id,
            "watermark_before": old_watermark,
            "watermark_after": new_watermark,
        },
        msg="水位线已重置",
    )


@router.post("/backfill", summary="按起始水位线补数并执行", response_model=BaseResponse)
async def backfill_task(req: BackfillReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    if task.collect_mode not in ("inc_id", "inc_time"):
        return BaseResponse(code=0, msg="只有 inc_id/inc_time 增量任务支持水位线补数")

    available, message = await _queue_available(task.id)
    if not available:
        return BaseResponse(code=0, msg=message)

    old_watermark = task.last_watermark
    start_watermark = (req.start_watermark or "").strip() or None
    task.last_watermark = start_watermark
    db.commit()
    if arq_module.arq_pool is not None:
        await arq_module.arq_pool.delete(f"task:{task.id}:watermark")

    ok, message, pending_log = await _enqueue_task(
        db,
        task,
        "backfill",
        {
            "watermark_before": old_watermark,
            "backfill_start_watermark": start_watermark,
            "reason": req.reason,
        },
    )
    if not ok:
        task.last_watermark = old_watermark
        db.commit()
        return BaseResponse(code=0, msg=message)

    return BaseResponse(
        data={
            "task_id": task.id,
            "log_id": pending_log.id,
            "watermark_before": old_watermark,
            "backfill_start_watermark": start_watermark,
            "status": "pending",
        },
        msg="补数任务已进入执行队列",
    )


@router.post("/retry", summary="重试失败的任务执行", response_model=BaseResponse)
async def retry_failed_task(req: RetryFailedReq, db: Session = Depends(get_db)):
    failed_log = db.execute(
        select(TaskLog).where(TaskLog.id == req.log_id)
    ).scalar_one_or_none()
    if not failed_log:
        return BaseResponse(code=0, msg="原执行日志不存在")
    if failed_log.status != "failed":
        return BaseResponse(code=0, msg=f"只有 failed 日志可以重试，当前状态为 {failed_log.status}")

    task = crud_task.get_by_id(db, failed_log.task_id)
    if not task:
        return BaseResponse(code=0, msg="原任务已不存在，无法重试")
    source = db.execute(
        select(DataSource).where(DataSource.id == task.source_id)
    ).scalar_one_or_none()
    if source and source.type.lower() in ("kafka", "mqtt", "rabbitmq"):
        return BaseResponse(code=0, msg="常驻消息任务请使用对应的 start 接口重新启动")

    ok, message, pending_log = await _enqueue_task(
        db,
        task,
        "retry",
        {"retry_of_log_id": failed_log.id, "reason": req.reason},
    )
    if not ok:
        return BaseResponse(code=0, msg=message)
    return BaseResponse(
        data={
            "task_id": task.id,
            "log_id": pending_log.id,
            "retry_of_log_id": failed_log.id,
            "status": "pending",
        },
        msg="失败任务已重新进入执行队列",
    )
