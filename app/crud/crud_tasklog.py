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
        # 动态排序
        sort_col = getattr(TaskLog, req.sort_by or "start_time", TaskLog.start_time)
        order = sort_col.desc() if req.sort_order == "desc" else sort_col.asc()
        stmt = select(TaskLog).order_by(order)

        # 可选：按任务ID过滤
        if req.task_id:
            stmt = stmt.where(TaskLog.task_id == req.task_id)

        # 可选：按任务名模糊搜索
        if req.task_name:
            stmt = stmt.where(TaskLog.task_name.like(f"%{req.task_name}%"))

        # 可选：按状态过滤
        if req.status:
            stmt = stmt.where(TaskLog.status == req.status)

        # 统计总数
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

        # 分页拉取数据
        offset = (req.page - 1) * req.size
        items = db.execute(stmt.offset(offset).limit(req.size)).scalars().all()

        return total, items

    def get_detail(self, db: Session, log_id: str = None, task_id: str = None):
        """ 获取单条日志详情（含 detail_json）, 支持 log_id 或 task_id 查询 """
        if log_id:
            return db.execute(select(TaskLog).where(TaskLog.id == log_id)).scalar_one_or_none()
        if task_id:
            return db.execute(
                select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.start_time.desc()).limit(1)
            ).scalar_one_or_none()
        return None


# 实例化全局单例
crud_tasklog = CRUDTaskLog()
