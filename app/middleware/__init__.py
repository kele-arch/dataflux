# -- coding: utf-8 --
# @Author: 胡H
# @File: app/middleware/__init__.py
# @Created: 2025/11/19 17:24
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: 存放自定义中间件
from fastapi import FastAPI


def init_middlewares(app: FastAPI) -> None:
    """ 统一注册所有自定义中间件 """
    pass


__all__ = []
