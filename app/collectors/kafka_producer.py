# -- coding: utf-8 --
# @Author: 胡H
# @File: kafka_producer.py
# @Created: 2026/6/5 9:56
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
import json
from confluent_kafka import Producer
from app.core import logger
from app.schemas.collectors import CollectDataEvent


class KafkaSender:
    def __init__(self, brokers: str = "127.0.0.1:9092"):
        self.producer = Producer({
            'bootstrap.servers': brokers,
            'linger.ms': 50,  # 延迟50ms凑批发送，提升吞吐
            'compression.type': 'lz4'  # 开启压缩，节省网络带宽
        })

    def delivery_report(self, err, msg):
        """ 投递结果回调 """
        if err is not None:
            logger.error(f"Kafka 消息投递失败: {err}")
        # 成功就不打印了，避免日志爆炸

    def send_event(self, kafka_topic: str, event: CollectDataEvent):
        """ 发送标准事件到 Kafka """
        try:
            # Pydantic 模型转 JSON 字符串 (支持 datetime 自动格式化)
            json_data = event.model_dump_json().encode('utf-8')

            self.producer.produce(
                topic=kafka_topic,
                value=json_data,
                callback=self.delivery_report
            )
            # 触发异步发送机制
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Kafka 发送异常: {str(e)}")

    def flush(self):
        """ 关闭前调用，确保缓冲区数据发完 """
        self.producer.flush()


# 单例模式，全局复用这一个生产者实例
kafka_client = KafkaSender()