# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/task_operations.py
# @Created: 2026/7/28 11:50
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务预检、预览、水位线、补数与失败重试请求模型

from typing import Optional

from pydantic import Field

from app.schemas.base import BaseDecryptReq


class TaskOperationReq(BaseDecryptReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务 UUID")


class TaskPreviewReq(TaskOperationReq):
    table_name: Optional[str] = Field(default=None, description="要预览的源表/集合；不传时使用任务配置中的第一张")
    limit: int = Field(default=20, ge=1, le=100, description="预览行数，最多 100")


class WatermarkResetReq(TaskOperationReq):
    watermark: Optional[str] = Field(default=None, description="新水位线；传 null 或空字符串表示清空")


class BackfillReq(TaskOperationReq):
    start_watermark: Optional[str] = Field(
        default=None,
        description="补数起始水位线；传 null 表示从头执行。增量过滤采用大于该值",
    )
    reason: Optional[str] = Field(default=None, max_length=255, description="补数原因")


class RetryFailedReq(BaseDecryptReq):
    log_id: str = Field(..., min_length=32, max_length=32, description="原失败执行日志 UUID")
    reason: Optional[str] = Field(default=None, max_length=255, description="重试原因")
