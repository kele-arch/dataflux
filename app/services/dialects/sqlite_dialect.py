# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/dialects/sqlite_dialect.py
# @Created: 2026/6/15 17:14
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: SQLite 方言处理器 -> 类型归一化 + 约束清洗

from sqlalchemy import String, Text, Numeric, Integer, DateTime, Date, Boolean, Float
from app.services.dialects.base import BaseDialectHandler


class SQLiteDialectHandler(BaseDialectHandler):
    """
    SQLite 使用动态类型(Type Affinity), 反射出的类型名千变万化：
    INTEGER、INT、BIGINT、TINYINT、TEXT、VARCHAR(n)、REAL、NUMERIC...
    甚至用户自定义的 "MY_INT_COLUMN" 这类随意命名
    必须做模糊匹配归一化
    """

    def normalize_type(self, col_type):
        type_str = str(col_type).upper()

        # INTEGER 系列(含 AUTOINCREMENT)
        if any(k in type_str for k in ("INT",)):
            return Integer()

        # 文本系列
        if any(k in type_str for k in ("TEXT", "CLOB", "CHAR")):
            # VARCHAR(n) 保留长度
            if "CHAR" in type_str:
                length = getattr(col_type, "length", None)
                return String(length) if length else Text()
            return Text()

        # 浮点/数值系列
        if any(k in type_str for k in ("REAL", "FLOAT", "DOUBLE")):
            return Float()

        if any(k in type_str for k in ("NUMERIC", "DECIMAL", "NUMBER")):
            precision = getattr(col_type, "precision", None)
            scale = getattr(col_type, "scale", None)
            return Numeric(precision=precision, scale=scale)

        # 布尔
        if "BOOL" in type_str:
            return Boolean()

        # 日期时间
        if "DATETIME" in type_str:
            return DateTime()

        if "DATE" in type_str:
            return Date()

        if "TIME" in type_str:
            return DateTime()

        # BLOB → Text(转 hex 字符串存储, 在 _clean_row_data 处理)
        if "BLOB" in type_str:
            return Text()

        # SQLite 特有：NullType(完全没有类型声明的列)
        # 归一化为 Text, 最安全
        type_name = type(col_type).__name__
        if type_name in ("NullType", "NULLTYPE"):
            return Text()

        # 兜底
        return Text()

    def clean_column(self, col):
        # SQLite 不存在复杂的服务端默认值函数, 基本是字面量
        # 但 CURRENT_TIMESTAMP / CURRENT_DATE 需要清洗
        if col.server_default is not None:
            sdf = str(col.server_default.arg).upper() if hasattr(col.server_default, "arg") else ""
            sqlite_defaults = ("CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME")
            if any(kw in sdf for kw in sqlite_defaults):
                col.server_default = None

        col.default = None

        # SQLite 的 ROWID 别名(INTEGER PRIMARY KEY)不要传给 PG
        if hasattr(col, "autoincrement"):
            col.autoincrement = False

        return col