# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/tsync.py
# @Created: 2026/6/5 10:07
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据同步任务管理

from fastapi import APIRouter, Depends, HTTPException, Form, Response, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import arq_pool as arq_module
from app.crud.crud_tsync import crud_task
from app.models.collectTaskModel import CollectTask
from app.schemas.tsync import DBSyncReq, TaskIdReq, TaskUpdateReq, TaskCreateReq, TaskPageQueryReq, TaskPageOut, \
    TaskOut, DashboardOut, TaskStatusReq
from app.schemas.response import BaseResponse
from app.services.sync_service import sync_database_architecture_and_data, DatabaseSyncEngine
from app.com.decorators import measure_time
from app.db.session import get_db
from app.core import logger
from app.services.scheduler_service import refresh_scheduler_jobs
from app.utils.cron_helper import generate_cron_expression
from app.services.task_control import set_task_status, TASK_PAUSED, TASK_CANCELLED, TASK_RUNNING

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
    try:
        # 拦截参数,翻译生成标准的 Cron 表达式
        cron_str = generate_cron_expression(req.schedule_type, req.schedule_value)

        # 直接赋值给原请求对象,对底层的 CRUD 零侵入
        req.schedule_cron = cron_str

        obj = crud_task.create(db, req)
        refresh_scheduler_jobs()

        return BaseResponse(data={"id": obj.id}, msg="任务创建成功")

    except ValueError as e:
        # 捕获我们在翻译层抛出的不合法异常
        return BaseResponse(code=0, msg=str(e))


@router.post("/update", summary="修改同步任务配置", response_model=BaseResponse)
def update_task(req: TaskUpdateReq, db: Session = Depends(get_db)):
    try:
        # 判断前端是否传了调度相关的修改
        if req.schedule_type is not None:
            cron_str = generate_cron_expression(req.schedule_type, req.schedule_value)
            req.schedule_cron = cron_str

        success = crud_task.update(db, req)
        if not success:
            return BaseResponse(code=0, msg="任务不存在或更新失败")

        refresh_scheduler_jobs()

        return BaseResponse(msg="任务更新成功")

    except ValueError as e:
        return BaseResponse(code=0, msg=str(e))


@router.post("/delete", summary="删除同步任务", response_model=BaseResponse)
def delete_task(req: TaskIdReq, db: Session = Depends(get_db)):
    success = crud_task.delete(db, req.task_id)
    if not success:
        return BaseResponse(code=0, msg="任务不存在")
    refresh_scheduler_jobs()
    return BaseResponse(msg="删除成功")


@router.post("/change_status", summary="切换任务启用/停用", response_model=BaseResponse)
def change_task_status(req: TaskStatusReq, db: Session = Depends(get_db)):
    success = crud_task.change_status(db, req.task_id, req.status)
    if not success:
        return BaseResponse(code=0, msg="任务不存在")
    refresh_scheduler_jobs()
    label = "启用" if req.status == 1 else "停用"
    return BaseResponse(msg=f"任务已{label}")


@router.post("/run", summary="手动执行数据同步任务", response_model=BaseResponse)
async def run_sync_task(req: TaskIdReq, db: Session = Depends(get_db)):
    """
   纯异步下发接口
    """
    # 确认任务存在且处于启用状态
    task = db.execute(select(CollectTask).where(CollectTask.id == req.task_id)).scalar_one_or_none()
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    if task.status == 0:
        return BaseResponse(code=0, msg="任务处于停用状态, 无法执行")

    # 将耗时的同步任务扔给后台独立 Worker 进程
    if arq_module.arq_pool:

        await arq_module.arq_pool.enqueue_job('run_sync_job', task.id)

        logger.info(f"手动触发同步任务 -> [ID:{task.id} 名称:{task.task_name}], 已推入后台队列")

        # 立即响应前端,不等待执行结果
        return BaseResponse(msg="执行指令已下发至后台队列,请稍后在日志中查看进度")
    else:
        logger.error("ARQ 队列池未初始化,无法下发手动执行任务")
        return BaseResponse(code=0, msg="系统队列服务未就绪, 下发失败")


# region ---- 任务状态控制 (中断/恢复) ----
@router.post("/pause", summary="暂停正在执行的任务", response_model=BaseResponse)
def pause_task(req: TaskIdReq):
    set_task_status(req.task_id, TASK_PAUSED)
    return BaseResponse(msg="暂停指令已下发, 任务将在当前批次完成后优雅暂停")


@router.post("/cancel", summary="取消正在执行的任务", response_model=BaseResponse)
def cancel_task(req: TaskIdReq):
    set_task_status(req.task_id, TASK_CANCELLED)
    return BaseResponse(msg="取消指令已下发, 任务将立即终止")


@router.post("/resume", summary="清理中断状态(恢复默认)", response_model=BaseResponse)
def resume_task(req: TaskIdReq):
    set_task_status(req.task_id, TASK_RUNNING)
    return BaseResponse(msg="状态锁已清理, 任务下一次将正常运行")


# endregion


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
