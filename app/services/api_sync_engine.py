# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/api_sync_engine.py
# @Created: 2026/6/10 15:41
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: HTTP 接口采集：业务数据入PG, 监控指标入InfluxDB

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import Table, Column, Text, MetaData, String
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import JSON

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.task_control import get_task_status, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException


class ApiSyncEngine:
    """
    HTTP 接口采集
    支持:
      - monitor 模式: 监控接口健康, 响应时间/状态码 -> InfluxDB
      - data    模式: 抽取响应体业务数据 -> PG(JSON列存储)
      - both    模式: 两者同时进行(默认)
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = getattr(settings, "BATCH_SIZE", 1000)

    #  状态探测

    def _check_task_status(self):
        status = get_task_status(str(self.req.task_id))
        if status == TASK_PAUSED:
            raise TaskPausedException("接口采集任务已暂停")
        if status == TASK_CANCELLED:
            raise TaskCancelledException("接口采集任务已取消")

    #  HTTP 请求

    def _request(self) -> tuple:
        """
        发起 HTTP 请求
        返回: (response, elapsed_ms, status_code, is_success)
        请求失败时 response 为 None
        """
        method = (self.req.api_method or "GET").upper()
        url = self.req.api_url
        headers = self.req.api_headers or {}
        body = self.req.api_body

        start = time.time()
        try:
            with httpx.Client(timeout=30, verify=False) as client:
                resp = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method in ("POST", "PUT", "PATCH") else None,
                    params=body if method == "GET" and body else None,
                )
            elapsed_ms = round((time.time() - start) * 1000, 2)
            is_success = resp.is_success
            logger.info(f"接口请求完成: {method} {url} -> {resp.status_code} ({elapsed_ms}ms)")
            return resp, elapsed_ms, resp.status_code, is_success

        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"接口请求失败: {method} {url} -> {e} ({elapsed_ms}ms)")
            return None, elapsed_ms, 0, False

    #  InfluxDB 写入

    def _write_monitor_to_influx(
            self,
            task_id: str,
            elapsed_ms: float,
            status_code: int,
            is_success: bool,
            response_size: int,
            error_msg: str = ""
    ):
        """
        将本次请求的监控指标写入 InfluxDB(Line Protocol)
        measurement: api_monitor
        tags:  task_id, api_url, method, status_code
        fields: response_time, is_success, response_size
        """
        # tag 值不能有空格和逗号, 需要转义
        task_id_safe = task_id.replace(" ", "_")
        url_safe = (self.req.api_url or "").replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")
        method_safe = (self.req.api_method or "GET").upper()

        # 拼装 Line Protocol
        tags = (
            f"task_id={task_id_safe},"
            f"method={method_safe},"
            f"status_code={status_code},"
            f"url={url_safe}"
        )
        fields = (
            f"response_time={elapsed_ms},"
            f"is_success={1 if is_success else 0}i,"
            f"response_size={response_size}i"
        )

        # error_msg 有内容时附加(字符串 field 用双引号)
        if error_msg:
            safe_error = error_msg.replace('"', '\\"').replace("\n", " ")[:200]
            fields += f',error_msg="{safe_error}"'

        line = f"api_monitor,{tags} {fields}"

        influx = get_influx_client()
        success = influx.write_line_protocol(line)
        if success:
            logger.info(f"监控指标已写入 InfluxDB: status={status_code}, time={elapsed_ms}ms")
        else:
            logger.warning("监控指标写入 InfluxDB 失败, 不影响主流程")

    #  业务数据提取

    def _extract_data(self, body) -> list:
        """
        从响应体中按 api_data_path 提取业务数据列表
        支持点分路径: "data.items" 或 "$.data.items"
        不指定则整个响应体作为一条记录
        """
        if not self.req.api_data_path:
            if isinstance(body, list):
                return body
            return [body]

        # 去掉 JSONPath 前缀
        path = self.req.api_data_path.lstrip("$").lstrip(".")
        keys = path.split(".") if path else []

        data = body
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
                if data is None:
                    logger.warning(f"api_data_path 路径节点 [{key}] 在响应体中不存在, 返回空列表")
                    return []
            else:
                logger.warning(f"路径中间节点不是 dict, 当前类型: {type(data).__name__}, 返回空列表")
                return []

        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        elif data is not None:
            return [{"value": str(data)}]
        return []

    #  JSON 序列化清洗

    def _sanitize_for_json(self, obj) -> dict:
        """
        强制 JSON 序列化再反序列化
        确保所有特殊类型(datetime、bytes等)都被转为基础类型
        PG 的 JSON 列能正常接受
        """
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"raw": str(obj)}

    #  PG 目标表准备

    def _prepare_target_table(self, table_name: str) -> Table:
        """
        准备 PG 目标表
        固定结构:
          id           VARCHAR(32) UUID 主键
          raw_doc      JSON        响应数据(原生 JSON, 非 JSONB)
          collected_at TEXT        采集时间(ISO 字符串)
        """
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("raw_doc", JSON, nullable=False),
            Column("collected_at", Text, nullable=True),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"PG 目标表 [{table_name}] 已就绪(id UUID + raw_doc JSON + collected_at)")
        return table

    #  PG 写入(业务数据)

    def _ingest_to_pg(self, rows: list) -> int:
        """
        将业务数据分批写入 PG
        每条记录存为一行 raw_doc(JSON)
        """
        if not rows:
            logger.warning("响应体解析结果为空, 无数据写入 PG")
            return 0

        # 传了就直接用，没传则从 URL 中自动切出路径末段作为表名
        target_table_name = self.req.target_table
        if not target_table_name:
            from urllib.parse import urlparse
            path_parts = [p for p in urlparse(self.req.api_url).path.split('/') if p]
            url_stem = path_parts[-1] if path_parts else "data"
            target_table_name = f"api_{url_stem}"
            logger.info(f"未指定 target_table, 自动根据URL生成独立表名: {target_table_name}")
        target_table = self._prepare_target_table(target_table_name)
        collected_at = datetime.now(timezone.utc).isoformat()
        total_inserted = 0

        with self.target_engine.begin() as conn:
            for i in range(0, len(rows), self.batch_size):
                self._check_task_status()

                batch = [
                    {
                        "id": uuid.uuid4().hex,
                        "raw_doc": self._sanitize_for_json(row),
                        "collected_at": collected_at
                    }
                    for row in rows[i: i + self.batch_size]
                ]

                conn.execute(pg_insert(target_table).values(batch))
                total_inserted += len(batch)
                logger.info(f"已写入 {total_inserted}/{len(rows)} 条")

        logger.info(f"业务数据写入 PG 完成, 共 {total_inserted} 条 -> [{target_table_name}]")
        return total_inserted

    def main(self) -> dict:
        """

        """
        if not self.req.api_url:
            raise ValueError("接口采集必须指定 api_url")

        task_id = str(self.req.task_id)
        extract_mode = getattr(self.req, "api_extract_mode", "both") or "both"
        start_time = time.time()

        logger.info(
            f"启动接口采集: {self.req.api_method or 'GET'} {self.req.api_url}, 模式: {extract_mode}, 数据路径: {self.req.api_data_path or '整体响应'}"
        )

        try:
            # 探测任务状态
            self._check_task_status()

            # 发起 HTTP 请求
            resp, elapsed_ms, status_code, is_success = self._request()
            response_size = len(resp.content) if resp else 0
            error_msg = "" if is_success else (resp.text[:200] if resp else "网络请求异常")

            # 监控指标 -> InfluxDB(monitor / both 模式)
            if extract_mode in ("monitor", "both"):
                self._write_monitor_to_influx(
                    task_id=task_id,
                    elapsed_ms=elapsed_ms,
                    status_code=status_code,
                    is_success=is_success,
                    response_size=response_size,
                    error_msg=error_msg
                )

            # 请求失败, 记录失败结果并返回
            if not is_success or resp is None:
                logger.error(f"接口请求失败, status={status_code}, 跳过业务数据解析")
                return {
                    "status": "failed",
                    "tables_synced": 0,
                    "total_records": 0,
                    "new_watermark": None,
                    "table_details": [],
                    "monitor": {
                        "status_code": status_code,
                        "response_time_ms": elapsed_ms,
                        "is_success": False,
                        "error": error_msg
                    }
                }

            # 业务数据 -> PG(data / both 模式)
            parsed_rows = 0
            if extract_mode in ("data", "both"):
                self._check_task_status()
                try:
                    body = resp.json()
                    rows = self._extract_data(body)
                    logger.info(f"响应体解析完成, 提取到 {len(rows)} 条业务数据")
                    parsed_rows = self._ingest_to_pg(rows)
                except json.JSONDecodeError:
                    logger.warning(
                        f"响应体不是合法 JSON, 跳过业务数据入库 "
                        f"Content-Type: {resp.headers.get('content-type', 'unknown')}"
                    )
                except Exception as e:
                    logger.error(f"业务数据入库失败: {e}")
                    raise

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"接口采集完成, 耗时 {elapsed}s, 业务数据: {parsed_rows} 条")

            # 智能表名推导逻辑
            _tbl = self.req.target_table
            if not _tbl:
                from urllib.parse import urlparse
                _parts = [p for p in urlparse(self.req.api_url).path.split('/') if p]
                _tbl = f"api_{_parts[-1]}" if _parts else "api_data"

            return {
                "status": "success",
                "tables_synced": 1 if parsed_rows > 0 else 0,
                "total_records": parsed_rows,
                "new_watermark": None,
                "table_details": [{
                    "name": self.req.api_url,
                    "target_name": _tbl,
                    "records": parsed_rows,
                    "cost_seconds": elapsed,
                    "high_watermark": None
                }],
                "monitor": {
                    "status_code": status_code,
                    "response_time_ms": elapsed_ms,
                    "is_success": is_success,
                    "response_size": response_size
                }
            }

        except (TaskPausedException, TaskCancelledException):
            raise

        except Exception as e:
            logger.error(f"接口采集异常: {e}")
            raise
