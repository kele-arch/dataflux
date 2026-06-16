# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/rabbitmq_sync_engine.py
# @Created: 2026/6/16 21:48
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: RabbitMQ 流式采集-- 常驻消费, 写库成功后才ACK, 确保零丢失

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
import urllib.parse

import aio_pika
from sqlalchemy import Table, Column, String, MetaData, JSON
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq


class RabbitMQSyncEngine:
    """
    RabbitMQ 流式采集引擎
      - 常驻消费指定队列(支持交换机绑定)
      - 攒批写入 PG, 写库成功后批量 ACK, 确保零丢失
      - 单条消息处理失败时 NACK 重新入队, 避免数据丢失
      - 消费速率/队列深度写入 InfluxDB
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = req.mq_batch_size or 100
        self.batch_timeout_ms = req.mq_batch_timeout_ms or 3000

    #  序列化 / 幂等 ID

    def _sanitize_for_json(self, obj) -> dict:
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"raw": str(obj)}

    def _generate_row_id(self, routing_key: str, body: bytes) -> str:
        """
        仅用 routing_key + body 内容生成幂等ID
        不依赖系统时间, 重新投递的消息ID保持一致
        """
        content = f"{routing_key}:{body.hex()}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    #  消息解析

    def _decode_body(self, body: bytes):
        value_format = (self.req.mq_value_format or "json").lower()

        if value_format == "json":
            try:
                return json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {"raw_text": body.decode("utf-8", errors="replace")}
        elif value_format == "text":
            return {"raw_text": body.decode("utf-8", errors="replace")}
        elif value_format == "hex":
            return {"raw_hex": body.hex()}
        return {"raw_text": body.decode("utf-8", errors="replace")}

    #  PG 写入

    def _prepare_target_table(self, table_name: str) -> Table:
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("routing_key", String(255), nullable=True),
            Column("raw_doc", JSON, nullable=False),
            Column("collected_at", String(64), nullable=True),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"PG 目标表 [{table_name}] 已就绪")
        return table

    def _ingest_batch(self, target_table: Table, batch: list) -> int:
        if not batch:
            return 0

        rows = [
            {
                "id": item["id"],
                "routing_key": item["routing_key"],
                "raw_doc": self._sanitize_for_json(item["value"]),
                "collected_at": item["received_at"]
            }
            for item in batch
        ]

        with self.target_engine.begin() as conn:
            stmt = pg_insert(target_table).values(rows).on_conflict_do_nothing(index_elements=["id"])
            conn.execute(stmt)

        return len(rows)

    #  死信队列 (PG 落库，隔离毒药消息，阻断 NACK 死循环)

    def _prepare_dlq_table(self) -> Table:
        """准备 PostgreSQL 死信记录表"""
        metadata = MetaData()
        table = Table(
            "mq_dead_letter",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("task_id", String(64)),
            Column("queue_name", String(255)),
            Column("routing_key", String(255)),
            Column("raw_payload", String, nullable=False),
            Column("error_reason", String),
            Column("created_at", String(64)),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info("PG 死信表 [mq_dead_letter] 已就绪")
        return table

    def _ingest_dlq(self, dlq_table: Table, row: dict):
        """将毒药消息写入 PG 死信表"""
        with self.target_engine.begin() as conn:
            stmt = pg_insert(dlq_table).values(row).on_conflict_do_nothing(index_elements=["id"])
            conn.execute(stmt)

    #  InfluxDB 监控

    def _write_monitor(self, task_id: str, consumed: int, elapsed_ms: float):
        task_id_safe = task_id.replace(" ", "_")
        queue_safe = (self.req.mq_queue or "unknown").replace(" ", "_")

        line = (
            f"rabbitmq_monitor,task_id={task_id_safe},queue={queue_safe} "
            f"consumed={consumed}i,elapsed_ms={elapsed_ms}"
        )
        influx = get_influx_client()
        if not influx.write_line_protocol(line):
            logger.warning("RabbitMQ 监控指标写入 InfluxDB 失败")

    #  主消费循环

    async def run(self, stop_event: asyncio.Event):
        """
        常驻消费循环
        消息先进内存批次, 攒批写库成功后才批量ACK
                 写库失败则整批NACK重新入队(requeue=True), 不丢数据
        """
        task_id = str(self.req.task_id)

        if not self.req.mq_host or not self.req.mq_queue:
            raise ValueError("RabbitMQ 采集必须指定 mq_host 和 mq_queue")

        target_table_name = self.req.target_table or f"mq_{self.req.mq_queue}"
        target_table = self._prepare_target_table(target_table_name)
        dlq_table = self._prepare_dlq_table()

        # 构建连接 URL
        # safe_password = self.req.password or "guest"
        # connection_url = (
        #     f"amqp://{self.req.username or 'guest'}:{safe_password}"
        #     f"@{self.req.mq_host}:{self.req.mq_port or 5672}{self.req.mq_vhost or '/'}"
        # )
        safe_user = urllib.parse.quote(self.req.username or "guest")
        safe_password = urllib.parse.quote(self.req.password or "guest")
        safe_vhost = urllib.parse.quote(self.req.mq_vhost or "/", safe="")  # vhost的 / 也需要正确编码

        connection_url = (
            f"amqp://{safe_user}:{safe_password}"
            f"@{self.req.mq_host}:{self.req.mq_port or 5672}/{safe_vhost}"
        )

        logger.info(
            f"RabbitMQ Consumer 启动: {self.req.mq_host}:{self.req.mq_port or 5672}, "
            f"queue={self.req.mq_queue}"
        )

        connection = await aio_pika.connect_robust(connection_url)

        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=self.req.mq_prefetch_count or 50)

            # 声明队列(durable 保证 Broker 重启不丢队列定义)
            queue = await channel.declare_queue(
                self.req.mq_queue,
                durable=bool(self.req.mq_durable) if self.req.mq_durable is not None else True
            )

            # 如果配置了交换机, 声明并绑定
            if self.req.mq_exchange:
                exchange = await channel.declare_exchange(
                    self.req.mq_exchange,
                    type=self.req.mq_exchange_type or "direct",
                    durable=True
                )
                await queue.bind(exchange, routing_key=self.req.mq_routing_key or "")
                logger.info(
                    f"队列 [{self.req.mq_queue}] 已绑定交换机 [{self.req.mq_exchange}] "
                    f"routing_key=[{self.req.mq_routing_key}]"
                )

            batch = []  # 攒批缓冲：写入数据
            pending_messages = []  # 攒批缓冲：对应的原始 aio_pika Message 对象(用于ACK)
            last_flush_time = time.time()

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:

                    if stop_event.is_set():
                        break

                    received_at = datetime.now(timezone.utc).isoformat()
                    body = message.body
                    routing_key = message.routing_key or ""

                    batch.append({
                        "id": self._generate_row_id(routing_key, body),
                        "routing_key": routing_key,
                        "value": self._decode_body(body),
                        "received_at": received_at
                    })
                    pending_messages.append(message)

                    now = time.time()
                    batch_timeout_reached = (now - last_flush_time) * 1000 >= self.batch_timeout_ms

                    if len(batch) >= self.batch_size or batch_timeout_reached:
                        start = time.time()
                        try:
                            # 切入线程池防阻塞
                            inserted = await asyncio.to_thread(self._ingest_batch, target_table, batch)

                            # 批量 ACK
                            for msg in pending_messages:
                                await msg.ack()

                            elapsed_ms = round((time.time() - start) * 1000, 2)
                            logger.info(
                                f"[{task_id}] RabbitMQ 批次写入: {len(batch)} 条, 写入 {inserted} 条, 耗时 {elapsed_ms}ms")

                            # 监控写入切入线程池
                            await asyncio.to_thread(self._write_monitor, task_id, len(batch), elapsed_ms)

                        except OperationalError as e:
                            # 数据库宕机/连接断开，非数据本身的锅，整批 NACK 延时重试
                            logger.error(f"[{task_id}] 数据库连接异常，等待恢复: {e}")
                            for msg in pending_messages:
                                await msg.nack(requeue=True)
                            await asyncio.sleep(5)

                        except Exception as e:
                            # 批次写库失败 → 降级单条排雷，精确定位毒药消息
                            logger.warning(f"[{task_id}] 批次写库失败，触发降级单条排雷: {e}")

                            for idx, item in enumerate(batch):
                                msg = pending_messages[idx]
                                try:
                                    # 单条尝试写入正常表
                                    await asyncio.to_thread(
                                        self._ingest_batch, target_table, [item]
                                    )
                                    await msg.ack()  # 正常放行
                                except Exception as inner_e:
                                    # 毒药消息：写入 PG 死信表，隔离后 ACK 移出队列
                                    dlq_row = {
                                        "id": uuid.uuid4().hex,
                                        "task_id": task_id,
                                        "queue_name": self.req.mq_queue,
                                        "routing_key": item["routing_key"],
                                        "raw_payload": msg.body.decode("utf-8", errors="replace"),
                                        "error_reason": str(inner_e)[:1000],
                                        "created_at": datetime.now(timezone.utc).isoformat(),
                                    }
                                    try:
                                        await asyncio.to_thread(
                                            self._ingest_dlq, dlq_table, dlq_row
                                        )
                                        await msg.ack()
                                        logger.error(
                                            f"[{task_id}] 毒药消息已隔离至 PG mq_dead_letter, "
                                            f"routing_key={item['routing_key']}"
                                        )
                                    except Exception as dlq_e:
                                        # 极端情况：连死信表都写不进去(磁盘满等)
                                        logger.critical(
                                            f"[{task_id}] 死信表写入失败, 消息退回队列: {dlq_e}"
                                        )
                                        await msg.nack(requeue=True)

                        batch.clear()
                        pending_messages.clear()
                        last_flush_time = time.time()

                # 停止信号收到后, 处理剩余消息 (线程池执行)
                if batch:
                    try:
                        await asyncio.to_thread(self._ingest_batch, target_table, batch)
                        for msg in pending_messages:
                            await msg.ack()
                        logger.info(f"[{task_id}] 停止前写入剩余 {len(batch)} 条消息")
                    except Exception as e:
                        logger.error(f"[{task_id}] 停止前剩余消息写库失败, NACK重新入队: {e}")
                        for msg in pending_messages:
                            await msg.nack(requeue=True)

        except Exception as e:
            logger.error(f"[{task_id}] RabbitMQ Consumer 异常: {e}")
            raise

        finally:
            await connection.close()
            logger.info(f"[{task_id}] RabbitMQ Consumer 已停止")
