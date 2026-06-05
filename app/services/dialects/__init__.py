# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/dialects/__init__.py
# @Created: 2026/6/5 10:31
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from .mysql import MySQLHandler
from .postgres import PostgreSQLHandler


def get_dialect_handler(db_type: str):
    """ 根据传入的数据库类型 分配清洗器 """
    db_type = db_type.lower()
    if db_type == "mysql":
        return MySQLHandler()
    elif db_type == "postgresql":
        return PostgreSQLHandler()
    else:
        raise ValueError(f"暂不支持的方言清洗器: {db_type}")
