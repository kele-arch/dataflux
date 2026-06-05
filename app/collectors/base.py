# -- coding: utf-8 --
# @Author: 胡H
# @File: app/collectors/base.py
# @Created: 2026/6/5 9:56
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from abc import ABC, abstractmethod
from typing import Dict, Any
from app.collectors.kafka_producer import kafka_client
from app.schemas.collectors import CollectDataEvent


class BaseCollector(ABC):
    def __init__(self, task_id: str, source_type: str, config: Dict[str, Any]):
        """
        :param task_id: 采集任务ID
        :param source_type: 来源类型标识
        :param config: 该任务特有的配置字典 (如IP, 端口, 账号等)
        """
        self.task_id = task_id
        self.source_type = source_type
        self.config = config

    @abstractmethod
    def start(self):
        """ 启动采集任务 (可以是阻塞的 loop_forever，也可以是异步协程) """
        pass

    @abstractmethod
    def stop(self):
        """ 停止采集任务，释放连接 """
        pass

    def emit_to_kafka(self, topic: str, payload: Dict[str, Any]):
        """
        核心枢纽：子类采到数据后，只需调用 self.emit_to_kafka()
        """
        event = CollectDataEvent(
            task_id=self.task_id,
            source_type=self.source_type,
            topic=topic,
            payload=payload
        )

        # 默认将所有采集数据发往统一个汇总 Topic，比如叫 raw_collect_data
        # 消费者侧再根据 source_type 进行分发或统一落盘
        kafka_client.send_event(kafka_topic="raw_collect_data", event=event)