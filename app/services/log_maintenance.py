# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/log_maintenance.py
# @Created: 2026/7/28 16:39
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务日志统计、安全清理及 ZIP 归档导出服务

import base64
import csv
import io
import json
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.models.taskLogModel import SyncExecutionLog, TaskLog


def _serializable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


class LogMaintenanceService:
    delete_chunk_size = 5000

    def stats(self, db: Session, task_id: str | None = None) -> dict:
        task_filter = [TaskLog.task_id == task_id] if task_id else []
        execution_filter = [SyncExecutionLog.task_id == task_id] if task_id else []

        task_total = db.execute(
            select(func.count(TaskLog.id)).where(*task_filter)
        ).scalar() or 0
        execution_total = db.execute(
            select(func.count(SyncExecutionLog.id)).where(*execution_filter)
        ).scalar() or 0

        task_status_rows = db.execute(
            select(TaskLog.status, func.count(TaskLog.id))
            .where(*task_filter)
            .group_by(TaskLog.status)
        ).all()
        execution_status_rows = db.execute(
            select(SyncExecutionLog.status, func.count(SyncExecutionLog.id))
            .where(*execution_filter)
            .group_by(SyncExecutionLog.status)
        ).all()

        oldest, newest = db.execute(
            select(func.min(TaskLog.start_time), func.max(TaskLog.start_time)).where(*task_filter)
        ).one()

        orphan_filter = [
            ~select(TaskLog.id).where(TaskLog.id == SyncExecutionLog.log_id).exists()
        ]
        if task_id:
            orphan_filter.append(SyncExecutionLog.task_id == task_id)
        orphan_execution_logs = db.execute(
            select(func.count(SyncExecutionLog.id)).where(*orphan_filter)
        ).scalar() or 0
        task_log_size = self._table_size(db, TaskLog.__table__.fullname)
        execution_log_size = self._table_size(db, SyncExecutionLog.__table__.fullname)

        return {
            "task_id": task_id,
            "task_log_count": task_total,
            "execution_log_count": execution_total,
            "total_log_count": task_total + execution_total,
            "task_log_status": {status: count for status, count in task_status_rows},
            "execution_log_status": {status: count for status, count in execution_status_rows},
            "orphan_execution_log_count": orphan_execution_logs,
            "oldest_log_time": oldest.isoformat() if oldest else None,
            "newest_log_time": newest.isoformat() if newest else None,
            "task_log_size_bytes": task_log_size,
            "execution_log_size_bytes": execution_log_size,
            "log_storage_size_bytes": (
                task_log_size + execution_log_size
                if task_log_size is not None and execution_log_size is not None
                else None
            ),
            "database_size_bytes": self._database_size(db),
        }

    def _table_size(self, db: Session, table_name: str) -> int | None:
        if db.get_bind().dialect.name != "postgresql":
            return None
        try:
            return db.execute(
                text("SELECT pg_total_relation_size(CAST(:table_name AS regclass))"),
                {"table_name": table_name},
            ).scalar()
        except Exception:
            db.rollback()
            return None

    def _database_size(self, db: Session) -> int | None:
        if db.get_bind().dialect.name != "postgresql":
            return None
        try:
            return db.execute(
                text("SELECT pg_database_size(current_database())")
            ).scalar()
        except Exception:
            db.rollback()
            return None

    def _cutoff(self, req) -> datetime:
        return req.before_time or (datetime.now() - timedelta(days=req.keep_days))

    def _matching_task_ids_stmt(self, req):
        conditions = [
            TaskLog.status.in_(req.statuses),
            TaskLog.start_time < self._cutoff(req),
        ]
        if req.task_id:
            conditions.append(TaskLog.task_id == req.task_id)
        return select(TaskLog.id).where(*conditions)

    def clean_preview(self, db: Session, req) -> dict:
        ids_stmt = self._matching_task_ids_stmt(req)
        task_count = db.execute(
            select(func.count()).select_from(ids_stmt.subquery())
        ).scalar() or 0
        execution_count = db.execute(
            select(func.count(SyncExecutionLog.id)).where(
                SyncExecutionLog.log_id.in_(ids_stmt)
            )
        ).scalar() or 0
        limited_ids_stmt = (
            self._matching_task_ids_stmt(req)
            .order_by(TaskLog.start_time.asc())
            .limit(req.max_delete)
        )
        selected_execution_count = db.execute(
            select(func.count(SyncExecutionLog.id)).where(
                SyncExecutionLog.log_id.in_(limited_ids_stmt)
            )
        ).scalar() or 0
        return {
            "task_id": req.task_id,
            "statuses": req.statuses,
            "cutoff_time": self._cutoff(req).isoformat(),
            "matched_task_logs": task_count,
            "matched_execution_logs": execution_count,
            "single_run_task_log_limit": req.max_delete,
            "will_delete_task_logs": min(task_count, req.max_delete),
            "will_delete_execution_logs": selected_execution_count,
            "truncated": task_count > req.max_delete,
        }

    def clean(self, db: Session, req) -> dict:
        selected_ids = db.execute(
            self._matching_task_ids_stmt(req)
            .order_by(TaskLog.start_time.asc())
            .limit(req.max_delete + 1)
        ).scalars().all()
        truncated = len(selected_ids) > req.max_delete
        ids = selected_ids[:req.max_delete]
        if not ids:
            return {
                "task_id": req.task_id,
                "deleted_task_logs": 0,
                "deleted_execution_logs": 0,
                "cutoff_time": self._cutoff(req).isoformat(),
            }

        deleted_execution_logs = 0
        deleted_task_logs = 0
        try:
            for start in range(0, len(ids), self.delete_chunk_size):
                chunk = ids[start:start + self.delete_chunk_size]
                execution_result = db.execute(
                    delete(SyncExecutionLog).where(SyncExecutionLog.log_id.in_(chunk))
                )
                task_result = db.execute(
                    delete(TaskLog).where(TaskLog.id.in_(chunk))
                )
                deleted_execution_logs += execution_result.rowcount or 0
                deleted_task_logs += task_result.rowcount or 0
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "task_id": req.task_id,
            "statuses": req.statuses,
            "cutoff_time": self._cutoff(req).isoformat(),
            "deleted_task_logs": deleted_task_logs,
            "deleted_execution_logs": deleted_execution_logs,
            "truncated": truncated,
        }

    def export(self, db: Session, req) -> dict:
        archive = io.BytesIO()
        exported = {}
        truncated = {}

        with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            if req.include_task_logs:
                stmt = select(TaskLog).order_by(TaskLog.start_time.desc())
                if req.task_id:
                    stmt = stmt.where(TaskLog.task_id == req.task_id)
                if req.statuses:
                    stmt = stmt.where(TaskLog.status.in_(req.statuses))
                if req.start_time:
                    stmt = stmt.where(TaskLog.start_time >= req.start_time)
                if req.end_time:
                    stmt = stmt.where(TaskLog.start_time <= req.end_time)
                rows = db.execute(stmt.limit(req.max_rows + 1)).scalars().all()
                truncated["task_logs"] = len(rows) > req.max_rows
                rows = rows[:req.max_rows]
                zip_file.writestr("task_logs.csv", self._to_csv(TaskLog, rows))
                exported["task_logs"] = len(rows)

            if req.include_execution_logs:
                stmt = select(SyncExecutionLog).order_by(SyncExecutionLog.create_time.desc())
                if req.task_id:
                    stmt = stmt.where(SyncExecutionLog.task_id == req.task_id)
                if req.statuses:
                    stmt = stmt.where(SyncExecutionLog.status.in_(req.statuses))
                if req.start_time:
                    stmt = stmt.where(SyncExecutionLog.create_time >= req.start_time)
                if req.end_time:
                    stmt = stmt.where(SyncExecutionLog.create_time <= req.end_time)
                rows = db.execute(stmt.limit(req.max_rows + 1)).scalars().all()
                truncated["execution_logs"] = len(rows) > req.max_rows
                rows = rows[:req.max_rows]
                zip_file.writestr("execution_logs.csv", self._to_csv(SyncExecutionLog, rows))
                exported["execution_logs"] = len(rows)

        content = archive.getvalue()
        file_name = f"dataflux_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return {
            "file_name": file_name,
            "content_type": "application/zip",
            "encoding": "base64",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "file_size_bytes": len(content),
            "exported_rows": exported,
            "truncated": truncated,
        }

    def _to_csv(self, model, rows: list) -> str:
        columns = [column.name for column in model.__table__.columns]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                column: _serializable(getattr(row, column))
                for column in columns
            })
        return buffer.getvalue()


log_maintenance_service = LogMaintenanceService()
