# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/tsync.py
# @Created: 2026/6/5 10:07
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据同步任务管理
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Form, Response, Request, status
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.core import arq_pool as arq_module
from app.core.influx_client import get_influx_client
from app.crud.crud_tsync import crud_task
from app.models.collectTaskModel import CollectTask
from app.models.dataSourceModel import DataSource
from app.models.taskLogModel import TaskLog, FtpFileRecord, OssFileRecord
from app.schemas.tsync import DBSyncReq, TaskIdReq, TaskUpdateReq, TaskCreateReq, TaskPageQueryReq, TaskPageOut, \
    TaskOut, DashboardOut, TaskStatusReq, MonitorTrendReq, RecordQueryReq, TaskCleanReq
from app.schemas.response import BaseResponse
from app.services.kafka_manager import kafka_manager, _build_kafka_req
from app.services.mqtt_manager import mqtt_manager, _build_mqtt_req
from app.services.rabbitmq_manager import _build_rabbitmq_req, rabbitmq_manager
from app.services.sync_service import sync_database_architecture_and_data, DatabaseSyncEngine
from app.com.decorators import measure_time
from app.db.session import get_db
from app.core import logger
from app.services.scheduler_service import refresh_scheduler_jobs
from app.utils.cron_helper import generate_cron_expression
from app.services.task_control import set_task_status, TASK_PAUSED, TASK_CANCELLED, TASK_RUNNING, get_saved_watermark

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

        # 如果配置了清理 Cron，格式合法性校验
        if req.clean_cron and req.clean_cron.strip():
            try:
                generate_cron_expression("cron", req.clean_cron.strip())
            except ValueError as e:
                return BaseResponse(code=0, msg=f"清理Cron表达式格式非法: {e}")

        obj = crud_task.create(db, req)
        refresh_scheduler_jobs()

        return BaseResponse(data={"id": obj.id}, msg="任务创建成功")

    except ValueError as e:
        return BaseResponse(code=0, msg=str(e))


@router.post("/update", summary="修改同步任务配置", response_model=BaseResponse)
def update_task(req: TaskUpdateReq, db: Session = Depends(get_db)):
    try:
        # 判断前端是否传了调度相关的修改
        if req.schedule_type is not None:
            cron_str = generate_cron_expression(req.schedule_type, req.schedule_value)
            req.schedule_cron = cron_str

        # 如果配置了清理 Cron，格式合法性校验
        if req.clean_cron and req.clean_cron.strip():
            generate_cron_expression("cron", req.clean_cron.strip())

        success = crud_task.update(db, req)
        if not success:
            return BaseResponse(code=0, msg="任务不存在或更新失败")

        refresh_scheduler_jobs()

        return BaseResponse(msg="任务更新成功")

    except ValueError as e:
        return BaseResponse(code=0, msg=str(e))


@router.post("/delete", summary="删除同步任务", response_model=BaseResponse)
async def delete_task(req: TaskIdReq, db: Session = Depends(get_db)):
    # 删除前先检查是否为 Kafka/MQTT 常驻任务，是则先停 Consumer
    task = crud_task.get_by_id(db, req.task_id)
    if task:
        source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
        if source and source.type == "kafka":
            await kafka_manager.stop(req.task_id)
        if source and source.type == "mqtt":
            await mqtt_manager.stop(req.task_id)
        if source and source.type == "rabbitmq":
            await rabbitmq_manager.stop(req.task_id)

    success = crud_task.delete(db, req.task_id)
    if not success:
        return BaseResponse(code=0, msg="任务不存在")
    refresh_scheduler_jobs()
    return BaseResponse(msg="删除成功")


@router.post("/change_status", summary="切换任务启用/停用", response_model=BaseResponse)
async def change_task_status(req: TaskStatusReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    # 判断是否为 Kafka 任务（类型在 DataSource 表）
    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    is_kafka = source and source.type == "kafka"
    is_mqtt = source and source.type == "mqtt"
    is_rabbitmq = source and source.type == "rabbitmq"

    success = crud_task.change_status(db, req.task_id, req.status)
    if not success:
        return BaseResponse(code=0, msg="更新失败")

    refresh_scheduler_jobs()

    # Kafka 联动运行时状态
    if is_kafka:
        if req.status == 0:
            await kafka_manager.stop(req.task_id)
            logger.info(f"Kafka 任务 [{req.task_id}] 已停用, 底层 Consumer 已被强制停止")
        elif req.status == 1:
            logger.info(f"Kafka 任务 [{req.task_id}] 配置已启用, 等待用户手动点击启动按钮")

    # MQTT 联动运行时状态
    if is_mqtt:
        if req.status == 0:
            await mqtt_manager.stop(req.task_id)
            logger.info(f"MQTT 任务 [{req.task_id}] 已停用, 底层 Consumer 已被强制停止")
        elif req.status == 1:
            logger.info(f"MQTT 任务 [{req.task_id}] 配置已启用, 等待用户手动点击启动按钮")

    # RabbitMQ 联动运行时状态
    if is_rabbitmq:
        if req.status == 0:
            await rabbitmq_manager.stop(req.task_id)
            logger.info(f"RabbitMQ 任务 [{req.task_id}] 已停用, 底层 Consumer 已被强制停止")
        elif req.status == 1:
            logger.info(f"RabbitMQ 任务 [{req.task_id}] 配置已启用, 等待用户手动点击启动按钮")

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

    # 查数据源类型，过滤常驻流式任务
    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    source_type = source.type.lower() if source else ""
    if source_type in ("mqtt", "rabbitmq"):
        return BaseResponse(code=0, msg="MQTT/RabbitMQ 是常驻订阅任务，请使用专属 start/stop 接口启动")
    if source_type in ("kafka",):
        return BaseResponse(code=0, msg="Kafka 任务是常驻消费任务，请使用 /tsync/kafka/start 启动")

    # 将耗时的同步任务扔给后台独立 Worker 进程
    if not arq_module.arq_pool:
        logger.error("ARQ 队列池未初始化,无法下发手动执行任务")
        return BaseResponse(code=0, msg="系统队列服务未就绪, 下发失败")

    # 前置防抖拦截：检查分布式锁，防止产生僵尸 pending 记录
    lock_key = f"sync_task_lock:{req.task_id}"
    if await arq_module.arq_pool.exists(lock_key):
        return BaseResponse(code=0, msg="任务正在排队或执行中, 请勿重复触发")

    # 清理 Redis 控制信号
    set_task_status(req.task_id, TASK_RUNNING)

    # ORM 清理旧的 pending 僵尸日志
    db.execute(
        delete(TaskLog).where(TaskLog.task_id == task.id, TaskLog.status == "pending")
    )
    db.commit()

    # 创建 pending 占坑日志
    pending_log = TaskLog(
        task_id=task.id,
        task_name=task.task_name,
        status="pending",
        start_time=datetime.now()
    )
    db.add(pending_log)
    db.commit()
    db.refresh(pending_log)

    # 推入 ARQ 队列
    await arq_module.arq_pool.enqueue_job('run_sync_job', task.id)
    logger.info(f"手动触发同步任务 -> [ID:{task.id} 名称:{task.task_name}], 已推入后台队列")

    return BaseResponse(data={"log_id": pending_log.id, "status": "pending"}, msg="任务已进入执行队列")


# region ---- 任务状态控制 (中断/恢复) ----
@router.post("/pause", summary="暂停正在执行的任务", response_model=BaseResponse)
def pause_task(req: TaskIdReq):
    set_task_status(req.task_id, TASK_PAUSED)
    return BaseResponse(msg="暂停指令已下发, 任务将在当前批次完成后暂停")


@router.post("/cancel", summary="取消正在执行的任务", response_model=BaseResponse)
def cancel_task(req: TaskIdReq):
    set_task_status(req.task_id, TASK_CANCELLED)
    return BaseResponse(msg="取消指令已下发, 任务将立即终止")


@router.post("/resume", summary="恢复已暂停的任务(水位线持久化+自动入队)", response_model=BaseResponse)
async def resume_task(req: TaskIdReq, db: Session = Depends(get_db)):
    task = db.execute(select(CollectTask).where(CollectTask.id == req.task_id)).scalar_one_or_none()
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    if not arq_module.arq_pool:
        return BaseResponse(code=0, msg="系统队列服务未就绪")

    # 前置防抖：与 /run 一致，防止重复入队产生僵尸日志
    lock_key = f"sync_task_lock:{req.task_id}"
    if await arq_module.arq_pool.exists(lock_key):
        return BaseResponse(code=0, msg="任务正在排队或执行中, 请勿重复触发")

    # ORM 清理旧的 pending 僵尸日志
    db.execute(
        delete(TaskLog).where(TaskLog.task_id == task.id, TaskLog.status == "pending")
    )
    db.commit()

    # 打捞 Redis 断点水位线并回写数据库
    redis_watermark = get_saved_watermark(req.task_id)
    if redis_watermark:
        task.last_watermark = redis_watermark
        logger.info(f"任务 [{req.task_id}] 水位线已从 Redis 回写: {redis_watermark}")

    # 清除 Redis 控制信号
    set_task_status(req.task_id, TASK_RUNNING)

    # 自动生成续传 pending 日志
    pending_log = TaskLog(
        task_id=task.id,
        task_name=task.task_name,
        status="pending",
        start_time=datetime.now(),
        error_msg="断点续传任务启动中..."
    )
    db.add(pending_log)
    db.commit()
    db.refresh(pending_log)

    # 自动入队启动
    await arq_module.arq_pool.enqueue_job('run_sync_job', task.id)

    return BaseResponse(data={"log_id": pending_log.id, "status": "pending"}, msg="任务断点已恢复,成功重新入队运行")


# endregion


@router.post("/clean", summary="强制重置卡死任务(解锁+清理僵尸日志)", response_model=BaseResponse)
async def clean_task_zombie_state(req: TaskIdReq, db: Session = Depends(get_db)):
    # 清除 Redis 分布式锁和控制信号
    lock_key = f"sync_task_lock:{req.task_id}"
    control_key = f"task_control:{req.task_id}"
    if arq_module.arq_pool:
        await arq_module.arq_pool.delete(lock_key)
        await arq_module.arq_pool.delete(control_key)

    # 将该任务所有未结束的日志标记为 failed
    db.execute(
        delete(TaskLog).where(
            TaskLog.task_id == req.task_id,
            TaskLog.status.in_(["pending", "running"])
        )
    )
    db.commit()
    logger.warning(f"管理员手动清除了任务 [{req.task_id}] 的卡死锁及僵尸日志")
    return BaseResponse(msg="任务锁已解开，僵尸状态已强制重置，可以重新点击执行")


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


# region ---- 专属 Kafka 接口 ----
@router.post("/kafka/start", summary="启动Kafka常驻消费", response_model=BaseResponse)
async def kafka_start(req: TaskIdReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    # 通过关联 DataSource 判断类型
    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    if not source or source.type != "kafka":
        return BaseResponse(code=0, msg="任务关联的数据源不是Kafka类型")

    sync_req = _build_kafka_req(task)
    ok = await kafka_manager.start(sync_req)
    return BaseResponse(msg="Consumer已启动" if ok else "Consumer已在运行中")


@router.post("/kafka/stop", summary="停止Kafka常驻消费", response_model=BaseResponse)
async def kafka_stop(req: TaskIdReq):
    ok = await kafka_manager.stop(req.task_id)
    return BaseResponse(msg="Consumer已停止" if ok else "Consumer未在运行")


@router.post("/kafka/status", summary="查询Kafka消费状态", response_model=BaseResponse)
async def kafka_status(req: TaskIdReq):
    return BaseResponse(data={"status": kafka_manager.status(req.task_id)}, msg="获取成功")


# endregion


# region ----- kafka/mqtt 的 influx 数据获取 ----
@router.post("/monitor/trend", summary="获取队列任务运行监控时序数据", response_model=BaseResponse)
def get_task_monitor_trend(req: MonitorTrendReq, db: Session = Depends(get_db)):
    """
    自动识别 Kafka/MQTT 任务类型, 从对应的 InfluxDB measurement 查询时序数据
    """
    from app.core.influx_client import get_influx_client

    # 查任务关联的数据源类型, 确定查询哪个 measurement
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    source = db.execute(
        select(DataSource).where(DataSource.id == task.source_id)
    ).scalar_one_or_none()
    source_type = source.type.lower() if source else ""

    # 根据数据源类型选择对应的 InfluxDB measurement
    measurement_map = {
        "kafka": "kafka_monitor",
        "mqtt": "mqtt_monitor",
        "rabbitmq": "rabbitmq_monitor",
    }
    measurement = measurement_map.get(source_type)
    if not measurement:
        return BaseResponse(
            code=0,
            msg=f"该任务类型 [{source_type}] 不支持实时监控, 仅 Kafka/MQTT/RabbitMQ 常驻任务可用"
        )

    influx = get_influx_client()
    task_id_safe = req.task_id.replace("'", "")

    try:
        query_sql = f"""
                    SELECT
                        time,
                        consumed,
                        elapsed_ms
                    FROM "{measurement}"
                    WHERE task_id = '{task_id_safe}'
                      AND time >= now() - interval '{req.minutes} minutes'
                    ORDER BY time ASC
                """

        raw_data = influx.query_sql(query_sql)

        times = []
        consumed_list = []
        elapsed_list = []

        for row in raw_data:
            raw_time = str(row.get("time", ""))
            time_str = raw_time.split("T")[1][:8] if "T" in raw_time else raw_time

            times.append(time_str)
            consumed_list.append(row.get("consumed", 0))
            elapsed_list.append(row.get("elapsed_ms", 0))

        chart_data = {
            "xAxis": times,
            "series": {
                "consumed": consumed_list,
                "elapsed_ms": elapsed_list
            }
        }

        return BaseResponse(code=1, msg="获取监控数据成功", data=chart_data)

    except Exception as e:
        return BaseResponse(code=0, msg=f"查询 InfluxDB 监控数据失败: {str(e)}")


# endregion


# region ---- MQTT接口 ----

@router.post("/mqtt/start", summary="启动MQTT常驻订阅", response_model=BaseResponse)
async def mqtt_start(req: TaskIdReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    # db_type 在 DataSource 表, 需要关联查询
    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    if not source or source.type != "mqtt":
        return BaseResponse(code=0, msg="任务关联的数据源不是MQTT类型")

    sync_req = _build_mqtt_req(task)
    ok = await mqtt_manager.start(sync_req)

    return BaseResponse(msg="订阅已启动" if ok else "订阅已在运行中")


@router.post("/mqtt/stop", summary="停止MQTT常驻订阅", response_model=BaseResponse)
async def mqtt_stop(req: TaskIdReq):
    ok = await mqtt_manager.stop(req.task_id)
    return BaseResponse(msg="订阅已停止" if ok else "订阅未在运行")


@router.post("/mqtt/status", summary="查询MQTT订阅状态", response_model=BaseResponse)
async def mqtt_status(req: TaskIdReq):
    return BaseResponse(data={"status": mqtt_manager.status(req.task_id)}, msg="获取成功")


# endregion


# region ---- rabbitMQ接口 ----


@router.post("/rabbitmq/start", summary="启动RabbitMQ常驻消费", response_model=BaseResponse)
async def rabbitmq_start(req: TaskIdReq, db: Session = Depends(get_db)):
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    # db_type 在 DataSource 表, 需要关联查询
    source = db.execute(select(DataSource).where(DataSource.id == task.source_id)).scalar_one_or_none()
    if not source or source.type != "rabbitmq":
        return BaseResponse(code=0, msg="任务关联的数据源不是RabbitMQ类型")

    sync_req = _build_rabbitmq_req(task)
    ok = await rabbitmq_manager.start(sync_req)
    return BaseResponse(msg="消费已启动" if ok else "消费已在运行中")


@router.post("/rabbitmq/stop", summary="停止RabbitMQ常驻消费", response_model=BaseResponse)
async def rabbitmq_stop(req: TaskIdReq):
    ok = await rabbitmq_manager.stop(req.task_id)
    return BaseResponse(msg="消费已停止" if ok else "消费未在运行")


@router.post("/rabbitmq/status", summary="查询RabbitMQ消费状态", response_model=BaseResponse)
async def rabbitmq_status(req: TaskIdReq):
    return BaseResponse(data={"status": rabbitmq_manager.status(req.task_id)}, msg="获取成功")

# endregion


# region ---- 文件同步记录查询 ----
@router.post("/record/list", summary="获取同步文件明细记录(OSS / FTP)")
def get_sync_records(req: RecordQueryReq, db: Session = Depends(get_db)):
    """
    根据任务类型自动查询 oss_file_record 或 ftp_file_record 表,
    返回分页的文件级同步明细(文件名/大小/MD5/解析行数等)
    """
    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在", data=None)

    # 查 DataSource 判断是 OSS 还是 FTP
    source = db.execute(
        select(DataSource).where(DataSource.id == task.source_id)
    ).scalar_one_or_none()
    source_type = source.type.lower() if source else ""

    if source_type == "oss":
        model = OssFileRecord
        path_field = OssFileRecord.object_key
    elif source_type == "ftp":
        model = FtpFileRecord
        path_field = FtpFileRecord.remote_path
    else:
        return BaseResponse(
            code=0,
            msg=f"该任务类型 [{source_type}] 不支持文件记录查询, 仅 OSS / FTP 可用",
            data=None,
        )

    query = db.query(model).filter(model.task_id == req.task_id)

    if req.file_type:
        query = query.filter(model.file_type == req.file_type)

    total = query.count()
    offset = (req.page - 1) * req.page_size
    records = (
        query.order_by(model.create_time.desc())
        .offset(offset)
        .limit(req.page_size)
        .all()
    )

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "file_name": r.file_name,
            "file_path": getattr(r, path_field.name, None),
            "file_size": r.file_size,
            "md5": r.md5,
            "file_type": r.file_type,
            "is_parsed": r.is_parsed,
            "parsed_rows": r.parsed_rows,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
        })

    return BaseResponse(data={
        "total": total,
        "page": req.page,
        "page_size": req.page_size,
        "items": items,
    }, msg="获取成功")

# endregion


# region ---- 数据清理 ----
@router.post("/clean", summary="手动清理任务采集数据", response_model=BaseResponse)
def clean_task(req: TaskCleanReq, db: Session = Depends(get_db)):
    """
    action: truncate=清空 drop=删表 by_days=按天保留 by_count=按条数保留
    """
    from app.services.clean_service import clean_service

    task = crud_task.get_by_id(db, req.task_id)
    if not task:
        return BaseResponse(code=0, msg="任务不存在")

    table_name = task.topic_or_table or f"task_{req.task_id}"

    try:
        result = clean_service.clean_task_data(
            task_id=req.task_id,
            table_name=table_name,
            action=req.action,
            keep_days=req.keep_days,
            keep_count=req.keep_count,
            clean_files=req.clean_files,
        )
        return BaseResponse(data=result, msg="清理完成")
    except ValueError as e:
        return BaseResponse(code=0, msg=str(e))
    except Exception as e:
        logger.error(f"清理失败 [{req.task_id}]: {e}")
        return BaseResponse(code=0, msg=f"清理失败: {str(e)}")

# endregion
