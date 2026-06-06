# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/datasource.py
# @Created: 2026/6/5 15:25
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, inspect
from typing import List, Dict, Any

from app.db.session import get_db
from app.schemas.response import BaseResponse
from app.schemas.datasource import (
    DataSourceCreateReq, DataSourceUpdateReq, DataSourceIdReq,
    DataSourcePageQueryReq, DataSourceOut, DataSourceBase, DataSourcePageOut
)
from app.crud.crud_datasource import crud_datasource
from app.utils.db_helper import build_db_url

router = APIRouter(prefix="/datasource", tags=["数据源管理"])


@router.post("/test_connect", summary="测试数据库连接", response_model=BaseResponse)
def test_db_connection(req: DataSourceBase):
    try:
        url = build_db_url(req)

        engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            with engine.connect():
                pass
        finally:
            engine.dispose()

        return BaseResponse(msg="连接成功！数据库通信正常。")

    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


@router.post("/add", summary="新增数据源", response_model=BaseResponse)
def add_datasource(req: DataSourceCreateReq, db: Session = Depends(get_db)):
    obj = crud_datasource.create(db, req)
    return BaseResponse(data={"id": obj.id}, msg="数据源保存成功")


@router.post("/update", summary="修改数据源", response_model=BaseResponse)
def update_datasource(req: DataSourceUpdateReq, db: Session = Depends(get_db)):
    success = crud_datasource.update(db, req)
    if not success:
        return BaseResponse(code=0, msg=f"该场景下已存在名为 [{req.name}] 的实体")
    return BaseResponse(msg="数据源更新成功")


@router.post("/delete", summary="删除数据源", response_model=BaseResponse)
def delete_datasource(req: DataSourceIdReq, db: Session = Depends(get_db)):
    success = crud_datasource.delete(db, req.source_id)
    if not success:
        return BaseResponse(code=0, msg="删除失败")
    return BaseResponse(msg="数据源已删除")


@router.post("/list", summary="获取数据源列表", response_model=BaseResponse[DataSourcePageOut])
def get_datasource_list(req: DataSourcePageQueryReq, db: Session = Depends(get_db)):
    # 直接拿到 total 和 ORM 对象列表 (items)
    total, items = crud_datasource.get_list(db, req)

    return BaseResponse(data={"total": total, "items": items}, msg="获取成功")


@router.post("/tables", summary="获取该数据源下的所有表名", response_model=BaseResponse[List[str]])
def get_datasource_tables(req: DataSourceIdReq, db: Session = Depends(get_db)):
    source = crud_datasource.get_by_id(db, req.source_id)
    if not source:
        return BaseResponse(code=0, msg="数据源不存在")

    try:
        url = build_db_url(source)
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            inspector = inspect(engine)
            return BaseResponse(data=inspector.get_table_names(), msg="获取成功")
        finally:
            engine.dispose()
    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


@router.post("/tables/detail", summary="获取表结构详情(含表注释和字段注释)", response_model=BaseResponse[List[Dict[str, Any]]])
def get_datasource_tables_detail(req: DataSourceIdReq, db: Session = Depends(get_db)):
    """返回每张表的表名、表注释、字段名、字段类型、字段注释"""
    source = crud_datasource.get_by_id(db, req.source_id)
    if not source:
        return BaseResponse(code=0, msg="数据源不存在")

    try:
        url = build_db_url(source)
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            inspector = inspect(engine)
            result = []

            for table_name in inspector.get_table_names():
                # 表注释
                table_comment = (inspector.get_table_comment(table_name) or {}).get("text") or ""

                # 字段信息
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        "name": col["name"],
                        "type": str(col["type"]),
                        "comment": col.get("comment") or ""
                    })

                result.append({
                    "table_name": table_name,
                    "table_comment": table_comment,
                    "columns": columns
                })

            return BaseResponse(data=result, msg="获取成功")
        finally:
            engine.dispose()
    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")
