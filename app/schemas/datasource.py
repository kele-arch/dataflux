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
    type: Literal[
        "mysql", "postgresql", "oracle", "mongodb", "dm", "ftp", "api", "snmp", "socket", "kafka", "sqlite", "mqtt", "rabbitmq", "oss"] = Field(
        ..., description="数据库类型")
    host: str = Field(default="", description="主机地址（API/Kafka 等可留空）")
    port: int = Field(default=0, description="端口（API/Kafka 等可填 0）")
    db_name: Optional[str] = Field(default=None, description="数据库名（API/Kafka 等可留空）")
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


# region ---- FTP 目录勘探 ----
class FtpExploreReq(BaseModel):
    datasource_id: str = Field(..., min_length=32, max_length=32, description="数据源 UUID")
    remote_path: Optional[str] = Field("/", description="勘探的远程起始路径，默认根目录 /")
    recursive: Optional[bool] = Field(False, description="是否递归获取全量树（懒加载模式传 False）")
    max_depth: Optional[int] = Field(2, ge=1, le=5, description="递归最大深度 (1-5)，防止深层目录卡死")

    model_config = ConfigDict(from_attributes=True)


# endregion

# region ---- OSS 目录勘探 ----
class OssTreeReq(BaseModel):
    source_id: str = Field(..., description="关联的数据源ID")
    prefix: str = Field(default="", description="当前所在目录的前缀，查根目录传空字符串。例如：'cjcy_files/'")

# endregion
