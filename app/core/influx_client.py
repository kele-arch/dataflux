# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/influx_client.py
# @Created: 2026/6/10 15:41
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: InfluxDB 3.x 客户端封装(基于原生 HTTP, 兼容 /api/v3 接口)

import json
import requests
from typing import Optional
from app.core import logger
from app.core.config import settings


class InfluxDBV3Client:
    """
    写入使用 Line Protocol(/api/v3/write_lp)
    查询使用 SQL(/api/v3/query_sql)
    """

    def __init__(self):
        self.base_url = settings.INFLUX_URL.rstrip("/")
        self.token = settings.INFLUX_TOKEN
        self.db = settings.INFLUX_DB
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "text/plain"
        }
        self.timeout = 10

    def write_line_protocol(self, lines: str) -> bool:
        """
        写入 Line Protocol 格式数据
        lines 示例:
            api_monitor,task_id=xxx,status_code=200 response_time=123.4,is_success=1
        """
        url = f"{self.base_url}/api/v3/write_lp"
        try:
            resp = requests.post(
                url,
                headers=self.headers,
                params={"db": self.db},
                data=lines.strip(),
                timeout=self.timeout
            )
            if resp.status_code not in (200, 204):
                logger.error(f"InfluxDB 写入失败: {resp.status_code} {resp.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"InfluxDB 写入异常: {e}")
            return False

    def query_sql(self, sql: str) -> list:
        """
        执行 SQL 查询, 返回 list[dict]
        """
        url = f"{self.base_url}/api/v3/query_sql"
        try:
            resp = requests.post(
                url,
                headers={**self.headers, "Content-Type": "application/json"},
                json={"db": self.db, "q": sql},
                timeout=self.timeout
            )
            if resp.status_code != 200:
                logger.error(f"InfluxDB 查询失败: {resp.status_code} {resp.text}")
                return []
            return resp.json() if resp.text else []
        except Exception as e:
            logger.error(f"InfluxDB 查询异常: {e}")
            return []

    def ping(self) -> bool:
        """ 连通性检测 """
        try:
            result = self.query_sql("SELECT 1")
            return True
        except Exception:
            return False


# 全局单例
_influx_client: Optional[InfluxDBV3Client] = None


async def init_influx():
    """ 应用启动时初始化 InfluxDB 连接并验证连通性 """
    global _influx_client
    _influx_client = InfluxDBV3Client()
    if _influx_client.ping():
        logger.success(f"InfluxDB 连接成功 | 地址:{settings.INFLUX_URL} | 数据库:{settings.INFLUX_DB}")
    else:
        logger.warning("InfluxDB 连接不通, 监控指标写入将静默失败")


async def close_influx():
    """ 应用关闭时清理 InfluxDB 连接 """
    global _influx_client
    if _influx_client:
        # requests 的 HTTP 连接池会自动回收, 这里预留关闭扩展点
        _influx_client = None
        logger.info("InfluxDB 连接已关闭")


def get_influx_client() -> InfluxDBV3Client:
    global _influx_client
    if _influx_client is None:
        _influx_client = InfluxDBV3Client()
    return _influx_client