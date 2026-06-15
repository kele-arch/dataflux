# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/dialects/oracle_dialect.py
# @Created: 2026/6/15 15:53
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Oracle 方言处理器: 类型归一化 + 约束清洗

from sqlalchemy import String, Text, Numeric, Integer, DateTime, Date, LargeBinary
from sqlalchemy.types import NullType
from app.services.dialects.base import BaseDialectHandler


class OracleDialectHandler(BaseDialectHandler):
    """
    Oracle 数据库的方言处理器, 负责将 Oracle 特有的数据类型转换为 SQLAlchemy 的通用类型
    """

    def normalize_type(self, col_type):
        type_name = type(col_type).__name__.upper()
        type_str = str(col_type).upper()

        # VARCHAR2 / NVARCHAR2 ->  String
        if "VARCHAR2" in type_str or "NVARCHAR2" in type_str:
            length = getattr(col_type, "length", None)
            return String(length) if length else Text()

        # CHAR / NCHAR ->  String
        if "CHAR" in type_name:
            length = getattr(col_type, "length", None)
            return String(length) if length else String(255)

        # CLOB / NCLOB ->  Text
        if "CLOB" in type_name:
            return Text()

        # BLOB / RAW / LONG RAW ->  LargeBinary（二进制跳过或存hex）
        if "BLOB" in type_name or "RAW" in type_name:
            return LargeBinary()

        # NUMBER ->  根据精度判断 Integer 或 Numeric
        if "NUMBER" in type_name:
            precision = getattr(col_type, "precision", None)
            scale = getattr(col_type, "scale", None)
            if scale == 0 or scale is None:
                return Integer()
            return Numeric(precision=precision, scale=scale)

        # FLOAT / BINARY_FLOAT / BINARY_DOUBLE ->  Numeric
        if "FLOAT" in type_name or "DOUBLE" in type_name:
            return Numeric()

        # DATE ->  DateTime（Oracle 的 DATE 包含时分秒）
        if "DATE" in type_name:
            return DateTime()

        # TIMESTAMP ->  DateTime
        if "TIMESTAMP" in type_name:
            return DateTime()

        # INTERVAL ->  Text（转字符串存储）
        if "INTERVAL" in type_name:
            return Text()

        # 兜底
        return col_type

    def clean_column(self, col):
        # 剥离 Oracle 特有的默认值函数, 避免 PG 不认识
        # 如 SYSDATE、SYS_GUID()、SYSTIMESTAMP 等
        if col.server_default is not None:
            sdf = str(col.server_default.arg).upper() if hasattr(col.server_default, "arg") else ""
            oracle_defaults = ("SYSDATE", "SYS_GUID", "SYSTIMESTAMP", "CURRENT_TIMESTAMP", "SEQUENCE")
            if any(kw in sdf for kw in oracle_defaults):
                col.server_default = None

        col.default = None

        # Oracle 不支持自增, 主键约束单独处理
        # 剥离 autoincrement 防止 PG 建表时产生歧义
        if hasattr(col, "autoincrement"):
            col.autoincrement = False

        return col
