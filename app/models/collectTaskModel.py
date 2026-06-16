# -- coding: utf-8 --
# @Author: 胡H
# @File: collectTaskModel.py
# @Created: 2026/6/5 9:47
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:

from sqlalchemy import String, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.bashModel import BaseModelMixin
from app.core.config import settings


class CollectTask(Base, BaseModelMixin):
    __tablename__ = "sys_collect_task"
    __table_args__ = (
        {"schema": settings.DB_SCHEMA, "comment": "数据采集任务定义表"},
    )

    task_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="任务名称")

    # 完整的 SA2.0 逻辑关联
    source_id: Mapped[str] = mapped_column(String(32), comment="关联的数据源ID")

    topic_or_table: Mapped[str | None] = mapped_column(String(100), nullable=True,
                                                       comment="custom_sql模式下目标库写入表名")

    schedule_type: Mapped[str] = mapped_column(String(20), default="none",
                                               comment="调度类型: none, cron, interval_min, daily, weekly")
    schedule_value: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="调度值 (如 02:30)")

    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True,
                                                      comment="定时任务表达式，为空则表示常驻流式任务")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="任务状态：0停用, 1启用")

    sync_mode: Mapped[str] = mapped_column(String(20), default="overwrite", comment="冲突策略: insert, overwrite, skip")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="备注")

    sync_tables: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="指定同步表")
    table_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="表名映射: {'源表名':'目标表名'}")

    # 采集模式：full(全量), inc_id(自增列), inc_time(时间戳), custom_sql(自定义SQL)
    collect_mode: Mapped[str] = mapped_column(String(20), default="full")

    # 增量依赖的字段名 (如 "id" 或 "update_time")
    incremental_column: Mapped[str | None] = mapped_column(String(50))

    # 水位线记录 (上次采集的最大值)
    last_watermark: Mapped[str | None] = mapped_column(String(255))

    # 用户自定义的 SQL 语句
    custom_sql: Mapped[str | None] = mapped_column(Text)

    # 目标库配置 (MongoDB -> MongoDB 时需要)
    target_type: Mapped[str] = mapped_column(String(20), default="postgresql",
                                             comment="目标库类型: postgresql 或 mongodb")
    target_host: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="目标库主机")
    target_port: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="目标库端口")
    target_username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标库账号")
    target_password: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="目标库密码")
    target_db_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标库名")

    # FTP 采集配置
    ftp_url: Mapped[str | None] = mapped_column(String(500), nullable=True,
                                                comment="FTP完整URL,传了则自动解析覆盖连接参数")
    ftp_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="FTP远程文件路径")
    ftp_passive: Mapped[bool] = mapped_column(Integer, default=1, comment="是否被动模式(1是 0否)")
    file_parse: Mapped[bool] = mapped_column(Integer, default=0, comment="是否解析文件入库(1是 0否)")
    file_type: Mapped[str] = mapped_column(String(20), default="auto", comment="文件类型: auto/csv/json/yaml")

    # 接口采集配置
    api_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="接口完整URL")
    api_method: Mapped[str] = mapped_column(String(10), default="POST", comment="请求方法: GET/POST/PUT")
    api_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="请求头")
    api_body: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="请求体或查询参数")
    api_extract_mode: Mapped[str] = mapped_column(String(10), default="both", comment="data/monitor/both")
    api_data_path: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="响应体中业务数据的路径")

    # SNMP 采集配置
    snmp_version: Mapped[str] = mapped_column(String(10), default="v2c", comment="v1/v2c/v3")
    snmp_community: Mapped[str] = mapped_column(String(50), default="public", comment="v1/v2c团体字")
    snmp_user: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="v3用户名")
    snmp_auth_key: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="v3认证密码")
    snmp_priv_key: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="v3加密密码")
    snmp_auth_protocol: Mapped[str] = mapped_column(String(10), default="SHA", comment="v3认证协议")
    snmp_priv_protocol: Mapped[str] = mapped_column(String(10), default="AES", comment="v3加密协议")
    snmp_extract_mode: Mapped[str] = mapped_column(String(10), default="both", comment="metric/info/both")
    snmp_metric_oids: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="指标OID映射")
    snmp_table_oids: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="表格OID映射")

    # Socket 采集配置
    socket_protocol: Mapped[str] = mapped_column(String(10), default="tcp", comment="tcp/udp")
    socket_command: Mapped[str | None] = mapped_column(Text, nullable=True, comment="发送指令")
    socket_command_encoding: Mapped[str] = mapped_column(String(10), default="utf-8", comment="编码")
    socket_timeout: Mapped[int] = mapped_column(Integer, default=10, comment="超时秒数")
    socket_recv_size: Mapped[int] = mapped_column(Integer, default=4096, comment="缓冲区大小")
    socket_terminator: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="结束符")
    socket_response_format: Mapped[str] = mapped_column(String(10), default="json", comment="响应格式")

    # Kafka 采集配置
    kafka_bootstrap_servers: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Kafka地址")
    kafka_topic: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="订阅Topic")
    kafka_group_id: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="消费组ID")
    kafka_auto_offset_reset: Mapped[str | None] = mapped_column(String(20), nullable=True, default="latest")
    kafka_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True, default=500)
    kafka_batch_timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5000)
    kafka_value_format: Mapped[str | None] = mapped_column(String(20), nullable=True, default="json")

    # MQTT 采集配置
    mqtt_broker: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="MQTT Broker地址")
    mqtt_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1883)
    mqtt_topic: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="订阅Topic")
    mqtt_client_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="客户端ID")
    mqtt_qos: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    mqtt_clean_session: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0, comment="0=持久会话")
    mqtt_use_tls: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    mqtt_keepalive: Mapped[int | None] = mapped_column(Integer, nullable=True, default=60)
    mqtt_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True, default=100)
    mqtt_batch_timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3000)
    mqtt_value_format: Mapped[str | None] = mapped_column(String(20), nullable=True, default="json")

    def __repr__(self) -> str:
        return f"<CollectTask(task_name={self.task_name}, status={self.status})>"
