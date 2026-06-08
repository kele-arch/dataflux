# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tsync.py
# @Created: 2026/6/5 10:06
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from datetime import datetime
from urllib.parse import urlparse

from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, Literal, List

from app.core.config import settings
from app.schemas.base import BaseDecryptReq

_parsed_mongo = urlparse(settings.MONGO_URL)

# 即使没有密码或账号，urlparse 也会安全地解析为 None
_default_host = _parsed_mongo.hostname or "127.0.0.1"
_default_port = _parsed_mongo.port or 27017
_default_user = _parsed_mongo.username
_default_pass = _parsed_mongo.password
_default_db = settings.MONGO_DB_NAME


class DBSyncReq(BaseDecryptReq):
    """ 接收源数据库表单信息 """
    # 对外接口无影响，仅供后台 Worker 和 Engine 流转使用
    task_id: Optional[str] = Field(default=None, description="任务唯一标识(内部流转专用)")

    db_type: Literal["mysql", "postgresql", "oracle", "mongodb", "dm"] = Field(..., description="数据库类型")
    host: str = Field(..., description="主机地址 IP")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    db_name: str = Field(..., description="要同步的数据库名")

    # 选填, 有默认值
    charset: Optional[str] = Field("utf8mb4", description="字符集")
    target_table: Optional[str] = Field(default=None, description="指定表名，不填则整库同步")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表，为空则全库同步")
    table_mapping: Optional[dict] = Field(default=None, description="表名映射: {'源表名':'目标表名'}，不传则同名")

    # 核心同步策略
    sync_mode: Literal["insert", "overwrite", "skip"] = Field(
        default="overwrite",
        description="冲突策略: 默认 'overwrite' (覆盖更新)"
    )
    collect_mode: Literal["full", "inc_id", "inc_time", "custom_sql"] = Field(
        default="full",
        description="采集模式: 默认 'full' (全量采集)"
    )

    # 增量高级配置 (默认为 None)
    incremental_column: Optional[str] = Field(
        default=None,
        description="增量依赖的字段名(如 id 或 update_time)"
    )
    last_watermark: Optional[str] = Field(
        default=None,
        description="上次采集的最大水位线(如 2026-06-04 10:00:00)"
    )
    custom_sql: Optional[str] = Field(
        default=None,
        description="自定义提取SQL语句"
    )

    # 目标库类型,默认写 PG(postgresql / mongodb)
    target_type: str = Field(default="postgresql", description="目标库类型: postgresql 或 mongodb")
    # 目标库为 MongoDB 时的连接信息(目前先读取配置写死本机)
    target_host: Optional[str] = Field(default=_default_host, description="目标库主机")
    target_port: Optional[int] = Field(default=_default_port, description="目标库端口")
    target_username: Optional[str] = Field(default=_default_user, description="目标库账号")
    target_password: Optional[str] = Field(default=_default_pass, description="目标库密码")
    target_db_name: Optional[str] = Field(default=_default_db, description="目标库名")
    # target_host: Optional[str] = None
    # target_port: Optional[int] = 27017
    # target_username: Optional[str] = None
    # target_password: Optional[str] = None
    # target_db_name: Optional[str] = None


# region ---- 任务管理 ----
class TaskCreateReq(BaseDecryptReq):
    task_name: str = Field(..., description="任务名称")
    # source_id: str = Field(..., description="关联的数据源ID")
    source_id: Optional[str] = Field(default=None, description="数据源ID")
    topic_or_table: Optional[str] = Field(default=None, description="custom_sql模式下目标库写入表名，普通模式可不传")

    schedule_type: str = Field(default="none", description="调度类型: none, cron, interval_min, daily, weekly")
    schedule_value: Optional[str] = Field(default=None, description="配合 type 使用的值，如 '02:30'")

    schedule_cron: Optional[str] = Field(default=None, description="定时任务表达式")
    status: int = Field(default=1, description="任务状态：0停用, 1启用")
    sync_mode: str = Field(default="overwrite", description="冲突策略")
    collect_mode: Literal["full", "inc_id", "inc_time", "custom_sql"] = Field(default="full")
    incremental_column: Optional[str] = Field(default=None)
    last_watermark: Optional[str] = Field(default=None)
    custom_sql: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None, description="备注")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表")
    table_mapping: Optional[dict] = Field(default=None, description="表名映射: {'源表名':'目标表名'}，不传则同名")

    # 目标库配置 (MongoDB → MongoDB 时需要)
    target_type: str = Field(default="postgresql", description="目标库类型: postgresql 或 mongodb")
    target_host: Optional[str] = Field(default=None, description="目标库主机")
    target_port: Optional[int] = Field(default=None, description="目标库端口")
    target_username: Optional[str] = Field(default=None, description="目标库账号")
    target_password: Optional[str] = Field(default=None, description="目标库密码")
    target_db_name: Optional[str] = Field(default=None, description="目标库名")


class TaskUpdateReq(TaskCreateReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="要更新的任务ID(UUID)")
    schedule_type: Optional[str] = Field(default=None)
    schedule_value: Optional[str] = Field(default=None)


class TaskIdReq(BaseDecryptReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID(UUID)")


class TaskStatusReq(BaseDecryptReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID(UUID)")
    status: int = Field(..., description="目标状态: 0=停用, 1=启用")


class TaskPageQueryReq(BaseDecryptReq):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    task_name: Optional[str] = Field(default=None)
    collect_mode: Optional[str] = Field(default=None)


class TaskOut(BaseModel):
    id: str
    task_name: str
    source_id: Optional[str] = None
    topic_or_table: Optional[str]
    status: int
    sync_mode: str
    collect_mode: str
    incremental_column: Optional[str]
    last_watermark: Optional[str]
    remark: Optional[str]
    create_time: Optional[datetime]
    update_time: Optional[datetime]
    sync_tables: Optional[List[str]]
    table_mapping: Optional[dict] = None
    schedule_type: Optional[str]
    schedule_value: Optional[str]
    target_type: Optional[str] = "postgresql"
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    target_db_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskPageOut(BaseModel):
    total: int
    items: List[TaskOut]
    model_config = ConfigDict(from_attributes=True)


# endregion

# region ---- 仪表盘统计 ----
class DashboardOut(BaseModel):
    total_tasks: int
    active_tasks: int
    today_records: int
    success_rate: float
# endregion
