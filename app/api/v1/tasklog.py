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
from app.schemas.tasklog import LogPageQueryReq, TaskLogPageOut, TaskLogDetailOut
from app.crud.crud_tasklog import crud_tasklog

router = APIRouter(prefix="/tasklog", tags=["同步任务日志管理"])


@router.post("/task-list", summary="获取任务执行日志列表", response_model=BaseResponse[TaskLogPageOut])
def get_tasklog_list(req: LogPageQueryReq, db: Session = Depends(get_db)):
    """ 展示历史运行日志，task_id 不传则查全量 """
    total, items = crud_tasklog.get_list(db, req)
    return BaseResponse(data={"total": total, "items": items}, msg="获取日志成功")


@router.post("/detail", summary="获取单条日志详情", response_model=BaseResponse[TaskLogDetailOut])
def get_tasklog_detail(
    log_id: str = None,
    task_id: str = None,
    db: Session = Depends(get_db)
):
    """
    支持两种查询方式：
    - log_id: 精确查某条日志
    - task_id: 查该任务最近一次执行的日志
    """
    if not log_id and not task_id:
        return BaseResponse(code=0, msg="请传入 log_id 或 task_id")

    log_obj = crud_tasklog.get_detail(db, log_id=log_id, task_id=task_id)
    if not log_obj:
        return BaseResponse(code=0, msg="日志记录不存在")
    return BaseResponse(data=TaskLogDetailOut.model_validate(log_obj), msg="获取日志详情成功")
