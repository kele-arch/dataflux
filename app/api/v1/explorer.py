# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/explorer.py
# @Created: 2026/6/15 17:40
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据探索模块API, 适用于各种数据库表结构的查询需求

from fastapi import APIRouter, Depends
from sqlalchemy import MetaData, Table, select, func, inspect, asc, desc
from sqlalchemy.orm import Session

from app.db.session import get_collected_db
from app.schemas.explorer import DynamicDataQueryReq, TableColumnsReq, TableListReq
from app.schemas.response import BaseResponse

router = APIRouter(prefix="/explorer", tags=["数据探索"])


@router.post("/tables/list", summary="获取系统所有数据表列表")
def get_all_tables(req: TableListReq, db: Session = Depends(get_collected_db)):
    """
    查询当前数据库下的所有物理表名, 支持关键字模糊搜索
     {"keyword": "kafka"} 或 {}
    """
    bind = db.get_bind()
    inspector = inspect(bind)

    tables = inspector.get_table_names()

    # 支持根据关键字过滤表名
    if req.keyword:
        keyword_lower = req.keyword.lower()
        tables = [t for t in tables if keyword_lower in t.lower()]

    return BaseResponse(code=1, data=tables, msg="获取表列表成功")


@router.post("/tables/columns", summary="获取表结构详细信息")
def get_table_columns(req: TableColumnsReq, db: Session = Depends(get_collected_db)):
    """
    获取指定表的列名、类型、是否为空等元数据
     {"table_name": "sys_data_source"}
    """
    bind = db.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table(req.table_name):
        return BaseResponse(code=0, msg=f"表 [{req.table_name}] 不存在")

    columns = inspector.get_columns(req.table_name)

    res_columns = []
    for col in columns:
        res_columns.append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "default": str(col.get("default")) if col.get("default") else None,
            "comment": col.get("comment")
        })

    return BaseResponse(code=1, data=res_columns, msg="获取表结构成功")


@router.post("/tables/data", summary="通用表数据分页与多条件查询")
def get_table_data(req: DynamicDataQueryReq, db: Session = Depends(get_collected_db)):
    """ 
    基于传入的动态条件, 分页查询任意表数据
     
    {
      "table_name": "sys_task_log",
      "page": 1,
      "size": 15,
      "filters": {"status": "success"},
      "like_filters": {"remark": "采集"}
    }
    """
    bind = db.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table(req.table_name):
        return BaseResponse(code=0, msg=f"表 [{req.table_name}] 不存在")

    metadata = MetaData()
    target_table = Table(req.table_name, metadata, autoload_with=bind)

    stmt = select(target_table)

    # 挂载精确匹配
    for k, v in req.filters.items():
        if k in target_table.c and v is not None:
            stmt = stmt.where(getattr(target_table.c, k) == v)

    # 挂载模糊匹配
    for k, v in req.like_filters.items():
        if k in target_table.c and v:
            stmt = stmt.where(getattr(target_table.c, k).like(f"%{v}%"))

    # 统计总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # 动态排序
    if req.sort_by and req.sort_by in target_table.c:
        sort_col = getattr(target_table.c, req.sort_by)
        stmt = stmt.order_by(desc(sort_col) if req.sort_order.lower() == "desc" else asc(sort_col))
    else:
        # 默认使用主键降序
        if target_table.primary_key.columns:
            pk_col = list(target_table.primary_key.columns)[0]
            stmt = stmt.order_by(desc(pk_col))

    # 分页
    stmt = stmt.offset((req.page - 1) * req.size).limit(req.size)

    # 获取数据转为字典
    rows = db.execute(stmt).mappings().all()

    return BaseResponse(code=1, data={
        "total": total,
        "items": [dict(row) for row in rows]
    }, msg="查询成功")
