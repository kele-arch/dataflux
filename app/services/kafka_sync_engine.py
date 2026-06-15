# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/kafka_sync_engine.py
# @Created: 2026/6/13 11:47
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Kafka 流式采集服务: 常驻Consumer, offset由Kafka自身持久化

import hashlib
import json
import time
from datetime import datetime, timezone

from sqlalchemy import Table, Column, String, MetaData, JSON
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import logger
from app.core.config import settings
from app.core.influx_client import get_influx_client
from app.db.session import collected_engine as global_target_engine
from app.schemas.tsync import DBSyncReq


class KafkaSyncEngine:
    """
    Kafka 流式采集
      - 常驻 Consumer, 攒批写入 PG
      - offset 由 Kafka Consumer Group 自身管理(写入成功后手动 commit)
      - 消费速率/Lag 写入 InfluxDB
      - 支持外部信号停止 (asyncio.Event)
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = req.kafka_batch_size or 500
        self.batch_timeout_ms = req.kafka_batch_timeout_ms or 5000
        self._stop_event = None  # 由 Manager 注入, 用于停止

    #  序列化 / 幂等ID

    def _sanitize_for_json(self, obj) -> dict:
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"raw": str(obj)}

    def _generate_row_id(self, topic: str, partition: int, offset: int) -> str:
        """ 用 topic+partition+offset 生成确定性ID, 天然幂等去重 """
        return hashlib.md5(f"{topic}-{partition}-{offset}".encode("utf-8")).hexdigest()

    #  PG 写入

    def _prepare_target_table(self, table_name: str) -> Table:
        """
        确保目标表存在, 不存在则创建
         - id: 基于 topic+partition+offset 生成的唯一ID, 用于幂等去重
         - raw_doc: 原始消息内容的 JSON 序列化结果
         - collected_at: 消息被写入的时间戳 (ISO 格式字符串)
         - 其他字段可以根据需要扩展
         - 表名由 req.target_table 指定, 由 Manager 统一命名规范 (如 kafka_{task_id})
         - 使用 PostgreSQL 的 JSON 数据类型存储原始消息内容, 方便后续查询和处理
         - 创建表时使用 checkfirst=True 确保幂等执行
         - 返回 SQLAlchemy Table 对象供后续插入使用
        """
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("raw_doc", JSON, nullable=False),
            Column("collected_at", String(64), nullable=True),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        return table

    def _ingest_batch(self, target_table: Table, batch: list) -> int:
        """
        将一批消息写入目标表, 使用 PostgreSQL 的批量插入和 ON CONFLICT DO NOTHING 实现幂等去重
        """
        if not batch:
            return 0
        collected_at = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "id": self._generate_row_id(item["topic"], item["partition"], item["offset"]),
                "raw_doc": self._sanitize_for_json(item["value"]),
                "collected_at": collected_at
            }
            for item in batch
        ]
        with self.target_engine.begin() as conn:
            stmt = pg_insert(target_table).values(rows).on_conflict_do_nothing(index_elements=["id"])
            conn.execute(stmt)
        return len(rows)

    #  InfluxDB 监控

    def _write_monitor(self, task_id: str, consumed: int, elapsed_ms: float, lag: int = -1):
        """
        将消费速率和Lag写入 InfluxDB 监控
        """
        task_id_safe = task_id.replace(" ", "_")
        topic_safe = (self.req.kafka_topic or "unknown").replace(" ", "_")

        fields = f"consumed={consumed}i,elapsed_ms={elapsed_ms}"
        if lag >= 0:
            fields += f",lag={lag}i"

        line = f"kafka_monitor,task_id={task_id_safe},topic={topic_safe} {fields}"
        influx = get_influx_client()
        if not influx.write_line_protocol(line):
            logger.warning("Kafka 监控指标写入 InfluxDB 失败")

    #  消息解析

    def _decode_value(self, raw_value: bytes):
        """

        """
        value_format = self.req.kafka_value_format or "json"
        if value_format == "json":
            try:
                return json.loads(raw_value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {"raw_text": raw_value.decode("utf-8", errors="replace")}
        else:
            return {"raw_text": raw_value.decode("utf-8", errors="replace")}

    #  主消费循环(常驻, 由 Manager 以 asyncio.Task 方式启动)

    async def run(self, stop_event):
        """
        常驻消费循环
        stop_event: asyncio.Event, 外部调用 stop_event.set() 即可停止
        """
        from aiokafka import AIOKafkaConsumer

        self._stop_event = stop_event
        task_id = str(self.req.task_id)

        if not self.req.kafka_bootstrap_servers or not self.req.kafka_topic:
            raise ValueError("Kafka 采集必须指定 kafka_bootstrap_servers 和 kafka_topic")

        target_table_name = self.req.target_table or f"kafka_{self.req.kafka_topic}"
        target_table = self._prepare_target_table(target_table_name)
        group_id = self.req.kafka_group_id or f"dataflux_{task_id}"

        consumer = AIOKafkaConsumer(
            self.req.kafka_topic,
            bootstrap_servers=self.req.kafka_bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=self.req.kafka_auto_offset_reset or "latest",
            enable_auto_commit=False,  # 手动commit, 确保写库成功后才提交offset
            value_deserializer=lambda v: v,  # 先拿原始bytes, 自行解析
        )

        await consumer.start()
        logger.info(
            f"Kafka Consumer 已启动: topic={self.req.kafka_topic}, "
            f"group={group_id}, target_table={target_table_name}"
        )

        try:
            while not stop_event.is_set():
                start = time.time()

                # 满 batch_size 或超时 batch_timeout_ms 即返回
                msg_pack = await consumer.getmany(
                    timeout_ms=self.batch_timeout_ms,
                    max_records=self.batch_size
                )

                if not msg_pack:
                    continue  # 这一轮没有消息, 继续下一轮(同时会再检查stop_event)

                batch = []
                for tp, messages in msg_pack.items():
                    for msg in messages:
                        batch.append({
                            "topic": msg.topic,
                            "partition": msg.partition,
                            "offset": msg.offset,
                            "value": self._decode_value(msg.value)
                        })

                # 写入 PG
                inserted = self._ingest_batch(target_table, batch)

                # 写库成功后才 commit offset
                await consumer.commit()

                elapsed_ms = round((time.time() - start) * 1000, 2)
                logger.info(
                    f"[{task_id}] Kafka 消费批次完成: {len(batch)} 条消息, "
                    f"写入 {inserted} 条, 耗时 {elapsed_ms}ms"
                )

                self._write_monitor(task_id, len(batch), elapsed_ms)

        except Exception as e:
            logger.error(f"[{task_id}] Kafka 消费异常: {e}")
            raise

        finally:
            await consumer.stop()
            logger.info(f"[{task_id}] Kafka Consumer 已停止")
