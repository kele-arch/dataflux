# -- coding: utf-8 --
# @Author: 胡H
# @File: app/models/otherModel.py
# @Created: 2026/3/2 15:33
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 其他杂项模型 (如日志等)
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text

from app.core.config import settings
from app.db.base import Base


def generate_uuid() -> str:
    """ 生成 32 位无短横线的 UUID 字符串 """
    return uuid.uuid4().hex


class SysLog(Base):
    """ 系统操作日志表
    由于日志表可能有自己独立的逻辑结构 不继承 BaseModelMixin 需手动定义
    """
    __tablename__ = "sys_oper_log"
    __table_args__ = {'comment': '系统操作日志表', 'schema': settings.DB_SCHEMA}

    # 日志表也使用 UUID
    id = Column(String(32), primary_key=True, default=generate_uuid, comment="主键ID(UUID)")

    title = Column(String(50), nullable=True, comment="模块标题")
    business_type = Column(Integer, nullable=True, comment="业务类型 (如: 1新增 2修改 3删除)")
    oper_name = Column(String(50), nullable=True, comment="操作人员")
    oper_ip = Column(String(50), nullable=True, comment="主机地址")
    oper_param = Column(Text, nullable=True, comment="请求参数")
    json_result = Column(Text, nullable=True, comment="返回参数")
    status = Column(Integer, default=0, comment="操作状态 (0正常 1异常)")
    error_msg = Column(Text, nullable=True, comment="错误消息")
    oper_time = Column(DateTime, default=datetime.now, comment="操作时间")
