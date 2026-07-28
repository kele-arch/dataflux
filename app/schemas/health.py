# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/health.py
# @Created: 2026/7/28 11:50
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 服务健康与 Worker 状态检查请求模型

from pydantic import Field

from app.schemas.base import BaseDecryptReq


class HealthCheckReq(BaseDecryptReq):
    timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="单个依赖检查的超时时间（秒）",
    )


class WorkerHealthReq(HealthCheckReq):
    queue_name: str = Field(
        default="arq:queue",
        pattern=r"^[A-Za-z0-9:_-]+$",
        description="ARQ 队列名称",
    )
