# -- coding: utf-8 --
# @Author: 胡H
# @File: tsync.py
# @Created: 2026/6/5 10:07
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Form, Response, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.crud_tsync import crud_task
from app.models.collectTaskModel import CollectTask
from app.models.dataSourceModel import DataSource
from app.models.taskLogModel import TaskLog
from app.schemas.tsync import DBSyncReq, TaskIdReq, TaskUpdateReq, TaskCreateReq, TaskPageQueryReq, TaskPageOut, \
    TaskOut, DashboardOut
from app.schemas.response import BaseResponse
from app.services.sync_service import sync_database_architecture_and_data, DatabaseSyncEngine
from app.com.decorators import measure_time
from app.db.session import get_db
from app.core import logger

router = APIRouter(prefix="/tsync", tags=["数据同步任务管理"])


@router.post("/database", summary="全量克隆源数据库结构与数据", response_model=BaseResponse)
@measure_time  # 复用你写的耗时统计装饰器
def start_database_sync(req: DBSyncReq):
    try:
        # 这里由于迁移可能是 CPU 密集/IO 密集型,实际项目中建议放入 BackgroundTasks 或 线程池
        result = sync_database_architecture_and_data(req)
        return BaseResponse(data=result, msg="数据库同步成功")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"同步失败: {str(e)}")


# region ---- 任务管理接口 ----
@router.post("/list", summary="获取同步任务列表", response_model=BaseResponse[TaskPageOut])
def get_task_list(req: TaskPageQueryReq, db: Session = Depends(get_db)):
    result = crud_task.get_list(db, req)

    return BaseResponse(data=result, msg="获取列表成功")


@router.post("/add", summary="新增同步任务", response_model=BaseResponse)
def add_task(req: TaskCreateReq, db: Session = Depends(get_db)):
    crud_task.create(db, req)
    return BaseResponse(msg="任务创建成功")


@router.post("/update", summary="修改同步任务配置", response_model=BaseResponse)
def update_task(req: TaskUpdateReq, db: Session = Depends(get_db)):
    success = crud_task.update(db, req)
    if not success:
        return BaseResponse(code=0, msg="任务不存在或更新失败")
    return BaseResponse(msg="任务更新成功")


@router.post("/delete", summary="删除同步任务", response_model=BaseResponse)
def delete_task(req: TaskIdReq, db: Session = Depends(get_db)):
    success = crud_task.delete(db, req.task_id)
    if not success:
        return BaseResponse(code=0, msg="任务不存在")
    return BaseResponse(msg="删除成功")


@router.post("/run", summary="手动执行数据同步任务", response_model=BaseResponse[Any])
def run_sync_task(req: TaskIdReq, db: Session = Depends(get_db)):
    task = db.execute(select(CollectTask).where(CollectTask.id == req.task_id)).scalar_one_or_none()
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    if task.status == 0:
        return BaseResponse(code=0, msg="任务处于停用状态, 无法执行")

    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    if not source:
        return BaseResponse(code=0, msg="关联的数据源不存在")

    db_name = getattr(source, "db_name", None) or (source.config_json or {}).get("db_name")
    if not db_name:
        return BaseResponse(code=0, msg="数据源缺少 db_name 配置")

    sync_req = DBSyncReq(
        db_type=source.type,
        host=source.host,
        port=source.port,
        username=source.username,
        password=source.password,
        db_name=db_name,
        target_table=task.topic_or_table,
        sync_tables=task.sync_tables,
        sync_mode=getattr(task, "sync_mode", "overwrite"),
        collect_mode=task.collect_mode,
        incremental_column=task.incremental_column,
        last_watermark=task.last_watermark,
        custom_sql=task.custom_sql
    )

    task_log = TaskLog(
        task_id=task.id,
        task_name=task.task_name,
        status="running",
        start_time=datetime.now()
    )
    db.add(task_log)
    db.commit()
    db.refresh(task_log)  # 获取生成的 log_id

    try:
        logger.info(f"触发同步任务 -> [ID:{task.id} 名称:{task.task_name}]")
        engine = DatabaseSyncEngine(sync_req)

        result = engine.main()

        new_watermark = result.get("new_watermark")
        if new_watermark:
            task.last_watermark = str(new_watermark)
            db.commit()
            logger.info(f"任务[{task.task_name}] 高水位线已自动更新为: {new_watermark}")

        task_log.status = "success"
        task_log.end_time = datetime.now()
        task_log.tables_synced = result.get("tables_synced", 0)
        task_log.total_records = result.get("total_records", 0)
        db.commit()

        return BaseResponse(data=result, msg="任务执行完毕")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"任务执行异常: {error_msg}")

        task_log.status = "failed"
        task_log.end_time = datetime.now()
        task_log.error_msg = error_msg
        db.commit()
        return BaseResponse(code=0, msg=f"执行失败: {str(e)}")


@router.post("/detail", summary="获取任务详情", response_model=BaseResponse[TaskOut])
def get_task_detail(req: TaskIdReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")
    return BaseResponse(data=TaskOut.model_validate(task), msg="获取成功")


# endregion


# region ---- 仪表盘统计 ----
@router.post("/dashboard", summary="仪表盘统计", response_model=BaseResponse[DashboardOut])
def get_dashboard_stats(db: Session = Depends(get_db)):
    data = crud_task.get_dashboard_data(db)
    return BaseResponse(data=data, msg="获取成功")
# endregion
