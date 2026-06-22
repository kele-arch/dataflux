# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/clean_service.py
# @Created: 2026/6/22 11:11
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 采集数据清理服务-- 支持手动清理和定时自动清理

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text, inspect

from app.core import logger, project_rootpath
from app.core.config import settings
from app.db.session import collected_engine, SessionLocal
from app.models.taskLogModel import FtpFileRecord, OssFileRecord


class CleanService:
    """
    采集数据清理服务
    操作范围: 
      1. dataflux_collected 库里的采集数据表
      2. FtpFileRecord 记录(FTP/OSS 文件元数据)
      3. 本地下载文件(FTP/OSS 缓存文件)
    """

    #  工具方法

    def _table_exists(self, table_name: str) -> bool:
        inspector = inspect(collected_engine)
        return table_name in inspector.get_table_names()

    def _resolve_tables_to_clean(self, task_id: str, table_name: str) -> list:
        """
        解析实际需要清理的表名列表
        如果 table_name 是默认的动态表名模式(ftp_*/oss_*/mq_*/kafka_*/api_*), 
        则扫描采集库中所有匹配该前缀的表, 防止 DROP 遗漏动态生成的小表 
        """
        # 默认表名模式: 未指定 target_table 时自动生成
        auto_patterns = ("ftp_", "oss_", "mq_", "kafka_", "api_", "task_")
        is_auto = table_name.startswith(auto_patterns)

        if not is_auto:
            return [table_name]

        # 扫描采集库中所有匹配前缀的表
        inspector = inspect(collected_engine)
        all_tables = inspector.get_table_names()
        matched = [t for t in all_tables if t.startswith(table_name)]

        if matched:
            logger.info(f"动态表名解析: 默认 [{table_name}] ->  实际 {len(matched)} 张: {matched}")
            return matched
        return [table_name]

    def _get_local_task_dirs(self, task_id: str) -> list:
        ftp_base = Path(project_rootpath, getattr(settings, "FTP_LOCAL_SAVE_DIR", "ftp_files"))
        oss_base = Path(project_rootpath, getattr(settings, "OSS_LOCAL_SAVE_DIR", "data/oss_files"))
        dirs = []
        for base in (ftp_base, oss_base):
            task_dir = base / task_id
            if task_dir.exists():
                dirs.append(str(task_dir))
        return dirs

    def _clean_local_files(self, task_id: str) -> int:
        dirs = self._get_local_task_dirs(task_id)
        total = 0
        for d in dirs:
            try:
                count = sum(1 for _ in Path(d).rglob("*") if _.is_file())
                shutil.rmtree(d, ignore_errors=True)
                total += count
                logger.info(f"已删除本地缓存目录: {d} ({count} 个文件)")
            except Exception as e:
                logger.error(f"删除本地目录失败 [{d}]: {e}")
        return total

    def _clean_file_records(self, db, task_id: str) -> int:
        total = 0
        total += db.query(FtpFileRecord).filter(FtpFileRecord.task_id == task_id).delete()
        total += db.query(OssFileRecord).filter(OssFileRecord.task_id == task_id).delete()
        db.commit()
        logger.info(f"任务 [{task_id}] 文件记录已清理: {total} 条")
        return total

    #  核心清理操作

    def truncate_table(self, table_name: str) -> dict:
        """
        清空表数据(TRUNCATE), 保留表结构
        速度比 DELETE 快, 不写行日志
        """
        if not self._table_exists(table_name):
            return {"status": "skipped", "msg": f"表 [{table_name}] 不存在"}

        with collected_engine.begin() as conn:
            conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY'))

        logger.info(f"表 [{table_name}] 已 TRUNCATE")
        return {"status": "success", "action": "truncate", "table": table_name}

    def drop_table(self, table_name: str) -> dict:
        """
        删除表(DROP TABLE IF EXISTS)
        """
        with collected_engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))

        logger.info(f"表 [{table_name}] 已 DROP")
        return {"status": "success", "action": "drop", "table": table_name}

    def delete_by_days(self, table_name: str, keep_days: int, time_col: str = "collected_at") -> dict:
        """
        按时间保留: 删除 time_col < now() - keep_days 的数据
        time_col 默认是 collected_at(ISO字符串格式)
        """
        if not self._table_exists(table_name):
            return {"status": "skipped", "msg": f"表 [{table_name}] 不存在"}

        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()

        with collected_engine.begin() as conn:
            result = conn.execute(
                text(f'DELETE FROM "{table_name}" WHERE "{time_col}" < :cutoff'),
                {"cutoff": cutoff}
            )
            deleted_count = result.rowcount

        logger.info(f"表 [{table_name}] 按 {keep_days} 天保留策略删除 {deleted_count} 条")
        return {
            "status": "success", "action": "delete_by_days",
            "table": table_name, "deleted": deleted_count,
            "keep_days": keep_days, "cutoff": cutoff
        }

    def delete_by_count(self, table_name: str, keep_count: int, time_col: str = "collected_at") -> dict:
        """
        按条数保留: 只保留最新 keep_count 条, 删除其余
        通过子查询找出第 keep_count 条的 time_col 边界, 删除更早的数据
        """
        if not self._table_exists(table_name):
            return {"status": "skipped", "msg": f"表 [{table_name}] 不存在"}

        # 先查总数, 如果总数不超过 keep_count 则不需要清理
        with collected_engine.connect() as conn:
            total = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar()

        if total <= keep_count:
            logger.info(f"表 [{table_name}] 共 {total} 条, 未超过保留数量 {keep_count}, 跳过清理")
            return {
                "status": "skipped", "msg": "未超过保留数量",
                "table": table_name, "total": total, "keep_count": keep_count
            }

        with collected_engine.begin() as conn:
            result = conn.execute(
                text(f"""
                    DELETE FROM "{table_name}"
                    WHERE "{time_col}" < (
                        SELECT "{time_col}" FROM "{table_name}"
                        ORDER BY "{time_col}" DESC
                        LIMIT 1 OFFSET :keep_count
                    )
                """),
                {"keep_count": keep_count}
            )
            deleted_count = result.rowcount

        logger.info(f"表 [{table_name}] 按条数保留 {keep_count} 条, 删除 {deleted_count} 条")
        return {
            "status": "success", "action": "delete_by_count",
            "table": table_name, "deleted": deleted_count,
            "keep_count": keep_count
        }

    #  任务级别一键清理(联动文件记录 + 本地文件)

    def clean_task_data(
            self,
            task_id: str,
            table_name: str,
            action: str,  # truncate / drop / by_days / by_count
            keep_days: int = None,
            keep_count: int = None,
            clean_files: bool = True  # 是否同时清理本地文件
    ) -> dict:
        """
        任务级别一键清理
        action:
          truncate  ->  清空表数据, 保留结构
          drop      ->  删除整张表
          by_days   ->  按时间保留
          by_count  ->  按条数保留
        """
        # 解析目标表(动态表名场景下可能有多张)
        tables_to_clean = self._resolve_tables_to_clean(task_id, table_name)

        result = {"tables_cleaned": []}
        for tbl in tables_to_clean:
            if action == "truncate":
                result["tables_cleaned"].append(self.truncate_table(tbl))
            elif action == "drop":
                result["tables_cleaned"].append(self.drop_table(tbl))
            elif action == "by_days":
                if not keep_days:
                    raise ValueError("by_days 模式必须指定 keep_days")
                result["tables_cleaned"].append(self.delete_by_days(tbl, keep_days))
            elif action == "by_count":
                if not keep_count:
                    raise ValueError("by_count 模式必须指定 keep_count")
                result["tables_cleaned"].append(self.delete_by_count(tbl, keep_count))
            else:
                raise ValueError(f"不支持的清理操作: {action}")

        # 清理 FTP/OSS 文件记录(联动)
        db = SessionLocal()
        try:
            result["file_records_deleted"] = self._clean_file_records(db, task_id)
        finally:
            db.close()

        # 清理本地文件(可选)
        if clean_files:
            local_deleted = self._clean_local_files(task_id)
            result["local_files_deleted"] = local_deleted

        result["task_id"] = task_id
        result["cleaned_at"] = datetime.now().isoformat()
        logger.info(f"任务 [{task_id}] 数据清理完成: {result}")
        return result


clean_service = CleanService()
