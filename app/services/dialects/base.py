# -- coding: utf-8 --
# @Author: 胡H
# @File: base.py
# @Created: 2026/6/5 10:31
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

class BaseDialectHandler:
    def normalize_type(self, col_type):
        """ 默认不转换类型 """
        return col_type

    def clean_column(self, col):
        """ 通用的列清理逻辑 """
        col.server_default = None  # 砍掉所有默认值
        col.server_onupdate = None  # 砍掉自动更新机制

        # 砍掉排序规则 (Collation)
        col.collation = None
        if hasattr(col.type, 'collation'):
            col.type.collation = None

        return col
