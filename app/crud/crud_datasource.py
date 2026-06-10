# -- coding: utf-8 --
# @Author: 胡H
# @File: app/crud/crud_datasource.py
# @Created: 2026/6/5 15:25
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from app.models.dataSourceModel import DataSource
from app.schemas.datasource import DataSourceCreateReq, DataSourceUpdateReq, DataSourcePageQueryReq


class CRUDDataSource:
    def create(self, db: Session, req: DataSourceCreateReq) -> DataSource:
        obj_in_data = req.model_dump(exclude_unset=True)
        db_obj = DataSource(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_id(self, db: Session, source_id: str) -> DataSource:
        return db.execute(select(DataSource).where(DataSource.id == source_id)).scalar_one_or_none()

    def update(self, db: Session, req: DataSourceUpdateReq) -> bool:
        obj_in_data = req.model_dump(exclude_unset=True, exclude={"source_id"})
        stmt = update(DataSource).where(DataSource.id == req.source_id).values(**obj_in_data)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def delete(self, db: Session, source_id: str) -> bool:
        stmt = delete(DataSource).where(DataSource.id == source_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def get_list(self, db: Session, req: DataSourcePageQueryReq) -> tuple[int, list]:
        # 动态排序
        sort_col = getattr(DataSource, req.sort_by or "create_time", DataSource.create_time)
        order = sort_col.desc() if req.sort_order == "desc" else sort_col.asc()
        stmt = select(DataSource).order_by(order)
        if req.name:
            stmt = stmt.where(DataSource.name.like(f"%{req.name}%"))
        if req.type:
            stmt = stmt.where(DataSource.type == req.type)

        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = db.execute(stmt.offset((req.page - 1) * req.size).limit(req.size)).scalars().all()
        return total, items


crud_datasource = CRUDDataSource()
