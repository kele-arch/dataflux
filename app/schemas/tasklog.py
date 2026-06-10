# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tasklog.py
# @Created: 2026/6/5 15:54
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from app.schemas.base import BaseDecryptReq


class LogPageQueryReq(BaseDecryptReq):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    task_id: Optional[str] = Field(default=None, description="按任务ID过滤,不传则查全量")
    task_name: Optional[str] = Field(default=None, description="按任务名模糊搜索")
    status: Optional[str] = Field(default=None, description="状态过滤: running, success, failed")
    sort_by: Optional[Literal["start_time", "end_time", "task_name"]] = Field(default="start_time", description="排序字段")
    sort_order: Optional[Literal["asc", "desc"]] = Field(default="desc", description="排序方向")


class TaskLogOut(BaseModel):
    """列表页单条日志（不含 detail_json，轻量）"""
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


class TaskLogDetailOut(TaskLogOut):
    """日志详情（继承列表项，增加 detail_json）"""
    detail_json: Optional[Dict[str, Any]] = None


class TaskLogPageOut(BaseModel):
    total: int
    items: List[TaskLogOut]
    model_config = ConfigDict(from_attributes=True)
