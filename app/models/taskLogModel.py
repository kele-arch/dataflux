# -- coding: utf-8 --
# @Author: 胡H
# @File: app/models/taskLogModel.py
# @Created: 2026/6/5 15:44
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.base import Base
from app.models.bashModel import BaseModelMixin
from app.core.config import settings


class TaskLog(Base, BaseModelMixin):
    __tablename__ = "sys_task_log"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "任务执行历史日志表"},
    )

    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="关联的任务ID")
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="任务名称快照")

    # 状态枚举：running(运行中), success(成功), failed(失败)
    status: Mapped[str] = mapped_column(String(20), default="running", comment="执行状态")

    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="开始时间")
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")

    # 统计数据
    tables_synced: Mapped[int] = mapped_column(Integer, default=0, comment="同步表数量")
    total_records: Mapped[int] = mapped_column(Integer, default=0, comment="同步总条数")

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")