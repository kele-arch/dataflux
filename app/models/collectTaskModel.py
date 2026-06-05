# -- coding: utf-8 --
# @Author: 胡H
# @File: collectTaskModel.py
# @Created: 2026/6/5 9:47
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import String, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.bashModel import BaseModelMixin
from app.core.config import settings


class CollectTask(Base, BaseModelMixin):
    __tablename__ = "sys_collect_task"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "数据采集任务定义表"},
    )

    task_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="任务名称")

    # 完整的 SA2.0 逻辑关联
    source_id: Mapped[str] = mapped_column(String(32), comment="关联的数据源ID")

    topic_or_table: Mapped[str] = mapped_column(String(100), nullable=False, comment="目标表名或MQTT Topic")
    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True,
                                                      comment="定时任务表达式，为空则表示常驻流式任务")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="任务状态：0停用, 1启用")

    sync_mode: Mapped[str] = mapped_column(String(20), default="overwrite", comment="冲突策略: insert, overwrite, skip")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")

    sync_tables: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="指定同步表")

    # 采集模式：full(全量), inc_id(自增列), inc_time(时间戳), custom_sql(自定义SQL)
    collect_mode: Mapped[str] = mapped_column(String(20), default="full")

    # 增量依赖的字段名 (如 "id" 或 "update_time")
    incremental_column: Mapped[str | None] = mapped_column(String(50))

    # 水位线记录 (上次采集的最大值)
    last_watermark: Mapped[str | None] = mapped_column(String(255))

    # 用户自定义的 SQL 语句
    custom_sql: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<CollectTask(task_name={self.task_name}, status={self.status})>"
