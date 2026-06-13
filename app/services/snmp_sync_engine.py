# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/snmp_sync_engine.py
# @Created: 2026/6/13 9:45
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: SNMP 采集: 性能指标入InfluxDB, 设备表格信息入PG

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Table, Column, String, MetaData, JSON
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.task_control import get_task_status, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException


class SnmpSyncEngine:
    """
    SNMP 采集
      - metric 模式: GET 指定 OID(标量值) -> InfluxDB
      - info   模式: WALK 多个表格列 OID, 按索引聚合成行 -> PG(JSON)
      - both   模式: 两者都做
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = getattr(settings, "BATCH_SIZE", 1000)

    #  状态探测

    def _check_task_status(self):
        status = get_task_status(str(self.req.task_id))
        if status == TASK_PAUSED:
            raise TaskPausedException("SNMP 采集任务已暂停")
        if status == TASK_CANCELLED:
            raise TaskCancelledException("SNMP 采集任务已取消")

    #  认证构建

    def _build_auth(self):
        """
        根据 snmp_version 构建 pysnmp 的认证数据对象
        """
        from pysnmp.hlapi.v3arch.asyncio import (
            CommunityData, UsmUserData,
            usmHMACSHAAuthProtocol, usmHMACMD5AuthProtocol,
            usmAesCfb128Protocol, usmDESPrivProtocol,
            usmAesCfb128Protocol, usmDESPrivProtocol,
            usmNoAuthProtocol, usmNoPrivProtocol
        )
        version = (self.req.snmp_version or "v2c").lower()

        if version == "v1":
            return CommunityData(self.req.snmp_community or "public", mpModel=0)
        elif version == "v2c":
            return CommunityData(self.req.snmp_community or "public", mpModel=1)
        elif version == "v3":
            auth_proto = usmHMACSHAAuthProtocol if (self.req.snmp_auth_protocol or "SHA").upper() == "SHA" \
                else usmHMACMD5AuthProtocol
            priv_proto = usmAesCfb128Protocol if (self.req.snmp_priv_protocol or "AES").upper() == "AES" \
                else usmDESPrivProtocol

            if self.req.snmp_auth_key and self.req.snmp_priv_key:
                return UsmUserData(
                    self.req.snmp_user,
                    self.req.snmp_auth_key,
                    self.req.snmp_priv_key,
                    authProtocol=auth_proto,
                    privProtocol=priv_proto
                )
            elif self.req.snmp_auth_key:
                return UsmUserData(
                    self.req.snmp_user,
                    self.req.snmp_auth_key,
                    authProtocol=auth_proto,
                    privProtocol=usmNoPrivProtocol
                )
            else:
                return UsmUserData(
                    self.req.snmp_user,
                    authProtocol=usmNoAuthProtocol,
                    privProtocol=usmNoPrivProtocol
                )
        else:
            raise ValueError(f"不支持的 SNMP 版本: {version}")

    #  GET(标量指标)

    def _snmp_get(self, oid_map: dict) -> tuple:
        """
        对 oid_map 里的每个 OID 执行 GET(pysnmp 7.x 异步API)
        返回: (结果dict {字段名: 值}, 总耗时ms, 是否成功)
        """
        from pysnmp.hlapi.v3arch.asyncio import (
            SnmpEngine, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, get_cmd
        )
        import asyncio

        auth = self._build_auth()
        host, port = self.req.host, self.req.port or 161

        async def _get_one(oid: str):
            snmp_engine = SnmpEngine()
            transport = await UdpTransportTarget.create((host, port), timeout=5, retries=1)
            return await get_cmd(
                snmp_engine, auth, transport, ContextData(),
                ObjectType(ObjectIdentity(oid))
            )

        result = {}
        start = time.time()
        is_success = True

        for field_name, oid in oid_map.items():
            self._check_task_status()

            error_indication, error_status, error_index, var_binds = asyncio.run(_get_one(oid))

            if error_indication or error_status:
                logger.warning(f"SNMP GET 失败 [{field_name}={oid}]: {error_indication or error_status}")
                result[field_name] = None
                is_success = False
                continue

            for name, val in var_binds:
                try:
                    result[field_name] = float(val)
                except (ValueError, TypeError):
                    result[field_name] = str(val)

        elapsed_ms = round((time.time() - start) * 1000, 2)
        return result, elapsed_ms, is_success

    #  WALK(表格信息)

    def _snmp_walk(self, base_oid: str) -> dict:
        """
        对单个基础 OID 执行 WALK（pysnmp 7.x: next_cmd 是单步协程，
        需要手动循环 GETNEXT，直到 OID 超出子树范围)
        返回 {索引后缀: 值}
        """
        from pysnmp.hlapi.v3arch.asyncio import (
            SnmpEngine, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, next_cmd
        )
        import asyncio

        auth = self._build_auth()
        host, port = self.req.host, self.req.port or 161

        async def _walk():
            snmp_engine = SnmpEngine()
            transport = await UdpTransportTarget.create((host, port), timeout=5, retries=1)

            collected = []
            current_oid = ObjectIdentity(base_oid)
            max_iterations = 1000  # 防止子树异常导致死循环

            for _ in range(max_iterations):
                error_indication, error_status, error_index, var_binds = await next_cmd(
                    snmp_engine, auth, transport, ContextData(),
                    ObjectType(current_oid)
                )

                if error_indication:
                    logger.warning(f"SNMP WALK 异常 [{base_oid}]: {error_indication}")
                    break
                if error_status:
                    logger.warning(f"SNMP WALK 错误 [{base_oid}]: {error_status}")
                    break
                if not var_binds:
                    break

                oid, val = var_binds[0]
                oid_str = str(oid)

                # GETNEXT 走出了目标子树范围，walk 结束
                if not oid_str.startswith(base_oid):
                    break

                collected.append((oid_str, val))
                current_oid = ObjectIdentity(oid)  # 下一轮从这个 OID 继续 GETNEXT

            return collected

        raw_results = asyncio.run(_walk())

        result = {}
        for oid_str, val in raw_results:
            if oid_str.startswith(base_oid):
                index_suffix = oid_str[len(base_oid):].lstrip(".")
            else:
                index_suffix = oid_str
            try:
                result[index_suffix] = float(val)
            except (ValueError, TypeError):
                result[index_suffix] = str(val)

        return result

    #  InfluxDB 写入(性能指标)

    def _write_metrics_to_influx(self, task_id: str, metrics: dict, elapsed_ms: float, is_success: bool):
        task_id_safe = task_id.replace(" ", "_")
        host_safe = (self.req.host or "unknown").replace(" ", "_")

        # 数值型字段拼成 Line Protocol fields
        field_parts = []
        for k, v in metrics.items():
            if v is None:
                continue
            if isinstance(v, (int, float)):
                field_parts.append(f"{k}={v}")
            else:
                safe_v = str(v).replace('"', '\\"')
                field_parts.append(f'{k}="{safe_v}"')

        field_parts.append(f"response_time={elapsed_ms}")
        field_parts.append(f"is_success={1 if is_success else 0}i")

        if not field_parts:
            logger.warning("SNMP 指标为空, 跳过 InfluxDB 写入")
            return

        line = f"snmp_monitor,task_id={task_id_safe},host={host_safe} " + ",".join(field_parts)

        influx = get_influx_client()
        success = influx.write_line_protocol(line)
        if success:
            logger.info(f"SNMP 指标已写入 InfluxDB: {metrics}")
        else:
            logger.warning("SNMP 指标写入 InfluxDB 失败")

    #  PG 写入(表格信息)

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

    def _build_table_rows(self) -> list:
        """
        对 snmp_table_oids 里的每个基础 OID 做 WALK, 
        按索引后缀聚合成行：{字段名1: 值, 字段名2: 值, ..., '_index': 索引}
        """
        table_oids = self.req.snmp_table_oids or {}
        if not table_oids:
            return []

        # 每列单独 walk, 结果按索引聚合
        columns_data = {}  # {字段名: {索引: 值}}
        for field_name, base_oid in table_oids.items():
            self._check_task_status()
            columns_data[field_name] = self._snmp_walk(base_oid)
            logger.info(f"SNMP WALK [{field_name}={base_oid}] 完成, {len(columns_data[field_name])} 条")

        # 收集所有索引(取并集)
        all_indices = set()
        for col_dict in columns_data.values():
            all_indices.update(col_dict.keys())

        # 按索引组装行
        rows = []
        for index in sorted(all_indices):
            row = {"_index": index}
            for field_name, col_dict in columns_data.items():
                row[field_name] = col_dict.get(index)
            rows.append(row)

        return rows

    def _ingest_to_pg(self, rows: list) -> int:
        if not rows:
            return 0

        target_table_name = self.req.target_table or "snmp_info"
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

        logger.info(f"SNMP 表格数据写入 PG 完成, 共 {total_inserted} 条 -> [{target_table_name}]")
        return total_inserted

    def main(self) -> dict:
        if not self.req.host:
            raise ValueError("SNMP 采集必须指定 host")

        task_id = str(self.req.task_id)
        extract_mode = self.req.snmp_extract_mode or "both"
        start_time = time.time()

        logger.info(f"启动 SNMP 采集: {self.req.host}:{self.req.port or 161}, 模式: {extract_mode}")

        try:
            self._check_task_status()

            # metric 模式：GET 标量指标 -> InfluxDB
            metric_count = 0
            if extract_mode in ("metric", "both") and self.req.snmp_metric_oids:
                metrics, elapsed_ms, is_success = self._snmp_get(self.req.snmp_metric_oids)
                self._write_metrics_to_influx(task_id, metrics, elapsed_ms, is_success)
                metric_count = len([v for v in metrics.values() if v is not None])

            # info 模式：WALK 表格 -> PG
            parsed_rows = 0
            if extract_mode in ("info", "both") and self.req.snmp_table_oids:
                self._check_task_status()
                rows = self._build_table_rows()
                logger.info(f"SNMP 表格采集完成, {len(rows)} 行")
                parsed_rows = self._ingest_to_pg(rows)

            elapsed = round(time.time() - start_time, 2)

            return {
                "status": "success",
                "tables_synced": 1 if parsed_rows > 0 else 0,
                "total_records": parsed_rows,
                "new_watermark": None,
                "table_details": [{
                    "name": f"snmp://{self.req.host}",
                    "target_name": self.req.target_table or "snmp_info",
                    "records": parsed_rows,
                    "cost_seconds": elapsed,
                    "high_watermark": None
                }],
                "monitor": {
                    "metric_count": metric_count
                }
            }

        except (TaskPausedException, TaskCancelledException):
            raise
        except Exception as e:
            logger.error(f"SNMP 采集异常: {e}")
            raise
