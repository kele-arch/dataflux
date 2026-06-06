# -- coding: utf-8 --
# @Author: 胡H
# @File: app/crud/crud_exec_log.py
# @Created: 2026/6/6  15:25
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 表级同步执行日志 CRUD
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.taskLogModel import SyncExecutionLog
from app.schemas.sync_execution_log import ExecLogQueryReq


class CRUDExecLog:

    def get_list(self, db: Session, req: ExecLogQueryReq) -> tuple[int, list]:
        stmt = select(SyncExecutionLog).order_by(SyncExecutionLog.create_time.desc())

        if req.task_id:
            stmt = stmt.where(SyncExecutionLog.task_id == req.task_id)
        if req.log_id:
            stmt = stmt.where(SyncExecutionLog.log_id == req.log_id)
        if req.target_table:
            stmt = stmt.where(SyncExecutionLog.target_table.like(f"%{req.target_table}%"))
        if req.status:
            stmt = stmt.where(SyncExecutionLog.status == req.status)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        offset = (req.page - 1) * req.size
        items = db.execute(stmt.offset(offset).limit(req.size)).scalars().all()

        return total, items


crud_exec_log = CRUDExecLog()
