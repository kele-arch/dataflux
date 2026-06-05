# -- coding: utf-8 --
# @Author: 胡H
# @File: dataSourceModel.py
# @Created: 2026/6/5 9:46
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from sqlalchemy import String, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.bashModel import BaseModelMixin  # 假设复用你原有的 Mixin
from app.core.config import settings


class DataSource(Base, BaseModelMixin):
    __tablename__ = "sys_data_source"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "数据源配置表"},
    )

    # SA 2.0 语法：使用 Mapped[类型] 和 mapped_column
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="数据源名称，如：产线A_MySQL")
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="数据源类型：mysql, mqtt, kafka, redis")
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="主机地址")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="端口")

    db_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="数据库名称")

    # 可选字段可以标记为 Mapped[str | None] 或 Optional[str] (取决于你的Python版本)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="用户名")
    password: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="密码(建议密文存储)")
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="其他特有配置(如SSL证书路径等)")

    def __repr__(self) -> str:
        return f"<DataSource(name={self.name}, type={self.type})>"