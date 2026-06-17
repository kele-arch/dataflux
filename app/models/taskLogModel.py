# -- coding: utf-8 --
# @Author: 胡H
# @File: app/models/taskLogModel.py
# @Created: 2026/6/5 15:44
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from typing import Optional

from sqlalchemy import String, Integer, BigInteger, Text, DateTime, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.base import Base
from app.models.bashModel import BaseModelMixin
from app.core.config import settings


# region ---- 任务执行历史日志表 ----
class TaskLog(Base, BaseModelMixin):
    __tablename__ = "sys_task_log"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "任务执行历史日志表"},
    )

    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="关联的任务ID")
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="任务名称快照")

    # 状态枚举：running(运行中), success(成功), failed(失败)
    status: Mapped[str] = mapped_column(String(20), default="running", comment="执行状态")

    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="开始时间")
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")

    # 统计数据
    tables_synced: Mapped[int] = mapped_column(Integer, default=0, comment="同步表数量")
    total_records: Mapped[int] = mapped_column(Integer, default=0, comment="同步总条数")

    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="执行详情快照(策略/表名/条数/水位线)")

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")


# endregion

# region ---- 表级同步执行日志(映射流水表) ----

class SyncExecutionLog(Base, BaseModelMixin):
    """ 每张表的同步执行记录,关联到 TaskLog """
    __tablename__ = "sync_execution_log"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "表级同步执行日志(映射)"},
    )

    # 关联到 TaskLog（哪次执行）
    log_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="关联的TaskLog ID")

    # 关联到任务
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="归属的任务ID")

    # 表名（普通模式下 source = target，custom_sql 模式下可能不同）
    source_table: Mapped[str] = mapped_column(String(100), nullable=False, comment="源表名")
    target_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="目标表名")

    # 执行策略
    sync_mode: Mapped[str] = mapped_column(String(20), nullable=False, comment="冲突策略: overwrite/skip/insert")
    collect_mode: Mapped[str] = mapped_column(String(20), nullable=False,
                                              comment="采集模式: full/inc_id/inc_time/custom_sql")

    # 执行结果
    records_count: Mapped[int] = mapped_column(Integer, default=0, comment="本次同步条数")
    cost_seconds: Mapped[float] = mapped_column(Float, default=0, comment="耗时(秒)")
    watermark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="本次高水位线")

    # 状态
    status: Mapped[str] = mapped_column(String(20), default="success", comment="success/failed")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")


# endregion


# region ---- FTP采集记录表 ----
class FtpFileRecord(BaseModelMixin, Base):
    __tablename__ = "ftp_file_record"
    __table_args__ = {"comment": "FTP 文件采集记录表"}

    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="关联采集任务ID")
    remote_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="FTP远程文件路径")
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="本地存储绝对路径")
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="文件名")
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="文件大小(字节)")
    md5: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="文件MD5，用于增量去重")
    remote_mtime: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="远程文件修改时间，快速去重凭据")
    remote_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="远程文件大小，配合mtime做下载前去重")
    file_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True,
                                                     comment="文件类型: csv/json/yaml/binary")
    is_parsed: Mapped[int] = mapped_column(Integer, default=0, comment="是否已解析入库(0未解析 1已解析)")
    parsed_rows: Mapped[int] = mapped_column(Integer, default=0, comment="解析写入行数")
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="下载时间")


# endregion

# region ---- OSS采集记录表 ----
class OssFileRecord(BaseModelMixin, Base):
    __tablename__ = "oss_file_record"
    __table_args__ = {"comment": "OSS 对象存储文件采集记录表"}

    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="关联采集任务ID")
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="OSS对象Key(即文件完整路径)")
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="本地存储绝对路径")
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="文件名")
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="文件大小(字节)")
    md5: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="文件MD5，用于增量去重")
    file_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True,
                                                     comment="文件类型: csv/json/yaml/xlsx/xml/binary")
    is_parsed: Mapped[int] = mapped_column(Integer, default=0, comment="是否已解析入库(0未解析 1已解析)")
    parsed_rows: Mapped[int] = mapped_column(Integer, default=0, comment="解析写入行数")
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="首次下载时间")
# endregion
