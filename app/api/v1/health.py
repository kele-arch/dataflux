# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/health.py
# @Created: 2026/7/28 11:50
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 服务存活、依赖就绪及 ARQ Worker 健康状态检查接口

import asyncio
import time
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.core import arq_pool as arq_module
from app.core import redis as redis_module
from app.core.influx_client import get_influx_client
from app.core.mongo import mongo_client
from app.db.session import collected_engine, engine
from app.schemas.health import HealthCheckReq, WorkerHealthReq
from app.schemas.response import BaseResponse
from app.services.scheduler_service import scheduler


router = APIRouter(prefix="/health", tags=["服务健康检查"])


async def _run_check(name: str, checker, required: bool = True, timeout: float = 5.0) -> dict:
    started = time.perf_counter()
    try:
        result = checker()
        if asyncio.iscoroutine(result):
            await asyncio.wait_for(result, timeout=timeout)
        return {
            "name": name,
            "status": "up",
            "required": required,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "down",
            "required": required,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(exc)[:500],
        }


def _check_sql(sql_engine):
    with sql_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


async def _check_redis():
    if redis_module.redis_client is None:
        raise RuntimeError("Redis 客户端未初始化")
    await redis_module.redis_client.ping()


async def _check_arq():
    if arq_module.arq_pool is None:
        raise RuntimeError("ARQ 连接池未初始化")
    await arq_module.arq_pool.ping()


async def _check_mongo():
    if mongo_client.client is None:
        raise RuntimeError("MongoDB 客户端未初始化")
    await mongo_client.client.admin.command("ping")


def _check_influx():
    client = get_influx_client()
    if not client.ping():
        raise RuntimeError("InfluxDB 查询失败")


@router.post("/live", summary="进程存活检查", response_model=BaseResponse)
async def live(req: HealthCheckReq):
    return BaseResponse(
        data={
            "status": "up",
            "service": "dataflux",
            "time": datetime.now().isoformat(),
        },
        msg="服务存活",
    )


@router.post("/dependencies", summary="全部依赖状态", response_model=BaseResponse)
async def dependencies(req: HealthCheckReq):
    checks = await asyncio.gather(
        _run_check("main_database", lambda: asyncio.to_thread(_check_sql, engine), timeout=req.timeout_seconds),
        _run_check(
            "collected_database",
            lambda: asyncio.to_thread(_check_sql, collected_engine),
            timeout=req.timeout_seconds,
        ),
        _run_check("redis", _check_redis, timeout=req.timeout_seconds),
        _run_check("arq", _check_arq, timeout=req.timeout_seconds),
        _run_check("mongodb", _check_mongo, required=False, timeout=req.timeout_seconds),
        _run_check(
            "influxdb",
            lambda: asyncio.to_thread(_check_influx),
            required=False,
            timeout=req.timeout_seconds,
        ),
    )
    required_ok = all(item["status"] == "up" for item in checks if item["required"])
    return BaseResponse(
        code=1 if required_ok else 0,
        data={
            "status": "up" if required_ok else "down",
            "scheduler": {
                "status": "up" if scheduler.running else "down",
                "jobs": len(scheduler.get_jobs()) if scheduler.running else 0,
            },
            "dependencies": checks,
            "time": datetime.now().isoformat(),
        },
        msg="依赖状态正常" if required_ok else "必要依赖存在异常",
    )


@router.post("/ready", summary="服务就绪检查", response_model=BaseResponse)
async def ready(req: HealthCheckReq):
    dependency_response = await dependencies(req)
    payload = dependency_response.data
    scheduler_ok = payload["scheduler"]["status"] == "up"
    ready_ok = payload["status"] == "up" and scheduler_ok
    payload["status"] = "ready" if ready_ok else "not_ready"
    return BaseResponse(
        code=1 if ready_ok else 0,
        data=payload,
        msg="服务已就绪" if ready_ok else "服务未就绪",
    )


@router.post("/workers", summary="ARQ Worker 与队列状态", response_model=BaseResponse)
async def workers(req: WorkerHealthReq):
    if arq_module.arq_pool is None:
        return BaseResponse(
            code=0,
            data={"status": "down", "queue_name": req.queue_name},
            msg="ARQ 连接池未初始化",
        )

    health_key = f"{req.queue_name}:health-check"
    health_value = await arq_module.arq_pool.get(health_key)
    queued_jobs = await arq_module.arq_pool.zcard(req.queue_name)
    worker_up = health_value is not None
    payload = {
        "status": "up" if worker_up else "down",
        "queue_name": req.queue_name,
        "health_key": health_key,
        "last_health": health_value.decode() if isinstance(health_value, bytes) else health_value,
        "queued_jobs": queued_jobs,
        "time": datetime.now().isoformat(),
    }
    return BaseResponse(
        code=1 if worker_up else 0,
        data=payload,
        msg="Worker 状态正常" if worker_up else "未检测到 Worker 心跳",
    )
