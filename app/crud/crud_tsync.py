# -- coding: utf-8 --
# @Author: 胡H
# @File: app/crud/crud_tsync.py
# @Created: 2026/6/5 14:45
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import select, update, delete, func, case
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.collectTaskModel import CollectTask
from app.models.taskLogModel import TaskLog
from app.schemas.tsync import TaskCreateReq, TaskUpdateReq, TaskPageQueryReq
from app.services.task_control import _get_redis


class CRUDCollectTask:
    """ 同步任务配置 CRUD 封装类 """

    def create(self, db: Session, req: TaskCreateReq) -> CollectTask:
        """ 新增任务 """
        # 将 pydantic 模型转为字典并剥离不属于数据库的字段
        obj_in_data = req.model_dump(exclude_unset=True)
        db_obj = CollectTask(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_id(self, db: Session, task_id: int) -> CollectTask:
        """ 根据 ID 获取任务详情 """
        return db.execute(select(CollectTask).where(CollectTask.id == task_id)).scalar_one_or_none()

    def update(self, db: Session, req: TaskUpdateReq) -> bool:
        """ 更新任务 """
        obj_in_data = req.model_dump(exclude_unset=True, exclude={"task_id"})
        stmt = update(CollectTask).where(CollectTask.id == req.task_id).values(**obj_in_data)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def change_status(self, db: Session, task_id: str, status: int) -> bool:
        """ 切换任务启用/停用状态 """
        stmt = update(CollectTask).where(CollectTask.id == task_id).values(status=status)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def delete(self, db: Session, task_id: int) -> bool:
        """ 删除任务 """
        stmt = delete(CollectTask).where(CollectTask.id == task_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def get_list(self, db: Session, req: TaskPageQueryReq) -> dict:
        """ 分页与条件查询 (支持排序), 附带每项任务的 run_status """
        # 动态排序
        sort_col = getattr(CollectTask, req.sort_by or "create_time", CollectTask.create_time)
        order = sort_col.desc() if req.sort_order == "desc" else sort_col.asc()
        stmt = select(CollectTask).order_by(order)

        # 动态条件过滤
        if req.task_name:
            stmt = stmt.where(CollectTask.task_name.like(f"%{req.task_name}%"))
        if req.collect_mode:
            stmt = stmt.where(CollectTask.collect_mode == req.collect_mode)

        # 统计总数
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(total_stmt).scalar() or 0

        # 分页查出当前页的 Task
        offset = (req.page - 1) * req.size
        stmt = stmt.offset(offset).limit(req.size)
        items = db.execute(stmt).scalars().all()

        # 批量获取日志并注入 run_status
        if items:
            # 收集当前页所有的 task_id
            task_ids = [item.id for item in items]

            # 一次性查出这些 task_id 的所有关联日志（按时间倒序排好）
            logs_stmt = (
                select(TaskLog)
                .where(TaskLog.task_id.in_(task_ids))
                .order_by(TaskLog.task_id, TaskLog.start_time.desc())
            )
            all_logs = db.execute(logs_stmt).scalars().all()

            # 在 Python 内存中对日志进行分组, 只取每个任务的第一条（最新一条）
            latest_logs_map = {}
            for log in all_logs:
                if log.task_id not in latest_logs_map:
                    latest_logs_map[log.task_id] = log

            # 以 Redis 锁为最高准则注入 run_status（根治脑裂）
            active_statuses = {"pending", "running", "paused", "cancelled"}
            r_client = _get_redis()
            for item in items:
                lock_key = f"sync_task_lock:{item.id}"

                # 规则 1：Redis 锁存在 → 强行判定 running（即使 DB 日志已结束）
                if r_client.exists(lock_key):
                    latest_log = latest_logs_map.get(item.id)
                    item.run_status = "running"
                    item.current_log_id = latest_log.id if latest_log else None
                # 规则 2：锁不存在 → 按 DB 日志状态判定
                else:
                    latest_log = latest_logs_map.get(item.id)
                    if latest_log and latest_log.status in active_statuses:
                        item.run_status = latest_log.status
                        item.current_log_id = latest_log.id
                    else:
                        item.run_status = "idle"
                        item.current_log_id = None
        else:
            # 如果当前页没数据,直接忽略
            pass

        return {
            "total": total,
            "items": [item for item in items]
        }

    def update_watermark(self, db: Session, task_id: int, new_watermark: str):
        """ 核心闭环：每次同步完成后更新高水位线 """
        stmt = update(CollectTask).where(CollectTask.id == task_id).values(last_watermark=new_watermark)
        db.execute(stmt)
        db.commit()

    def get_dashboard_data(self, db: Session):
        today = datetime.now().date()
        today_filter = func.date(TaskLog.start_time) == today

        # 统计总量和成功量 (SA 2.0 风格)
        stats_stmt = select(
            func.count(TaskLog.id).label("total_logs"),
            func.sum(case((TaskLog.status == "success", 1), else_=0)).label("success_logs")
        ).where(today_filter)
        stats = db.execute(stats_stmt).first()

        total_logs = stats[0] or 0
        success_logs = stats[1] or 0

        # 计算成功率
        success_rate = 0.0
        if total_logs > 0:
            success_rate = round((success_logs / total_logs) * 100, 2)

        # 统计今日总记录数
        today_recs_stmt = select(func.sum(TaskLog.total_records)).where(today_filter)
        today_recs = db.execute(today_recs_stmt).scalar() or 0

        # 任务统计
        total_tasks = db.execute(select(func.count(CollectTask.id))).scalar() or 0
        active_tasks = db.execute(
            select(func.count(CollectTask.id)).where(CollectTask.status == 1)
        ).scalar() or 0

        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "today_records": int(today_recs),
            "success_rate": success_rate
        }


crud_task = CRUDCollectTask()
