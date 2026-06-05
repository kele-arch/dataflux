# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tasklog.py
# @Created: 2026/6/5 15:54
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.schemas.base import BaseDecryptReq


class LogPageQueryReq(BaseDecryptReq):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    task_id: str = Field(..., description="关联的任务ID,必传")
    status: Optional[str] = Field(default=None, description="状态过滤: running, success, failed")


class TaskLogOut(BaseModel):
    id: str
    task_id: str
    task_name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    tables_synced: int
    total_records: int
    error_msg: Optional[str]

    create_time: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class TaskLogPageOut(BaseModel):
    total: int
    items: List[TaskLogOut]
    model_config = ConfigDict(from_attributes=True)
