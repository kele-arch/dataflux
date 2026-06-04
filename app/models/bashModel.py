# -- coding: utf-8 --
# @Author: 胡H
# @File: app/models/baseModel.py
# @Created: 2026/3/2 15:32
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 基础混合类 (提供 UUID 主键及审计字段)
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer


def generate_uuid() -> str:
    """生成 32 位无短横线的 UUID 字符串"""
    return uuid.uuid4().hex


class BaseModelMixin:
    """基础模型混合类
    提供所有业务表通用的基础字段。
    继承此类的模型将自动获得这些列。
    """
    # 使用 String(32) 存储 32位 UUID
    id = Column(String(32), primary_key=True, default=generate_uuid, comment="主键ID(UUID)")

    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    create_by = Column(String(50), nullable=True, comment="创建人姓名/ID")
    is_delete = Column(Integer, nullable=False, default=0, comment="是否删除(0正常 1删除)")
