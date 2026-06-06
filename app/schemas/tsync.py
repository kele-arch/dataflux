# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tsync.py
# @Created: 2026/6/5 10:06
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from datetime import datetime

from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, Literal, List
from app.schemas.base import BaseDecryptReq


class DBSyncReq(BaseDecryptReq):
    """ 接收前端传来的源数据库表单信息 """
    # 对外接口无影响，仅供后台 Worker 和 Engine 流转使用
    task_id: Optional[str] = Field(default=None, description="任务唯一标识(内部流转专用)")

    db_type: str = Field(..., description="数据库类型：mysql, postgresql, oracle 等")
    host: str = Field(..., description="主机地址 IP")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    db_name: str = Field(..., description="要同步的数据库名")

    # 选填, 有默认值
    charset: Optional[str] = Field("utf8mb4", description="字符集")
    target_table: Optional[str] = Field(default=None, description="指定表名，不填则整库同步")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表，为空则全库同步")

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


# region ---- 任务管理 ----
class TaskCreateReq(BaseDecryptReq):
    task_name: str = Field(..., description="任务名称")
    # source_id: str = Field(..., description="关联的数据源ID")
    source_id: Optional[str] = Field(default=None, description="数据源ID")
    topic_or_table: Optional[str] = Field(default=None, description="custom_sql模式下目标库写入表名，普通模式可不传")
    schedule_cron: Optional[str] = Field(default=None, description="定时任务表达式")
    status: int = Field(default=1, description="任务状态：0停用, 1启用")
    sync_mode: str = Field(default="overwrite", description="冲突策略")
    collect_mode: Literal["full", "inc_id", "inc_time", "custom_sql"] = Field(default="full")
    incremental_column: Optional[str] = Field(default=None)
    last_watermark: Optional[str] = Field(default=None)
    custom_sql: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None, description="备注")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表")


class TaskUpdateReq(TaskCreateReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="要更新的任务ID(UUID)")


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
    source_id: str
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
