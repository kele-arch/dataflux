# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/monitor.py
# @Created: 2026/6/11 10:25
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: InfluxDB 监控查询接口

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.influx_client import get_influx_client
from app.schemas.response import BaseResponse

router = APIRouter(prefix="/monitor", tags=["监控查询"])


# region ---- schema校验 ----
class TaskReq(BaseModel):
    task_id: str = Field(..., description="任务ID")


class TrendReq(BaseModel):
    task_id: str = Field(..., description="任务ID")
    interval: str = Field("1 hour", description="聚合粒度: 1 hour / 5 minutes")


class LogsReq(BaseModel):
    task_id: str = Field(..., description="任务ID")
    limit: int = Field(50, ge=1, le=500, description="返回条数(1-500)")


class SeriesQueryReq(BaseModel):
    task_id: str = Field(..., description="任务ID")
    start_time: str = Field(..., description="开始时间(如 2026-06-10T00:00:00Z)")
    end_time: str = Field(..., description="结束时间(如 2026-06-11T00:00:00Z)")
    window: str = Field("5m", description="聚合粒度: 1m, 5m, 15m, 1h, 1d")


# endregion

@router.post("/stats", summary="24小时监控统计卡片", response_model=BaseResponse)
def get_monitor_stats(req: TaskReq):
    """
    返回该任务过去 24 小时的:
      - total_requests  总调用次数
      - avg_time_ms     平均响应时间(ms)
      - success_rate    成功率(%)
    """
    safe_task_id = req.task_id.replace("'", "").replace(";", "")
    influx = get_influx_client()
    sql = f"""
        SELECT
            COUNT(*) as total_requests,
            ROUND(AVG(response_time), 2) as avg_time_ms,
            ROUND(SUM(is_success) * 100.0 / COUNT(*), 2) as success_rate
        FROM api_monitor
        WHERE task_id = '{safe_task_id}' AND time >= now() - interval '24 hours'
    """
    result = influx.query_sql(sql)
    return BaseResponse(data=result[0] if result else {}, msg="获取成功")


@router.post("/trend", summary="耗时与并发趋势图", response_model=BaseResponse)
def get_monitor_trend(req: TrendReq):
    """
    返回过去 24 小时的时间分桶聚合数据:
      - _time          时间点
      - request_count  该时间段请求次数
      - avg_time_ms    平均耗时(ms)
    用于 Echarts 折线图
    """
    safe_task_id = req.task_id.replace("'", "").replace(";", "")
    influx = get_influx_client()
    sql = f"""
        SELECT
            date_bin(interval '{req.interval}', time) as _time,
            COUNT(*) as request_count,
            ROUND(AVG(response_time), 2) as avg_time_ms
        FROM api_monitor
        WHERE task_id = '{safe_task_id}' AND time >= now() - interval '24 hours'
        GROUP BY _time
        ORDER BY _time ASC
    """
    result = influx.query_sql(sql)
    return BaseResponse(data=result, msg="获取成功")


@router.post("/logs", summary="最新调用明细日志", response_model=BaseResponse)
def get_monitor_logs(req: LogsReq):
    """
    返回最新的 N 条调用明细:
      - api_url        请求地址
      - method         请求方法
      - status_code    响应状态码
      - response_time  响应时间(ms)
      - error_msg      错误信息
      - time           采集时间
    注意：500 状态码建议前端高亮标红
    """
    safe_task_id = req.task_id.replace("'", "").replace(";", "")
    influx = get_influx_client()
    sql = f"""
            SELECT *
            FROM api_monitor
            WHERE task_id = '{safe_task_id}'
            ORDER BY time DESC
            LIMIT {req.limit}
        """
    result = influx.query_sql(sql)
    return BaseResponse(data=result, msg="获取成功")


@router.post("/series/query", summary="高级时序详细展示接口（动态降采样）", response_model=BaseResponse)
def query_monitor_series(req: SeriesQueryReq):
    """
    根据前端传的时间范围和粒度，动态生成 InfluxDB 3.x SQL
    window 映射关系：'1m' -> INTERVAL '1 minute', '5m' -> INTERVAL '5 minutes' ...
    """
    safe_task_id = req.task_id.replace("'", "").replace(";", "")

    # 将前端的简写 window 转换为标准 SQL 间隔
    window_map = {
        "1m": "1 minute",
        "5m": "5 minutes",
        "15m": "15 minutes",
        "1h": "1 hour",
        "1d": "1 day"
    }
    sql_interval = window_map.get(req.window, "5 minutes")

    # 动态拼装 InfluxDB 3.x 独有的 DATE_BIN（时间分桶）SQL 语法
    sql = f"""
        SELECT 
            DATE_BIN(INTERVAL '{sql_interval}', time) as time_bucket,
            COUNT(*) as request_count,
            ROUND(AVG(response_time), 2) as avg_latency_ms,
            ROUND(MAX(response_time), 2) as max_latency_ms,
            ROUND(SUM(is_success) * 100.0 / COUNT(*), 2) as success_rate
        FROM api_monitor
        WHERE task_id = '{safe_task_id}'
          AND time >= '{req.start_time}'
          AND time <= '{req.end_time}'
        GROUP BY time_bucket
        ORDER BY time_bucket ASC
    """

    influx = get_influx_client()
    series_data = influx.query_sql(sql)

    response_payload = {
        "series": series_data,
        "meta": {
            "window_used": req.window,
            "data_points": len(series_data)
        }
    }

    return BaseResponse(data=response_payload, msg="获取成功")
