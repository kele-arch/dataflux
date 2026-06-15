# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/explorer.py
# @Created: 2026/6/15 17:40
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class TableListReq(BaseModel):
    keyword: Optional[str] = Field(default=None, description="表名模糊搜索(可选)")


# 2. 表结构请求模型
class TableColumnsReq(BaseModel):
    table_name: str = Field(..., description="目标表名")


# 3. 表数据动态查询请求模型
class DynamicDataQueryReq(BaseModel):
    table_name: str = Field(..., description="目标表名")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=15, ge=1, description="每页数量")

    # 动态等值过滤条件，例如: {"status": 1, "task_id": "xxx"}
    filters: Dict[str, Any] = Field(default_factory=dict, description="精确匹配条件")

    # 动态模糊过滤条件，例如: {"name": "test"} -> WHERE name LIKE '%test%'
    like_filters: Dict[str, str] = Field(default_factory=dict, description="模糊匹配条件")

    sort_by: Optional[str] = Field(default=None, description="排序字段名")
    sort_order: str = Field(default="desc", description="排序方式: asc 或 desc")
