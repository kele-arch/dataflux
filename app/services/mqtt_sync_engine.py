# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/mqtt_sync_engine.py
# @Created: 2026/6/16 9:57
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: MQTT 流式采集: 常驻订阅, 攒批写入PG, 监控指标入InfluxDB

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from sqlalchemy import Table, Column, String, MetaData, JSON, Integer
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq


class MqttSyncEngine:
    """
    MQTT 流式采集
      - 常驻订阅指定 Topic(支持通配符 + 和 #)
      - 攒批写入 PG(JSON 列存储)
      - 消息速率/QoS 统计写入 InfluxDB
      - 支持 QoS 0/1/2 和 TLS 加密连接
      - Clean Session=False 保证断线重连不丢消息

    设计要点(避免阻塞事件循环导致 MQTT 心跳超时/假性断连): 
      - PG 批量写入 (_ingest_batch) 是同步阻塞调用 -> 通过 asyncio.to_thread 丢进线程池
      - InfluxDB 监控写入 (_write_monitor) 同样是同步阻塞调用 -> 同样丢进线程池
      - 任何同步 I/O 都不应直接 await 在主消费协程里, 否则会卡住底层
        paho-mqtt 的 keepalive PINGREQ/PINGRESP 收发节奏, 造成 Operation timed out
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = req.mqtt_batch_size or 100
        self.batch_timeout_ms = req.mqtt_batch_timeout_ms or 3000

    #  序列化 / 幂等 ID

    def _sanitize_for_json(self, obj) -> dict:
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"raw": str(obj)}

    def _generate_row_id(self, topic: str, payload_bytes: bytes) -> str:
        """仅通过 topic 和 payload 内容生成强哈希, 确保 QoS 1/2 重传时主键一致"""
        content = f"{topic}:{payload_bytes.hex()}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    #  消息解析

    def _decode_payload(self, payload: bytes):
        """
        根据 mqtt_value_format 解析消息体
        """
        value_format = (self.req.mqtt_value_format or "json").lower()

        if value_format == "json":
            try:
                return json.loads(payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {"raw_text": payload.decode("utf-8", errors="replace")}

        elif value_format == "text":
            return {"raw_text": payload.decode("utf-8", errors="replace")}

        elif value_format == "hex":
            return {"raw_hex": payload.hex()}

        return {"raw_text": payload.decode("utf-8", errors="replace")}

    #  PG 写入(同步, 调用方需用 asyncio.to_thread 包裹)

    def _prepare_target_table(self, table_name: str) -> Table:
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("topic", String(255), nullable=True),  # 记录来源 Topic
            Column("raw_doc", JSON, nullable=False),
            Column("collected_at", String(64), nullable=True),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"PG 目标表 [{table_name}] 已就绪")
        return table

    def _ingest_batch(self, target_table: Table, batch: list) -> int:
        """
        批量写入, on_conflict_do_nothing 实现幂等
        注意: 这是同步阻塞方法, 必须通过 asyncio.to_thread 调用, 禁止直接 await
        """
        if not batch:
            return 0

        rows = [
            {
                "id": item["id"],
                "topic": item["topic"],
                "raw_doc": self._sanitize_for_json(item["value"]),
                "collected_at": item["received_at"]
            }
            for item in batch
        ]

        with self.target_engine.begin() as conn:
            stmt = pg_insert(target_table).values(rows).on_conflict_do_nothing(index_elements=["id"])
            conn.execute(stmt)

        return len(rows)

    #  InfluxDB 监控(同步, 调用方需用 asyncio.to_thread 包裹)

    def _write_monitor(self, task_id: str, consumed: int, elapsed_ms: float):
        """
        注意: 底层 get_influx_client().write_line_protocol() 大概率是同步 HTTP 请求, 
        这是同步阻塞方法, 必须通过 asyncio.to_thread 调用, 禁止直接 await
        """
        task_id_safe = task_id.replace(" ", "_")
        topic_safe = (self.req.mqtt_topic or "unknown").replace(
            " ", "_").replace("+", "plus").replace("#", "hash")

        line = (
            f"mqtt_monitor,task_id={task_id_safe},topic={topic_safe} "
            f"consumed={consumed}i,elapsed_ms={elapsed_ms}"
        )
        try:
            influx = get_influx_client()
            if not influx.write_line_protocol(line):
                logger.warning("MQTT 监控指标写入 InfluxDB 失败")
        except Exception as e:
            # 监控写入失败不应该影响主消费流程, 吞掉异常仅记录日志
            logger.warning(f"MQTT 监控指标写入 InfluxDB 异常(已忽略): {e}")

    #  主消费循环(常驻, 由 MqttManager 以 asyncio.Task 方式启动)

    async def run(self, stop_event: asyncio.Event):
        """
        常驻订阅循环
        stop_event: asyncio.Event, 外部调用 stop_event.set() 停止
        """
        import aiomqtt

        # ---- 消音 aiomqtt __aexit__ 清理阶段的已知噪音 ----
        # Windows + Python 3.13 下 aiomqtt 清理 socket 时会触发
        # add_reader/add_writer NotImplementedError, 不影响功能
        loop = asyncio.get_event_loop()

        def _mqtt_exc_handler(loop, context):
            exc = context.get("exception")
            msg = context.get("message", "")
            if isinstance(exc, NotImplementedError) and (
                    "add_reader" in str(msg) or "add_writer" in str(msg)
            ):
                return
            loop.default_exception_handler(context)

        loop.set_exception_handler(_mqtt_exc_handler)
        # ----------------------------------------------------------

        task_id = str(self.req.task_id)

        if not self.req.mqtt_broker or not self.req.mqtt_topic:
            raise ValueError("MQTT 采集必须指定 mqtt_broker 和 mqtt_topic")

        target_table_name = self.req.target_table or \
                            f"mqtt_{self.req.mqtt_topic.replace('/', '_').replace('+', 'any').replace('#', 'all')}"
        # 建表是启动前一次性同步操作, 不在消费循环内, 不会影响心跳, 无需 to_thread
        target_table = self._prepare_target_table(target_table_name)

        # 客户端 ID: 固定 ID 配合 clean_session=False 才能保证离线消息补发
        client_id = self.req.mqtt_client_id or f"dataflux_{task_id}"
        clean_session = bool(self.req.mqtt_clean_session) if self.req.mqtt_clean_session is not None else False
        qos = self.req.mqtt_qos if self.req.mqtt_qos is not None else 1

        # TLS 配置
        tls_params = None
        if self.req.mqtt_use_tls:
            import ssl
            tls_params = aiomqtt.TLSParameters(
                ca_certs=None,
                certfile=None,
                keyfile=None,
                tls_version=ssl.PROTOCOL_TLS,
            )

        logger.info(
            f"MQTT Consumer 启动: broker={self.req.mqtt_broker}:{self.req.mqtt_port or 1883}, "
            f"topic={self.req.mqtt_topic}, qos={qos}, "
            f"client_id={client_id}, clean_session={clean_session}"
        )

        # 攒批缓冲区和计时器
        batch = []
        last_flush_time = time.time()

        # 外层重连循环: 网络断开或 Broker 重启时自动重连
        retry_delay = 5  # 初始重连延迟(秒)
        max_retry_delay = 60  # 最大重连延迟(秒)

        while not stop_event.is_set():
            try:
                async with aiomqtt.Client(
                        hostname=self.req.mqtt_broker,
                        port=self.req.mqtt_port or 1883,
                        username=self.req.username or None,
                        password=self.req.password or None,
                        identifier=client_id,
                        clean_session=clean_session,
                        keepalive=self.req.mqtt_keepalive or 60,
                        tls_params=tls_params,
                ) as client:

                    await client.subscribe(self.req.mqtt_topic, qos=qos)
                    logger.info(f"[{task_id}] 已订阅 Topic: {self.req.mqtt_topic}")
                    retry_delay = 5  # 连接成功后重置重连延迟

                    async for message in client.messages:
                        if stop_event.is_set():
                            # 显式断开避免 Windows 下 __aexit__ 清理 socket 卡死
                            try:
                                await asyncio.wait_for(
                                    client.disconnect(), timeout=3
                                )
                            except Exception:
                                pass
                            break

                        received_at = datetime.now(timezone.utc).isoformat()
                        payload_bytes = bytes(message.payload)

                        batch.append({
                            "id": self._generate_row_id(str(message.topic), payload_bytes),
                            "topic": str(message.topic),
                            "value": self._decode_payload(payload_bytes),
                            "received_at": received_at
                        })

                        now = time.time()
                        batch_timeout_reached = (
                                (now - last_flush_time) * 1000 >= self.batch_timeout_ms
                        )

                        # 满批次 或 超时 ->  写库 (线程池执行, 不阻塞 event loop)
                        if len(batch) >= self.batch_size or batch_timeout_reached:
                            start = time.time()
                            inserted = await asyncio.to_thread(
                                self._ingest_batch, target_table, batch
                            )
                            elapsed_ms = round((time.time() - start) * 1000, 2)

                            logger.info(
                                f"[{task_id}] MQTT 批次写入: {len(batch)} 条消息, "
                                f"写入 {inserted} 条, 耗时 {elapsed_ms}ms"
                            )

                            await asyncio.to_thread(
                                self._write_monitor, task_id, len(batch), elapsed_ms
                            )

                            batch.clear()
                            last_flush_time = time.time()

                    # 停止信号收到后, 写入剩余消息
                    if batch:
                        await asyncio.to_thread(self._ingest_batch, target_table, batch)
                        logger.info(f"[{task_id}] 停止前写入剩余 {len(batch)} 条消息")

                    # 正常退出(stop_event 触发)
                    if stop_event.is_set():
                        break

            except Exception as e:
                if stop_event.is_set():
                    # 停止信号触发期间的异常是预期行为, 静默退出
                    logger.info(f"[{task_id}] MQTT Consumer 在停止过程中断开连接")
                    break

                # 异常断连前先把攒批中的消息安全落库, 避免数据丢失
                if batch:
                    try:
                        await asyncio.to_thread(
                            self._ingest_batch, target_table, batch
                        )
                        logger.info(
                            f"[{task_id}] 断连前抢救写入剩余 {len(batch)} 条消息"
                        )
                    except Exception as flush_err:
                        logger.error(
                            f"[{task_id}] 抢救写入失败, 丢失 {len(batch)} 条: {flush_err}"
                        )
                    batch.clear()

                logger.exception(
                    f"[{task_id}] MQTT 连接断开 [{type(e).__name__}]: {e}, "
                    f"{retry_delay}s 后自动重连..."
                )
                # 指数退避等待后重连
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

        logger.info(f"[{task_id}] MQTT Consumer 已停止")
