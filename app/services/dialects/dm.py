# -- coding: utf-8 --
# @Author: 胡H
# @File: dm.py
# @Created: 2026/6/5 10:31
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 达梦(DM) 数据库方言特化清洗器
from sqlalchemy import String, Text, Numeric, DateTime
from app.services.dialects.base import BaseDialectHandler


class DMHandler(BaseDialectHandler):
    """ 达梦数据库方言处理器: 将 Oracle 风格类型归一化为通用类型 """

    def clean_column(self, col):
        """ 达梦专属清理: 额外剥离 Python 侧默认值 (如 DEFAULT SYSDATE) """
        col = super().clean_column(col)
        col.default = None
        return col

    def normalize_type(self, col_type):
        type_name = str(col_type).upper()

        if "VARCHAR2" in type_name or "VARCHAR" in type_name:
            return String(length=getattr(col_type, "length", 255))
        elif "CLOB" in type_name or "TEXT" in type_name:
            return Text()
        elif "NUMBER" in type_name:
            return Numeric(
                precision=getattr(col_type, "precision", None),
                scale=getattr(col_type, "scale", None)
            )
        elif "DATE" in type_name or "TIMESTAMP" in type_name:
            return DateTime()

        return col_type
