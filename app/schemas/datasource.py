# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/datasource.py
# @Created: 2026/6/5 15:24
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, List, Literal
from app.schemas.base import BaseDecryptReq


class DataSourceBase(BaseDecryptReq):
    name: str = Field(..., description="数据源名称，如：产线A_MySQL")
    # type: str = Field(..., description="数据源类型：mysql, postgresql")
    type: Literal["mysql", "postgresql", "oracle", "mongodb", "dm", "ftp"] = Field(..., description="数据库类型")
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口")
    db_name: str = Field(..., description="数据库名")
    username: Optional[str] = Field(default=None, description="用户名")
    password: Optional[str] = Field(default=None, description="密码")
    config_json: Optional[dict] = Field(default=None, description="高级配置(如 charset)")


class DataSourceCreateReq(DataSourceBase):
    pass


class DataSourceUpdateReq(DataSourceBase):
    source_id: str = Field(..., description="数据源的 UUID")


class DataSourceIdReq(BaseDecryptReq):
    source_id: str = Field(..., description="数据源的 UUID")


class DataSourcePageQueryReq(BaseDecryptReq):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    name: Optional[str] = Field(default=None, description="按名称模糊搜索")
    type: Optional[str] = Field(default=None, description="按类型过滤")
    sort_by: Optional[Literal["create_time", "name"]] = Field(default="create_time", description="排序字段")
    sort_order: Optional[Literal["asc", "desc"]] = Field(default="desc", description="排序方向")


# 响应序列化模型
class DataSourceOut(BaseModel):
    id: str
    name: str
    type: str
    host: str
    port: int
    db_name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    # 在序列化时过滤掉
    config_json: Optional[dict]

    model_config = ConfigDict(from_attributes=True)


class DataSourcePageOut(BaseModel):
    total: int
    items: List[DataSourceOut]
    model_config = ConfigDict(from_attributes=True)
