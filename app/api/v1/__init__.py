# -- coding: utf-8 --
# @Author: 胡H
# @File: app/v1/__init__.py
# @Created: 2025/11/19 10:40
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:
from fastapi import APIRouter
from .tsync import router as tsync_router
from .datasource import router as datasource_router
from .tasklog import router as tasklog_router
from .exec_log import router as exec_log_router
from .monitor import router as monitor_router
from .explorer import router as explorer_router
from .media import router as media_router

api_router = APIRouter()
api_router.include_router(tsync_router)
api_router.include_router(datasource_router)
api_router.include_router(tasklog_router)
api_router.include_router(exec_log_router)
api_router.include_router(monitor_router)
api_router.include_router(explorer_router)
api_router.include_router(media_router)
