# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/sync_execution_log.py
# @Created: 2026/06/6 20:28
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 表级同步执行日志 Schema
from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.schemas.base import BaseDecryptReq


class ExecLogQueryReq(BaseDecryptReq):
    """ 表级日志查询请求 """
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    task_id: Optional[str] = Field(default=None, description="按任务ID过滤")
    log_id: Optional[str] = Field(default=None, description="按TaskLog ID过滤(某次执行)")
    target_table: Optional[str] = Field(default=None, description="按目标表名过滤")
    status: Optional[str] = Field(default=None, description="按状态过滤: success/failed")


class ExecLogOut(BaseModel):
    """ 表级日志输出 """
    id: str
    log_id: str
    task_id: str
    source_table: str
    target_table: str
    sync_mode: str
    collect_mode: str
    records_count: int
    cost_seconds: float
    watermark: Optional[str]
    status: str
    error_msg: Optional[str]
    create_time: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ExecLogPageOut(BaseModel):
    total: int
    items: List[ExecLogOut]
    model_config = ConfigDict(from_attributes=True)
