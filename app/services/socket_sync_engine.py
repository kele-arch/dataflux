# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/socket_sync_engine.py
# @Created: 2026/6/13 9:45
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 原生 Socket 采集: 主动发送指令获取响应, 监控入InfluxDB, 数据入PG

import hashlib
import json
import socket
import time
from datetime import datetime, timezone

from sqlalchemy import Table, Column, String, MetaData, JSON
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.task_control import get_task_status, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException


class SocketSyncEngine:
    """
    原生 Socket 采集(主动请求-响应模式)
      - 建立 TCP/UDP 连接 -> 发送指令 -> 接收响应
      - 监控指标(延迟/是否成功)-> InfluxDB
      - 解析响应内容 -> PG(JSON)
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = getattr(settings, "BATCH_SIZE", 1000)

    #  状态探测

    def _check_task_status(self):
        status = get_task_status(str(self.req.task_id))
        if status == TASK_PAUSED:
            raise TaskPausedException("Socket 采集任务已暂停")
        if status == TASK_CANCELLED:
            raise TaskCancelledException("Socket 采集任务已取消")

    #  请求-响应

    def _build_command_bytes(self) -> bytes:
        """
        根据 socket_command_encoding 构建发送的字节内容
        支持: utf-8(普通文本)/ hex(十六进制字符串, 用于二进制协议)
        """
        command = self.req.socket_command or ""
        encoding = (self.req.socket_command_encoding or "utf-8").lower()

        if encoding == "hex":
            # 十六进制字符串转字节, 如 "01 02 0A" 或 "01020A"
            hex_str = command.replace(" ", "").replace("\\x", "")
            return bytes.fromhex(hex_str)
        else:
            return command.encode(encoding)

    def _request(self) -> tuple:
        """
        建立连接 -> 发送指令 -> 接收响应
        返回: (响应bytes, elapsed_ms, is_success, error_msg)
        """
        host = self.req.host
        port = self.req.port
        protocol = (self.req.socket_protocol or "tcp").lower()
        timeout = self.req.socket_timeout or 10
        recv_size = self.req.socket_recv_size or 4096
        terminator = self.req.socket_command_encoding and self.req.socket_terminator

        start = time.time()
        sock = None

        try:
            if protocol == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((host, port))
            else:  # udp
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)

            command_bytes = self._build_command_bytes()

            if protocol == "tcp":
                sock.sendall(command_bytes)
            else:
                sock.sendto(command_bytes, (host, port))

            # 接收响应
            response = b""
            terminator_bytes = self.req.socket_terminator.encode("utf-8") if self.req.socket_terminator else None

            if protocol == "udp":
                # UDP 一次性接收
                response, _ = sock.recvfrom(recv_size)
            else:
                # TCP: 按终止符或超时持续接收
                while True:
                    self._check_task_status()
                    try:
                        chunk = sock.recv(recv_size)
                    except socket.timeout:
                        break  # 超时即认为接收完毕
                    if not chunk:
                        break
                    response += chunk
                    if terminator_bytes and response.endswith(terminator_bytes):
                        break
                    if not terminator_bytes:
                        # 没有终止符配置时, 读到一次数据就认为完成(避免无限阻塞)
                        break

            elapsed_ms = round((time.time() - start) * 1000, 2)
            logger.info(f"Socket 请求完成: {protocol}://{host}:{port} -> {len(response)} bytes ({elapsed_ms}ms)")
            return response, elapsed_ms, True, ""

        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"Socket 请求失败: {host}:{port} -> {e} ({elapsed_ms}ms)")
            return b"", elapsed_ms, False, str(e)

        finally:
            if sock:
                sock.close()

    #  InfluxDB 写入(监控指标)

    def _write_monitor_to_influx(self, task_id: str, elapsed_ms: float, is_success: bool,
                                 response_size: int, error_msg: str = ""):
        task_id_safe = task_id.replace(" ", "_")
        host_safe = (self.req.host or "unknown").replace(" ", "_")
        protocol = (self.req.socket_protocol or "tcp").upper()

        fields = (
            f"response_time={elapsed_ms},"
            f"is_success={1 if is_success else 0}i,"
            f"response_size={response_size}i"
        )
        if error_msg:
            safe_error = error_msg.replace('"', '\\"')[:200]
            fields += f',error_msg="{safe_error}"'

        line = f"socket_monitor,task_id={task_id_safe},host={host_safe},protocol={protocol},port={self.req.port} {fields}"

        influx = get_influx_client()
        success = influx.write_line_protocol(line)
        if success:
            logger.info(f"Socket 监控指标已写入 InfluxDB: time={elapsed_ms}ms, success={is_success}")
        else:
            logger.warning("Socket 监控指标写入 InfluxDB 失败")

    #  响应解析

    def _parse_response(self, response: bytes) -> list:
        """
        根据 socket_response_format 解析响应内容
        返回数据行列表, 每行将作为一条记录写入 PG
        """
        response_format = (self.req.socket_response_format or "json").lower()

        if response_format == "json":
            try:
                text = response.decode("utf-8")
                data = json.loads(text)
                if isinstance(data, list):
                    return data
                return [data]
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.warning(f"响应不是合法 JSON: {e}, 降级为文本存储")
                return [{"raw_text": response.decode("utf-8", errors="replace")}]

        elif response_format == "text":
            text = response.decode("utf-8", errors="replace")
            return [{"raw_text": text}]

        elif response_format == "hex":
            return [{"raw_hex": response.hex()}]

        else:
            return [{"raw_hex": response.hex()}]

    #  PG 写入

    def _sanitize_for_json(self, obj) -> dict:
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"raw": str(obj)}

    def _generate_row_id(self, row_dict: dict) -> str:
        return hashlib.md5(json.dumps(row_dict, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def _prepare_target_table(self, table_name: str) -> Table:
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("raw_doc", JSON, nullable=False),
            Column("collected_at", String(64), nullable=True),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"PG 目标表 [{table_name}] 已就绪")
        return table

    def _ingest_to_pg(self, rows: list) -> int:
        if not rows:
            return 0

        target_table_name = self.req.target_table or "socket_data"
        target_table = self._prepare_target_table(target_table_name)
        collected_at = datetime.now(timezone.utc).isoformat()
        total_inserted = 0

        with self.target_engine.begin() as conn:
            for i in range(0, len(rows), self.batch_size):
                self._check_task_status()
                batch = [
                    {
                        "id": self._generate_row_id(row),
                        "raw_doc": self._sanitize_for_json(row),
                        "collected_at": collected_at
                    }
                    for row in rows[i: i + self.batch_size]
                ]
                stmt = pg_insert(target_table).values(batch).on_conflict_do_nothing(index_elements=["id"])
                conn.execute(stmt)
                total_inserted += len(batch)

        logger.info(f"Socket 数据写入 PG 完成, 共 {total_inserted} 条 -> [{target_table_name}]")
        return total_inserted

    def main(self) -> dict:
        if not self.req.host or not self.req.port:
            raise ValueError("Socket 采集必须指定 host 和 port")

        task_id = str(self.req.task_id)
        extract_mode = getattr(self.req, "socket_extract_mode", "both") or "both"
        start_time = time.time()

        protocol = (self.req.socket_protocol or "tcp").upper()
        logger.info(f"启动 Socket 采集: {protocol}://{self.req.host}:{self.req.port}")

        try:
            self._check_task_status()

            # 1. 发送指令并接收响应
            response, elapsed_ms, is_success, error_msg = self._request()
            response_size = len(response)

            # 2. 监控指标 -> InfluxDB
            if extract_mode in ("monitor", "both"):
                self._write_monitor_to_influx(task_id, elapsed_ms, is_success, response_size, error_msg)

            # 3. 请求失败
            if not is_success:
                return {
                    "status": "failed",
                    "tables_synced": 0,
                    "total_records": 0,
                    "new_watermark": None,
                    "table_details": [],
                    "monitor": {
                        "is_success": False,
                        "response_time_ms": elapsed_ms,
                        "error": error_msg
                    }
                }

            # 4. 解析响应 -> PG
            parsed_rows = 0
            if extract_mode in ("data", "both"):
                self._check_task_status()
                rows = self._parse_response(response)
                parsed_rows = self._ingest_to_pg(rows)

            elapsed = round(time.time() - start_time, 2)

            return {
                "status": "success",
                "tables_synced": 1 if parsed_rows > 0 else 0,
                "total_records": parsed_rows,
                "new_watermark": None,
                "table_details": [{
                    "name": f"{protocol.lower()}://{self.req.host}:{self.req.port}",
                    "target_name": self.req.target_table or "socket_data",
                    "records": parsed_rows,
                    "cost_seconds": elapsed,
                    "high_watermark": None
                }],
                "monitor": {
                    "is_success": True,
                    "response_time_ms": elapsed_ms,
                    "response_size": response_size
                }
            }

        except (TaskPausedException, TaskCancelledException):
            raise
        except Exception as e:
            logger.error(f"Socket 采集异常: {e}")
            raise
