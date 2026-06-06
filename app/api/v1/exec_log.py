# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/exec_log.py
# @Created: 2026/6/6 15:25
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 表级同步执行日志接口

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.response import BaseResponse
from app.schemas.sync_execution_log import ExecLogQueryReq, ExecLogPageOut
from app.crud.crud_exec_log import crud_exec_log

router = APIRouter(prefix="/execlog", tags=["表级同步日志"])


@router.post("/list", summary="获取表级同步日志列表", response_model=BaseResponse[ExecLogPageOut])
def get_exec_log_list(req: ExecLogQueryReq, db: Session = Depends(get_db)):
    """
    查询每张表的同步执行记录
    - 不传任何参数: 全量日志
    - 传 task_id: 某个任务的所有表级日志
    - 传 log_id: 某次执行的所有表级日志
    - 传 target_table: 按目标表名模糊搜索
    """
    total, items = crud_exec_log.get_list(db, req)
    return BaseResponse(data={"total": total, "items": items}, msg="获取成功")
