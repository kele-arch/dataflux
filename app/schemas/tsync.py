# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tsync.py
# @Created: 2026/6/5 10:06
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from pydantic import Field
from typing import Optional, Literal
from app.schemas.base import BaseDecryptReq


class DBSyncReq(BaseDecryptReq):
    """ 接收前端传来的源数据库表单信息 """
    db_type: str = Field(..., description="数据库类型：mysql, postgresql, oracle 等")
    host: str = Field(..., description="主机地址 IP")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    db_name: str = Field(..., description="要同步的数据库名")

    # 选填, 有默认值
    charset: Optional[str] = Field("utf8mb4", description="字符集")
    target_table: Optional[str] = Field(default=None, description="指定表名，不填则整库同步")

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
