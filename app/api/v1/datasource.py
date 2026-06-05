# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/datasource.py
# @Created: 2026/6/5 15:25
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from typing import List

from app.db.session import get_db
from app.schemas.response import BaseResponse
from app.schemas.datasource import (
    DataSourceCreateReq, DataSourceUpdateReq, DataSourceIdReq,
    DataSourcePageQueryReq, DataSourceOut, DataSourceBase, DataSourcePageOut
)
from app.crud.crud_datasource import crud_datasource

router = APIRouter(prefix="/datasource", tags=["数据源管理"])


@router.post("/test_connect", summary="测试数据库连接", response_model=BaseResponse)
def test_db_connection(req: DataSourceBase):
    try:
        db_type = req.type.lower()
        safe_pwd = quote_plus(req.password) if req.password else ""
        charset = (req.config_json or {}).get("charset", "utf8mb4")

        if db_type == "mysql":
            url = f"mysql+pymysql://{req.username}:{safe_pwd}@{req.host}:{req.port}/{req.db_name}?charset={charset}"
        elif db_type == "postgresql":
            url = f"postgresql+psycopg2://{req.username}:{safe_pwd}@{req.host}:{req.port}/{req.db_name}"
        else:
            return BaseResponse(code=0, msg=f"暂不支持测试该类型: {req.type}")

        engine = create_engine(url, connect_args={"connect_timeout": 3})

        with engine.connect() as conn:
            pass

        return BaseResponse(msg="连接成功！数据库通信正常。")

    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


@router.post("/add", summary="新增数据源", response_model=BaseResponse)
def add_datasource(req: DataSourceCreateReq, db: Session = Depends(get_db)):
    crud_datasource.create(db, req)
    return BaseResponse(msg="数据源保存成功")


@router.post("/update", summary="修改数据源", response_model=BaseResponse)
def update_datasource(req: DataSourceUpdateReq, db: Session = Depends(get_db)):
    success = crud_datasource.update(db, req)
    if not success:
        raise HTTPException(status_code=400, detail=f"该场景下已存在名为 [{req.name}] 的实体")
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
