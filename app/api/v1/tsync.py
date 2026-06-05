# -- coding: utf-8 --
# @Author: 胡H
# @File: tsync.py
# @Created: 2026/6/5 10:07
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from fastapi import APIRouter, Depends, HTTPException, Form, Response, Request, status

from app.schemas.tsync import DBSyncReq
from app.schemas.response import BaseResponse
from app.services.sync_service import sync_database_architecture_and_data
from app.com.decorators import measure_time

router = APIRouter(prefix="/tsync", tags=["数据同步引擎"])


@router.post("/database", summary="全量克隆源数据库结构与数据")
@measure_time  # 复用你写的耗时统计装饰器
def start_database_sync(req: DBSyncReq):
    try:
        # 这里由于迁移可能是 CPU 密集/IO 密集型,实际项目中建议放入 BackgroundTasks 或 线程池
        result = sync_database_architecture_and_data(req)
        return BaseResponse(data=result, msg="数据库同步成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"同步失败: {str(e)}")
