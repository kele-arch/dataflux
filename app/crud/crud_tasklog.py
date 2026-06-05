# -- coding: utf-8 --
# @Author: 胡H
# @File: app/crud/crud_tasklog.py
# @Created: 2026/6/5 15:55
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.taskLogModel import TaskLog
from app.schemas.tasklog import LogPageQueryReq


class CRUDTaskLog:
    """ 任务日志查询 CRUD """

    def get_list(self, db: Session, req: LogPageQueryReq) -> tuple[int, list]:
        # 强制约束只能查某个特定任务的日志，按时间倒序排（最新的在最上面）
        stmt = select(TaskLog).where(TaskLog.task_id == req.task_id).order_by(TaskLog.start_time.desc())

        # 可选的状态过滤
        if req.status:
            stmt = stmt.where(TaskLog.status == req.status)

        # 统计总数
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

        # 分页拉取数据
        offset = (req.page - 1) * req.size
        items = db.execute(stmt.offset(offset).limit(req.size)).scalars().all()

        return total, items


# 实例化全局单例
crud_tasklog = CRUDTaskLog()
