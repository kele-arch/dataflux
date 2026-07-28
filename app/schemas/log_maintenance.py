# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/log_maintenance.py
# @Created: 2026/7/28 16:39
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 日志容量统计、清理预览、执行清理与导出请求模型

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.base import BaseDecryptReq


ClosedLogStatus = Literal["success", "failed", "paused", "cancelled"]
LogStatus = Literal["pending", "running", "success", "failed", "paused", "cancelled"]


class LogStatsReq(BaseDecryptReq):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32, description="按任务统计；不传统计全部")


class LogCleanPreviewReq(BaseDecryptReq):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32, description="按任务清理；不传匹配全部任务")
    statuses: list[ClosedLogStatus] = Field(default_factory=lambda: ["success"], description="允许清理的已结束状态")
    keep_days: Optional[int] = Field(default=90, ge=1, le=3650, description="保留最近 N 天")
    before_time: Optional[datetime] = Field(default=None, description="删除该时间以前的日志，优先于 keep_days")
    max_delete: int = Field(default=100000, ge=1, le=500000, description="单次最多删除的任务日志数")

    @model_validator(mode="after")
    def validate_filter(self):
        if not self.statuses:
            raise ValueError("statuses 不能为空")
        if self.before_time is None and self.keep_days is None:
            raise ValueError("before_time 和 keep_days 至少传一个")
        return self


class LogCleanReq(LogCleanPreviewReq):
    confirm: bool = Field(..., description="必须传 true 才执行删除")

    @model_validator(mode="after")
    def validate_confirm(self):
        if not self.confirm:
            raise ValueError("执行日志清理必须确认 confirm=true")
        return self


class LogExportReq(BaseDecryptReq):
    task_id: Optional[str] = Field(default=None, min_length=32, max_length=32, description="按任务导出；不传导出全部")
    statuses: Optional[list[LogStatus]] = Field(default=None, description="状态过滤；不传不过滤")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    include_task_logs: bool = Field(default=True, description="是否导出任务级日志")
    include_execution_logs: bool = Field(default=True, description="是否导出表级日志")
    max_rows: int = Field(default=50000, ge=1, le=100000, description="每类日志最大导出行数")

    @model_validator(mode="after")
    def validate_export(self):
        if not self.include_task_logs and not self.include_execution_logs:
            raise ValueError("至少选择一种日志类型")
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("start_time 不能晚于 end_time")
        return self
