# -- coding: utf-8 --
# @Author: 胡H
# @File: collectRecordModel.py
# @Created: 2026/6/5 9:45
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.bashModel import BaseModelMixin
from app.core.config import settings
from typing import Any


class CollectRecord(Base, BaseModelMixin):
    __tablename__ = "sys_collect_record"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "异构原始数据落地表"},
    )

    task_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="是由哪个采集任务采回来的")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="来源类型(冗余字段方便查询)")

    # SA 2.0 中 JSON 对应的 Python 类型通常用 dict 或 list，更宽泛可以用 Any
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, comment="完整的异构数据载体")

    def __repr__(self) -> str:
        return f"<CollectRecord(source_type={self.source_type}, task_id={self.task_id})>"
