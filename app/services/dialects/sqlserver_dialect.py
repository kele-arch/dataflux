# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/dialects/sqlserver_dialect.py
# @Created: 2026/6/15 15:54
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: SQL Server 方言处理器：类型归一化 + 约束清洗

from sqlalchemy import String, Text, Numeric, Integer, DateTime, Date, Boolean, LargeBinary
from app.services.dialects.base import BaseDialectHandler


class SqlServerDialectHandler(BaseDialectHandler):
    """
    SQL Server 数据库的方言处理器, 负责将 SQL Server 特有的数据类型转换为 SQLAlchemy 的通用类型
    """

    def normalize_type(self, col_type):
        type_name = type(col_type).__name__.upper()
        type_str = str(col_type).upper()

        # VARCHAR / NVARCHAR ->  String 或 Text
        if "NVARCHAR" in type_str or "VARCHAR" in type_str:
            length = getattr(col_type, "length", None)
            if length and length > 0:
                return String(length)
            return Text()  # VARCHAR(MAX) / NVARCHAR(MAX)

        # CHAR / NCHAR ->  String
        if "NCHAR" in type_str or type_name == "CHAR":
            length = getattr(col_type, "length", None)
            return String(length) if length else String(255)

        # TEXT / NTEXT ->  Text(已废弃但老库还在用)
        if type_name in ("TEXT", "NTEXT"):
            return Text()

        # INT 系列
        if type_name in ("BIGINT",):
            return Integer()
        if type_name in ("INT", "INTEGER", "SMALLINT", "TINYINT"):
            return Integer()

        # DECIMAL / NUMERIC / MONEY / SMALLMONEY ->  Numeric
        if type_name in ("DECIMAL", "NUMERIC", "MONEY", "SMALLMONEY"):
            precision = getattr(col_type, "precision", 18)
            scale = getattr(col_type, "scale", 2)
            return Numeric(precision=precision, scale=scale)

        # FLOAT / REAL ->  Numeric
        if type_name in ("FLOAT", "REAL"):
            return Numeric()

        # DATETIME / DATETIME2 / SMALLDATETIME ->  DateTime
        if "DATETIME" in type_name:
            return DateTime()

        # DATE ->  Date
        if type_name == "DATE":
            return Date()

        # TIME ->  Text(PG 的 Time 类型存在时区问题, 转 Text 更安全)
        if type_name == "TIME":
            return Text()

        # BIT ->  Boolean
        if type_name == "BIT":
            return Boolean()

        # UNIQUEIDENTIFIER (GUID) ->  String(36)
        if "UNIQUEIDENTIFIER" in type_name:
            return String(36)

        # VARBINARY / BINARY / IMAGE ->  LargeBinary
        if "BINARY" in type_name or type_name == "IMAGE":
            return LargeBinary()

        # XML ->  Text
        if type_name == "XML":
            return Text()

        # 兜底
        return super().normalize_type(col_type)

    def clean_column(self, col):
        # 剥离 SQL Server 特有的默认值函数
        if col.server_default is not None:
            sdf = str(col.server_default.arg).upper() if hasattr(col.server_default, "arg") else ""
            sqlserver_defaults = ("GETDATE", "GETUTCDATE", "NEWID", "NEWSEQUENTIALID", "SYSDATETIME")
            if any(kw in sdf for kw in sqlserver_defaults):
                col.server_default = None

        col.default = None

        # SQL Server 的 IDENTITY 列(自增)剥离
        if hasattr(col, "autoincrement"):
            col.autoincrement = False

        return col
