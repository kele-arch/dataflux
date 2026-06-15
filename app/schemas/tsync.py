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

    db_type: Literal["mysql", "postgresql", "oracle", "mongodb", "dm", "ftp", "api", "snmp", "socket", "kafka", "sqlite"] = Field(
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

# region ----- kafka的influx数据获取 ----
class MonitorTrendReq(BaseModel):
    task_id: str = Field(..., min_length=32, max_length=32, description="任务ID")
    minutes: int = Field(default=30, ge=1, description="查询过去多少分钟的数据")
# endregion
