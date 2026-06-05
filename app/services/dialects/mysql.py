# -- coding: utf-8 --
# @Author: 胡H
# @File: mysql.py
# @Created: 2026/6/5 10:31
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import DateTime, Integer, Text, String, Float
from sqlalchemy.types import NullType
from sqlalchemy.dialects.mysql import (
    DATETIME, TIMESTAMP, TINYINT, LONGTEXT, MEDIUMTEXT, TINYTEXT,
    ENUM, SET, YEAR, DOUBLE, FLOAT as MYSQL_FLOAT
)
from app.services.dialects.base import BaseDialectHandler
from app.core import logger


class MySQLHandler(BaseDialectHandler):
    def normalize_type(self, col_type):
        """ 将 MySQL 方言转为 PG 兼容的通用类型 """
        if isinstance(col_type, (DATETIME, TIMESTAMP)):
            return DateTime()
        if isinstance(col_type, TINYINT):
            return Integer()
        if isinstance(col_type, (LONGTEXT, MEDIUMTEXT, TINYTEXT, NullType)):
            return Text()
        if isinstance(col_type, (ENUM, SET)):
            return String(255)  # 把 MySQL 的枚举强转为字符串,防止建表报错
        if isinstance(col_type, YEAR):
            return Integer()
        if isinstance(col_type, (DOUBLE, MYSQL_FLOAT)):
            return Float()
        return col_type
