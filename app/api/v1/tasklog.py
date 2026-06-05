# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/tasklog.py
# @Created: 2026/6/5 15:55
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.response import BaseResponse
from app.schemas.tasklog import LogPageQueryReq, TaskLogPageOut
from app.crud.crud_tasklog import crud_tasklog

router = APIRouter(prefix="/tasklog", tags=["同步任务日志管理"])


@router.post("/task-list", summary="获取任务执行日志列表", response_model=BaseResponse[TaskLogPageOut])
def get_tasklog_list(req: LogPageQueryReq, db: Session = Depends(get_db)):
    """ 展示该任务的历史运行情况 """

    total, items = crud_tasklog.get_list(db, req)

    return BaseResponse(data={"total": total, "items": items}, msg="获取日志成功")
