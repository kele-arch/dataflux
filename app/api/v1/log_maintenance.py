# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/log_maintenance.py
# @Created: 2026/7/28 16:39
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 日志容量统计、清理预览、执行清理与归档导出接口

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import logger
from app.db.session import get_db
from app.schemas.log_maintenance import (
    LogCleanPreviewReq,
    LogCleanReq,
    LogExportReq,
    LogStatsReq,
)
from app.schemas.response import BaseResponse
from app.services.log_maintenance import log_maintenance_service


router = APIRouter(prefix="/log", tags=["日志维护"])


@router.post("/stats", summary="日志容量统计", response_model=BaseResponse)
def get_log_stats(req: LogStatsReq, db: Session = Depends(get_db)):
    try:
        result = log_maintenance_service.stats(db, req.task_id)
        return BaseResponse(data=result, msg="日志容量统计成功")
    except Exception as exc:
        logger.error(f"日志容量统计失败: {exc}")
        return BaseResponse(code=0, msg=f"日志容量统计失败: {exc}")


@router.post("/clean/preview", summary="日志清理预览", response_model=BaseResponse)
def preview_log_clean(req: LogCleanPreviewReq, db: Session = Depends(get_db)):
    try:
        result = log_maintenance_service.clean_preview(db, req)
        return BaseResponse(data=result, msg="日志清理预览成功")
    except Exception as exc:
        logger.error(f"日志清理预览失败: {exc}")
        return BaseResponse(code=0, msg=f"日志清理预览失败: {exc}")


@router.post("/clean", summary="执行日志清理", response_model=BaseResponse)
def clean_logs(req: LogCleanReq, db: Session = Depends(get_db)):
    try:
        result = log_maintenance_service.clean(db, req)
        return BaseResponse(data=result, msg="日志清理完成")
    except Exception as exc:
        db.rollback()
        logger.error(f"日志清理失败: {exc}")
        return BaseResponse(code=0, msg=f"日志清理失败: {exc}")


@router.post("/export", summary="导出任务及表级日志", response_model=BaseResponse)
def export_logs(req: LogExportReq, db: Session = Depends(get_db)):
    try:
        result = log_maintenance_service.export(db, req)
        return BaseResponse(data=result, msg="日志导出成功")
    except Exception as exc:
        logger.error(f"日志导出失败: {exc}")
        return BaseResponse(code=0, msg=f"日志导出失败: {exc}")
