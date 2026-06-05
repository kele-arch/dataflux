# -- coding: utf-8 --
# @Author: 胡H
# @File: collectors.py
# @Created: 2026/6/5 9:55
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from pydantic import BaseModel, Field
from typing import Any, Dict
from datetime import datetime

class CollectDataEvent(BaseModel):
    """
    流转于 采集器 -> Kafka -> 消费者 之间的标准数据事件
    """
    task_id: str = Field(..., description="采集任务ID (对应 sys_collect_task.id)")
    source_type: str = Field(..., description="数据源类型 (mysql, mqtt, etc)")
    topic: str = Field(..., description="细分主题或表名")
    payload: Dict[str, Any] = Field(..., description="真实异构数据体")
    timestamp: datetime = Field(default_factory=datetime.now, description="采集时间")