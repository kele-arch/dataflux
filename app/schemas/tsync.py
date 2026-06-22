# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/tsync.py
# @Created: 2026/6/5 10:06
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from datetime import datetime
from urllib.parse import urlparse

from pydantic import Field, BaseModel, ConfigDict
from typing import Optional, Literal, List

from app.core.config import settings
from app.schemas.base import BaseDecryptReq

_parsed_mongo = urlparse(settings.MONGO_URL)

# 即使没有密码或账号，urlparse 也会安全地解析为 None
_default_host = _parsed_mongo.hostname or "127.0.0.1"
_default_port = _parsed_mongo.port or 27017
_default_user = _parsed_mongo.username
_default_pass = _parsed_mongo.password
_default_db = settings.MONGO_DB_NAME


class DBSyncReq(BaseDecryptReq):
    """ 接收源数据库表单信息 """
    # 对外接口无影响，仅供后台 Worker 和 Engine 流转使用
    task_id: Optional[str] = Field(default=None, description="任务唯一标识(内部流转专用)")

    db_type: Literal[
        "mysql", "postgresql", "oracle", "mongodb", "dm", "ftp", "api", "snmp", "socket", "kafka", "sqlite", "mqtt", "rabbitmq", "oss"] = Field(
        ...,
        description="数据库类型")
    host: str = Field(..., description="主机地址 IP")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    db_name: str = Field(..., description="要同步的数据库名")

    # 选填, 有默认值
    charset: Optional[str] = Field("utf8mb4", description="字符集")
    config_json: Optional[dict] = Field(default=None, description="扩展配置(如Oracle SID、SQLServer实例名)")
    target_table: Optional[str] = Field(default=None, description="指定表名，不填则整库同步")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表，为空则全库同步")
    table_mapping: Optional[dict] = Field(default=None, description="表名映射: {'源表名':'目标表名'}，不传则同名")

    # 核心同步策略
    sync_mode: Literal["insert", "overwrite", "skip"] = Field(
        default="overwrite",
        description="冲突策略: 默认 'overwrite' (覆盖更新)"
    )
    collect_mode: Literal["full", "inc_id", "inc_time", "custom_sql"] = Field(
        default="full",
        description="采集模式: 默认 'full' (全量采集)"
    )

    # 增量高级配置 (默认为 None)
    incremental_column: Optional[str] = Field(
        default=None,
        description="增量依赖的字段名(如 id 或 update_time)"
    )
    last_watermark: Optional[str] = Field(
        default=None,
        description="上次采集的最大水位线(如 2026-06-04 10:00:00)"
    )
    custom_sql: Optional[str] = Field(
        default=None,
        description="自定义提取SQL语句"
    )

    # 目标库类型,默认写 PG(postgresql / mongodb)
    target_type: str = Field(default="postgresql", description="目标库类型: postgresql 或 mongodb")
    # 目标库为 MongoDB 时的连接信息(目前先读取配置写死本机)
    target_host: Optional[str] = Field(default=_default_host, description="目标库主机")
    target_port: Optional[int] = Field(default=_default_port, description="目标库端口")
    target_username: Optional[str] = Field(default=_default_user, description="目标库账号")
    target_password: Optional[str] = Field(default=_default_pass, description="目标库密码")
    target_db_name: Optional[str] = Field(default=_default_db, description="目标库名")
    # target_host: Optional[str] = None
    # target_port: Optional[int] = 27017
    # target_username: Optional[str] = None
    # target_password: Optional[str] = None
    # target_db_name: Optional[str] = None

    # ---- FTP配置参数 ----
    ftp_url: Optional[str] = Field(default=None,
                                   description="FTP完整URL,如 ftp://admin:123456@127.0.0.1:21/data/file.yaml, 传了则自动解析覆盖host/port/username/password/ftp_path")
    ftp_url_scheme: Optional[str] = Field(default=None, description="内部流转: URL解析出的协议类型(ftp/ftps/sftp/sdtp)")
    ftp_path: Optional[str] = Field(default=None, description="FTP远程文件路径,如 /data/calico.yaml")
    ftp_passive: int = Field(default=1, description="是否使用FTP被动模式(1是 0否)")
    local_save_dir: Optional[str] = Field(default=None, description="本地存储目录,不填则用配置默认目录")
    ftp_dir: Optional[str] = Field(default=None, description="批量模式: 远程FTP根目录,如 /factory/logs/")
    file_pattern: Optional[str] = Field(default="*", description="批量模式: 文件通配符,如 *.csv, log_*.xml")
    is_recursive: bool = Field(default=False, description="批量模式: 是否递归遍历子目录")
    file_parse: int = Field(default=0, description="是否解析结构化文件内容入库(1是 0否)")
    file_type: Optional[Literal["csv", "json", "yaml", "xlsx", "xml", "auto"]] = Field(
        default="auto",
        description="文件类型，auto则根据扩展名自动判断"
    )

    # ---- 接口采集专用 ----
    api_url: Optional[str] = Field(default=None, description="接口完整URL")
    api_method: Optional[str] = Field(default="POST", description="请求方法: GET/POST/PUT")
    api_headers: Optional[dict] = Field(default=None, description="请求头")
    api_body: Optional[dict] = Field(default=None, description="请求体或查询参数")
    api_extract_mode: Optional[Literal["data", "monitor", "both"]] = Field(
        default="both", description="data=业务数据入PG, monitor=监控入InfluxDB, both=都要"
    )
    api_data_path: Optional[str] = Field(
        default=None, description="响应体中业务数据的路径，如 data.list 或 $.data.list"
    )

    # ---- SNMP 专用 ----
    snmp_version: Optional[Literal["v1", "v2c", "v3"]] = Field(default="v2c", description="SNMP版本")
    snmp_community: Optional[str] = Field(default="public", description="v1/v2c 团体字")
    # v3 专用
    snmp_user: Optional[str] = Field(default=None, description="v3用户名")
    snmp_auth_key: Optional[str] = Field(default=None, description="v3认证密码")
    snmp_priv_key: Optional[str] = Field(default=None, description="v3加密密码")
    snmp_auth_protocol: Optional[str] = Field(default="SHA", description="v3认证协议: MD5/SHA")
    snmp_priv_protocol: Optional[str] = Field(default="AES", description="v3加密协议: DES/AES")

    snmp_extract_mode: Optional[Literal["metric", "info", "both"]] = Field(
        default="both", description="metric=指标入InfluxDB, info=表格入PG, both=都要"
    )
    # metric模式: {字段名: OID}，每个OID取一个标量值
    snmp_metric_oids: Optional[dict] = Field(default=None, description="性能指标OID映射，如 {'cpu':'1.3.6.1.4.1.x'}")
    # info模式: {字段名: 基础OID}，对每个基础OID做WALK，按索引号聚合成行
    snmp_table_oids: Optional[dict] = Field(default=None,
                                            description="表格列OID映射，如 {'ifDescr':'1.3.6.1.2.1.2.2.1.2'}")

    # ---- Socket 专用 ----
    socket_protocol: Optional[Literal["tcp", "udp"]] = Field(default="tcp", description="传输层协议")
    socket_command: Optional[str] = Field(default=None, description="发送的指令内容")
    socket_command_encoding: Optional[str] = Field(default="utf-8", description="指令编码，二进制协议可用 hex")
    socket_timeout: Optional[int] = Field(default=10, description="超时秒数")
    socket_recv_size: Optional[int] = Field(default=4096, description="单次接收缓冲区大小")
    socket_terminator: Optional[str] = Field(default=None,
                                             description="响应结束符，如 '\\n'，不填则一次性recv后判断超时结束")
    socket_response_format: Optional[Literal["json", "text", "hex"]] = Field(
        default="json", description="响应解析格式"
    )
    # ---- Kafka 专用 ----
    kafka_bootstrap_servers: Optional[str] = Field(default=None, description="Kafka地址，如 127.0.0.1:9092")
    kafka_topic: Optional[str] = Field(default=None, description="订阅的Topic")
    kafka_group_id: Optional[str] = Field(default=None, description="消费组ID，不填则自动用 task_id")
    kafka_auto_offset_reset: Optional[Literal["earliest", "latest"]] = Field(
        default="latest", description="首次消费时的起始位置"
    )
    kafka_batch_size: Optional[int] = Field(default=500, description="攒批大小，满批或超时则写入一次")
    kafka_batch_timeout_ms: Optional[int] = Field(default=5000, description="攒批超时毫秒数")
    kafka_value_format: Optional[Literal["json", "text"]] = Field(default="json", description="消息体解析格式")

    # ---- MQTT 专用 ----
    mqtt_broker: Optional[str] = Field(default=None, description="MQTT Broker地址，如 127.0.0.1")
    mqtt_port: Optional[int] = Field(default=1883, description="MQTT Broker端口，TLS通常用8883")
    mqtt_topic: Optional[str] = Field(default=None, description="订阅的Topic，支持通配符 + 和 #")
    mqtt_client_id: Optional[str] = Field(default=None, description="客户端ID，不填则自动生成")
    mqtt_qos: Optional[int] = Field(default=1, description="服务质量: 0=最多一次 1=至少一次 2=恰好一次")
    mqtt_clean_session: Optional[bool] = Field(default=False, description="False=断线重连补发离线消息")
    mqtt_use_tls: Optional[bool] = Field(default=False, description="是否启用 TLS 加密连接")
    mqtt_keepalive: Optional[int] = Field(default=60, description="心跳间隔秒数")
    mqtt_batch_size: Optional[int] = Field(default=100, description="攒批写入大小")
    mqtt_batch_timeout_ms: Optional[int] = Field(default=3000, description="攒批超时毫秒数")
    mqtt_value_format: Optional[Literal["json", "text", "hex"]] = Field(
        default="json", description="消息体解析格式"
    )

    # ---- RabbitMQ 专用 ----
    mq_host: Optional[str] = Field(default=None, description="RabbitMQ地址")
    mq_port: Optional[int] = Field(default=5672, description="端口，默认5672")
    mq_vhost: Optional[str] = Field(default="/", description="虚拟主机")
    mq_queue: Optional[str] = Field(default=None, description="队列名称")
    mq_exchange: Optional[str] = Field(default=None, description="交换机名称,绑定队列时用")
    mq_exchange_type: Optional[Literal["direct", "topic", "fanout", "headers"]] = Field(
        default="direct", description="交换机类型"
    )
    mq_routing_key: Optional[str] = Field(default=None, description="路由键，topic模式支持通配符 * #")
    mq_durable: Optional[bool] = Field(default=True, description="队列是否持久化")
    mq_prefetch_count: Optional[int] = Field(default=50, description="预取消息数量，控制内存占用")
    mq_batch_size: Optional[int] = Field(default=100, description="攒批写入大小")
    mq_batch_timeout_ms: Optional[int] = Field(default=3000, description="攒批超时毫秒数")
    mq_value_format: Optional[Literal["json", "text", "hex"]] = Field(default="json", description="消息体解析格式")

    # ---- OSS (S3兼容) 专用 ----
    oss_endpoint: Optional[str] = Field(default=None,
                                        description="Endpoint地址，如 https://oss-cn-hangzhou.aliyuncs.com")
    oss_access_key: Optional[str] = Field(default=None, description="AccessKeyId")
    oss_secret_key: Optional[str] = Field(default=None, description="AccessKeySecret")
    oss_bucket: Optional[str] = Field(default=None, description="Bucket名称")
    oss_region: Optional[str] = Field(default=None, description="区域，部分S3兼容存储需要，可留空")

    # 采集模式: 单文件 或 批量前缀
    oss_object_key: Optional[str] = Field(default=None, description="单文件模式：完整对象Key，如 data/2026/calico.yaml")
    oss_prefix: Optional[str] = Field(default=None, description="批量模式：前缀，如 logs/2026-06/，采集该前缀下所有对象")
    oss_max_keys: Optional[int] = Field(default=1000, description="批量模式单次列举的最大对象数")

    oss_use_ssl: Optional[bool] = Field(default=True, description="是否使用HTTPS")
    oss_addressing_style: Optional[Literal["virtual", "path"]] = Field(
        default="virtual", description="virtual=虚拟主机风格(默认) path=路径风格(部分MinIO需要)"
    )


# region ---- 任务管理 ----
class TaskCreateReq(BaseDecryptReq):
    task_name: str = Field(..., description="任务名称")
    # source_id: str = Field(..., description="关联的数据源ID")
    source_id: Optional[str] = Field(default=None, description="数据源ID")
    topic_or_table: Optional[str] = Field(default=None, description="custom_sql模式下目标库写入表名，普通模式可不传")

    schedule_type: str = Field(default="none", description="调度类型: none, cron, interval_min, daily, weekly")
    schedule_value: Optional[str] = Field(default=None, description="配合 type 使用的值，如 '02:30'")

    schedule_cron: Optional[str] = Field(default=None, description="定时任务表达式")
    status: int = Field(default=1, description="任务状态：0停用, 1启用")
    sync_mode: str = Field(default="overwrite", description="冲突策略")
    collect_mode: Literal["full", "inc_id", "inc_time", "custom_sql"] = Field(default="full")
    incremental_column: Optional[str] = Field(default=None)
    last_watermark: Optional[str] = Field(default=None)
    custom_sql: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None, description="备注")
    sync_tables: Optional[List[str]] = Field(default=None, description="指定同步的表名列表")
    table_mapping: Optional[dict] = Field(default=None, description="表名映射: {'源表名':'目标表名'}，不传则同名")

    # 目标库配置 (MongoDB → MongoDB 时需要)
    target_type: str = Field(default="postgresql", description="目标库类型: postgresql 或 mongodb")
    target_host: Optional[str] = Field(default=None, description="目标库主机")
    target_port: Optional[int] = Field(default=None, description="目标库端口")
    target_username: Optional[str] = Field(default=None, description="目标库账号")
    target_password: Optional[str] = Field(default=None, description="目标库密码")
    target_db_name: Optional[str] = Field(default=None, description="目标库名")

    # FTP 采集配置
    ftp_url: Optional[str] = Field(default=None,
                                   description="FTP完整URL,如 ftp://admin:123456@127.0.0.1:21/data/file.yaml, 传了自动解析覆盖连接参数")
    ftp_path: Optional[str] = Field(default=None, description="FTP远程文件路径,如 /data/report.csv")
    ftp_dir: Optional[str] = Field(default=None, description="批量模式: 远程FTP根目录")
    file_pattern: Optional[str] = Field(default="*", description="批量模式: 文件通配符,如 *.csv")
    is_recursive: int = Field(default=0, description="批量模式: 是否递归子目录, 0/1")
    ftp_passive: int = Field(default=1, description="是否使用FTP被动模式(1是 0否)")
    file_parse: int = Field(default=0, description="是否解析结构化文件内容入库(1是 0否)")
    file_type: Optional[Literal["csv", "json", "yaml", "xlsx", "xml", "auto"]] = Field(default="auto",
                                                                                       description="文件类型:auto自动识别")

    # 接口采集配置
    api_url: Optional[str] = Field(default=None, description="接口完整URL")
    api_method: Optional[str] = Field(default="POST", description="请求方法: GET/POST/PUT")
    api_headers: Optional[dict] = Field(default=None, description="请求头")
    api_body: Optional[dict] = Field(default=None, description="请求体或查询参数")
    api_extract_mode: Optional[Literal["data", "monitor", "both"]] = Field(default="both")
    api_data_path: Optional[str] = Field(default=None, description="响应体中业务数据的路径,如 data.list")

    # SNMP 采集配置
    snmp_version: Optional[str] = Field(default="v2c", description="SNMP版本: v1/v2c/v3")
    snmp_community: Optional[str] = Field(default="public", description="v1/v2c团体字")
    snmp_extract_mode: Optional[str] = Field(default="both", description="metric/info/both")
    snmp_metric_oids: Optional[dict] = Field(default=None, description="性能指标OID映射")
    snmp_table_oids: Optional[dict] = Field(default=None, description="表格列OID映射")

    # Socket 采集配置
    socket_protocol: Optional[str] = Field(default="tcp", description="tcp/udp")
    socket_command: Optional[str] = Field(default=None, description="发送的指令内容")
    socket_command_encoding: Optional[str] = Field(default="utf-8", description="指令编码,如 utf-8 或 hex")
    socket_timeout: Optional[int] = Field(default=10, description="单次请求超时秒数")
    socket_recv_size: Optional[int] = Field(default=4096, description="接收缓冲区大小")
    socket_terminator: Optional[str] = Field(default=None, description="响应结束符,如 '\\n'")
    socket_response_format: Optional[str] = Field(default="json", description="json/text/hex")

    # Kafka 采集配置
    kafka_bootstrap_servers: Optional[str] = Field(default=None, description="Kafka地址,如 127.0.0.1:9092")
    kafka_topic: Optional[str] = Field(default=None, description="订阅的Topic")
    kafka_group_id: Optional[str] = Field(default=None, description="消费组ID,不填自动用task_id")
    kafka_auto_offset_reset: Optional[str] = Field(default="latest", description="earliest/latest")
    kafka_batch_size: Optional[int] = Field(default=500, description="攒批大小")
    kafka_batch_timeout_ms: Optional[int] = Field(default=5000, description="攒批超时毫秒")
    kafka_value_format: Optional[str] = Field(default="json", description="json/text")

    # MQTT 采集配置
    mqtt_broker: Optional[str] = Field(default=None, description="MQTT Broker地址,如 127.0.0.1")
    mqtt_port: Optional[int] = Field(default=1883, description="MQTT Broker端口")
    mqtt_topic: Optional[str] = Field(default=None, description="订阅的Topic,支持通配符 + 和 #")
    mqtt_client_id: Optional[str] = Field(default=None, description="客户端ID,不填自动生成")
    mqtt_qos: Optional[int] = Field(default=1, description="服务质量: 0/1/2")
    mqtt_clean_session: Optional[int] = Field(default=0, description="0=全新会话 1=持久会话(断线补发)")
    mqtt_use_tls: Optional[int] = Field(default=0, description="是否启用TLS: 0=否 1=是")
    mqtt_keepalive: Optional[int] = Field(default=60, description="心跳间隔秒数")
    mqtt_batch_size: Optional[int] = Field(default=100, description="攒批大小")
    mqtt_batch_timeout_ms: Optional[int] = Field(default=3000, description="攒批超时毫秒")
    mqtt_value_format: Optional[str] = Field(default="json", description="消息体解析格式: json/text/hex")

    # RabbitMQ 采集配置
    mq_host: Optional[str] = Field(default=None, description="RabbitMQ Broker地址")
    mq_port: Optional[int] = Field(default=5672, description="端口，默认5672")
    mq_vhost: Optional[str] = Field(default="/", description="虚拟主机")
    mq_queue: Optional[str] = Field(default=None, description="队列名称")
    mq_exchange: Optional[str] = Field(default=None, description="交换机名称,绑定队列时用")
    mq_exchange_type: Optional[str] = Field(default="direct", description="交换机类型: direct/topic/fanout/headers")
    mq_routing_key: Optional[str] = Field(default=None, description="路由键，topic模式支持通配符 * #")
    mq_durable: Optional[int] = Field(default=1, description="队列是否持久化")
    mq_prefetch_count: Optional[int] = Field(default=50, description="预取消息数量")
    mq_batch_size: Optional[int] = Field(default=100, description="攒批大小")
    mq_batch_timeout_ms: Optional[int] = Field(default=3000, description="攒批超时毫秒")
    mq_value_format: Optional[str] = Field(default="json", description="消息体解析格式: json/text/hex")

    # OSS (S3兼容) 采集配置
    oss_endpoint: Optional[str] = Field(default=None, description="Endpoint地址")
    oss_access_key: Optional[str] = Field(default=None, description="AccessKeyId")
    oss_secret_key: Optional[str] = Field(default=None, description="AccessKeySecret")
    oss_bucket: Optional[str] = Field(default=None, description="Bucket名称")
    oss_region: Optional[str] = Field(default=None, description="区域(可留空)")
    oss_object_key: Optional[str] = Field(default=None, description="单文件模式: 完整对象Key")
    oss_prefix: Optional[str] = Field(default=None, description="批量模式: 前缀")
    oss_max_keys: Optional[int] = Field(default=1000, description="批量列举最大对象数")
    oss_use_ssl: Optional[int] = Field(default=1, description="是否HTTPS: 0/1")
    oss_addressing_style: Optional[str] = Field(default="virtual", description="virtual/path")

    # 数据清理策略
    clean_policy: Optional[str] = Field(default="none", description="清理策略: none/by_days/by_count")
    clean_keep_days: Optional[int] = Field(default=None, description="按天保留: 保留最近N天")
    clean_keep_count: Optional[int] = Field(default=None, description="按条数保留: 保留最新N条")
    clean_cron: Optional[str] = Field(default=None, description="自动清理Cron表达式,如 '0 3 * * *'")


class TaskUpdateReq(TaskCreateReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="要更新的任务ID(UUID)")
    schedule_type: Optional[str] = Field(default=None)
    schedule_value: Optional[str] = Field(default=None)


class TaskIdReq(BaseDecryptReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID(UUID)")


class TaskStatusReq(BaseDecryptReq):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID(UUID)")
    status: int = Field(..., description="目标状态: 0=停用, 1=启用")


class TaskPageQueryReq(BaseDecryptReq):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1)
    task_name: Optional[str] = Field(default=None, description="按任务名模糊搜索")
    collect_mode: Optional[str] = Field(default=None, description="按采集模式过滤")
    db_type: Optional[str] = Field(default=None, description="按数据源类型过滤, 如 kafka, mysql")
    sort_by: Optional[Literal["create_time", "update_time", "task_name"]] = Field(default="create_time",
                                                                                  description="排序字段")
    sort_order: Optional[Literal["asc", "desc"]] = Field(default="desc", description="排序方向")


class TaskOut(BaseModel):
    id: str
    task_name: str
    source_id: Optional[str] = None
    db_type: Optional[str] = None
    topic_or_table: Optional[str]
    status: int
    run_status: Optional[str] = "idle"
    current_log_id: Optional[str] = None
    sync_mode: str
    collect_mode: str
    incremental_column: Optional[str]
    last_watermark: Optional[str]
    remark: Optional[str]
    create_time: Optional[datetime]
    update_time: Optional[datetime]
    sync_tables: Optional[List[str]]
    table_mapping: Optional[dict] = None
    schedule_type: Optional[str]
    schedule_value: Optional[str]
    target_type: Optional[str] = "postgresql"
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    target_db_name: Optional[str] = None
    ftp_url: Optional[str] = None
    ftp_path: Optional[str] = None
    ftp_dir: Optional[str] = None
    file_pattern: Optional[str] = "*"
    is_recursive: Optional[int] = 0
    ftp_passive: Optional[int] = 1
    file_parse: Optional[int] = 0
    file_type: Optional[str] = "auto"
    api_url: Optional[str] = None
    api_method: Optional[str] = "POST"
    api_extract_mode: Optional[str] = "both"
    api_data_path: Optional[str] = None
    snmp_version: Optional[str] = "v2c"
    snmp_community: Optional[str] = "public"
    snmp_extract_mode: Optional[str] = "both"
    snmp_metric_oids: Optional[dict] = None
    snmp_table_oids: Optional[dict] = None
    socket_protocol: Optional[str] = "tcp"
    socket_command: Optional[str] = None
    socket_command_encoding: Optional[str] = "utf-8"
    socket_timeout: Optional[int] = 10
    socket_recv_size: Optional[int] = 4096
    socket_terminator: Optional[str] = None
    socket_response_format: Optional[str] = "json"
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic: Optional[str] = None
    kafka_group_id: Optional[str] = None
    kafka_auto_offset_reset: Optional[str] = "latest"
    kafka_batch_size: Optional[int] = 500
    kafka_batch_timeout_ms: Optional[int] = 5000
    kafka_value_format: Optional[str] = "json"
    mqtt_broker: Optional[str] = None
    mqtt_port: Optional[int] = 1883
    mqtt_topic: Optional[str] = None
    mqtt_client_id: Optional[str] = None
    mqtt_qos: Optional[int] = 1
    mqtt_use_tls: Optional[int] = 0
    mqtt_keepalive: Optional[int] = 60
    mqtt_batch_size: Optional[int] = 100
    mqtt_batch_timeout_ms: Optional[int] = 3000
    mqtt_value_format: Optional[str] = "json"

    mq_host: Optional[str] = None
    mq_port: Optional[int] = 5672
    mq_vhost: Optional[str] = "/"
    mq_queue: Optional[str] = None
    mq_exchange: Optional[str] = None
    mq_exchange_type: Optional[str] = "direct"
    mq_routing_key: Optional[str] = None
    mq_durable: Optional[int] = 1
    mq_prefetch_count: Optional[int] = 50
    mq_batch_size: Optional[int] = 100
    mq_batch_timeout_ms: Optional[int] = 3000
    mq_value_format: Optional[str] = "json"
    oss_endpoint: Optional[str] = None
    oss_bucket: Optional[str] = None
    oss_region: Optional[str] = None
    oss_object_key: Optional[str] = None
    oss_prefix: Optional[str] = None
    oss_addressing_style: Optional[str] = "virtual"
    clean_policy: Optional[str] = "none"
    clean_keep_days: Optional[int] = None
    clean_keep_count: Optional[int] = None
    clean_cron: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskPageOut(BaseModel):
    total: int
    items: List[TaskOut]
    model_config = ConfigDict(from_attributes=True)


# endregion

# region ---- 仪表盘统计 ----
class DashboardOut(BaseModel):
    total_tasks: int
    active_tasks: int
    today_records: int
    success_rate: float


# endregion

# region ---- 数据清理 ----
class TaskCleanReq(BaseModel):
    task_id: str = Field(..., min_length=32, max_length=32)
    action: Literal["truncate", "drop", "by_days", "by_count"] = Field(
        ..., description="清理操作: truncate=清空 drop=删表 by_days=按天 by_count=按条数"
    )
    keep_days: Optional[int] = Field(default=None, description="by_days模式: 保留最近N天")
    keep_count: Optional[int] = Field(default=None, description="by_count模式: 保留最新N条")
    clean_files: bool = Field(default=True, description="是否同时清理本地缓存文件")
# endregion

# region ---- 文件同步记录查询 ----
class RecordQueryReq(BaseModel):
    task_id: str = Field(..., min_length=32, max_length=32, description="关联的采集任务 ID")
    file_type: Optional[str] = Field(default=None, description="按文件类型过滤: csv/json/yaml/xlsx/xml/binary")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, description="每页条数")


# endregion


# region ----- kafka的influx数据获取 ----
class MonitorTrendReq(BaseModel):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID")
    minutes: int = Field(default=30, ge=1, description="查询过去多少分钟的数据")
# endregion
