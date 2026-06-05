# -- coding: utf-8 --
# @Author: 胡H
# @File: postgres.py
# @Created: 2026/6/5 10:31
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM
from app.services.dialects.base import BaseDialectHandler


class PostgreSQLHandler(BaseDialectHandler):
    def normalize_type(self, col_type):
        """ PG 到 PG,绝大多数类型是原生兼容的,但要注意自定义枚举 """
        if isinstance(col_type, ENUM):
            # PG 的 ENUM 是独立创建的 Type为. 了 ODS 层的极简和通用
            # 将源库的 ENUM 统一下降级为 VARCHAR
            return String(255)
        return col_type
