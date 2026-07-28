# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/task_preflight.py
# @Created: 2026/7/28 11:50
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 任务配置预检与多类型数据源只读预览服务

import re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote_plus, urlparse

import httpx
from bson import ObjectId
from pymongo import MongoClient
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.utils.db_helper import build_db_url


_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_MUTATING_SQL = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|truncate|create|grant|revoke|call|execute)\b",
    re.IGNORECASE,
)


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _check(name: str, ok: bool, message: str) -> dict:
    return {"name": name, "status": "passed" if ok else "failed", "message": message}


class TaskPreflightService:
    relational_types = {"mysql", "postgresql", "oracle", "sqlserver", "dm", "sqlite", "vastbase"}

    def validate(self, task, source) -> dict:
        source_type = source.type.lower()
        checks = [
            {
                "name": "task_enabled",
                "status": "passed" if task.status == 1 else "warning",
                "message": "任务已启用" if task.status == 1 else "任务处于停用状态，配置仍可预检但不能执行",
            },
            _check("source_exists", True, f"数据源存在，类型为 {source_type}"),
        ]

        if task.clean_policy and task.clean_policy != "none":
            checks.append(
                _check(
                    "clean_target",
                    bool((task.topic_or_table or "").strip()),
                    "已配置精确清理目标表" if task.topic_or_table else "启用清理策略时必须配置 topic_or_table",
                )
            )

        try:
            if source_type in self.relational_types:
                checks.extend(self._validate_relational(task, source))
            elif source_type == "mongodb":
                checks.extend(self._validate_mongo(task, source))
            else:
                checks.extend(self._validate_non_database(task, source, source_type))
        except Exception as exc:
            checks.append(_check("connection", False, f"连接或元数据检查失败: {exc}"))

        return {
            "valid": all(item["status"] != "failed" for item in checks),
            "source_type": source_type,
            "checks": checks,
        }

    def _validate_relational(self, task, source) -> list[dict]:
        engine = create_engine(build_db_url(source), pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                probe_sql = "SELECT 1 FROM DUAL" if source.type.lower() == "oracle" else "SELECT 1"
                conn.execute(text(probe_sql))

            inspector = inspect(engine)
            schema = source.username.upper() if source.type.lower() in ("dm", "oracle") else None
            available = set(inspector.get_table_names(schema=schema))
            requested = list(task.sync_tables or [])
            checks = [_check("connection", True, "数据库连接成功")]

            if requested:
                missing = [name for name in requested if name not in available]
                checks.append(
                    _check(
                        "source_tables",
                        not missing,
                        "指定源表均存在" if not missing else f"源表不存在: {missing}",
                    )
                )
            else:
                checks.append(_check("source_tables", bool(available), f"检测到 {len(available)} 张源表"))

            if task.collect_mode in ("inc_id", "inc_time"):
                column = task.incremental_column
                selected = requested or list(available)
                missing_column = []
                for table_name in selected:
                    if table_name not in available:
                        continue
                    columns = {
                        item["name"].lower()
                        for item in inspector.get_columns(table_name, schema=schema)
                    }
                    if not column or column.lower() not in columns:
                        missing_column.append(table_name)
                checks.append(
                    _check(
                        "incremental_column",
                        bool(column) and not missing_column,
                        "增量字段在所有源表中存在"
                        if column and not missing_column
                        else f"以下表缺少增量字段 [{column}]: {missing_column}",
                    )
                )

            if task.collect_mode == "custom_sql":
                sql = (task.custom_sql or "").strip()
                safe = bool(sql) and _READ_ONLY_SQL.match(sql) and not _MUTATING_SQL.search(sql)
                checks.append(_check("custom_sql", bool(safe), "自定义 SQL 为只读查询" if safe else "只允许只读 SELECT/WITH 查询"))
                checks.append(_check("target_table", bool(task.topic_or_table), "已配置目标表" if task.topic_or_table else "custom_sql 必须配置目标表"))

            return checks
        finally:
            engine.dispose()

    def _mongo_client(self, source):
        username = quote_plus(source.username or "")
        password = quote_plus(source.password or "")
        auth = f"{username}:{password}@" if username else ""
        auth_source = "?authSource=admin" if username else ""
        uri = f"mongodb://{auth}{source.host}:{source.port}/{source.db_name}{auth_source}"
        return MongoClient(uri, serverSelectionTimeoutMS=5000)

    def _validate_mongo(self, task, source) -> list[dict]:
        client = self._mongo_client(source)
        try:
            client.admin.command("ping")
            available = set(client[source.db_name].list_collection_names())
            requested = list(task.sync_tables or [])
            missing = [name for name in requested if name not in available]
            return [
                _check("connection", True, "MongoDB 连接成功"),
                _check(
                    "source_collections",
                    not missing and bool(available),
                    f"检测到 {len(available)} 个集合" if not missing else f"集合不存在: {missing}",
                ),
                _check(
                    "incremental_column",
                    task.collect_mode != "inc_time" or bool(task.incremental_column),
                    "增量配置有效"
                    if task.collect_mode != "inc_time" or task.incremental_column
                    else "inc_time 模式必须配置 incremental_column",
                ),
            ]
        finally:
            client.close()

    def _validate_non_database(self, task, source, source_type: str) -> list[dict]:
        required = {
            "api": [("api_url", task.api_url)],
            "ftp": [("ftp_path_or_dir", task.ftp_path or task.ftp_dir or task.ftp_url)],
            "ftps": [("ftp_path_or_dir", task.ftp_path or task.ftp_dir or task.ftp_url)],
            "sftp": [("ftp_path_or_dir", task.ftp_path or task.ftp_dir or task.ftp_url)],
            "oss": [("oss_bucket", task.oss_bucket or source.db_name)],
            "snmp": [("snmp_metric_or_table_oids", task.snmp_metric_oids or task.snmp_table_oids)],
            "socket": [("socket_host_port", bool(source.host and source.port))],
            "kafka": [("kafka_topic", task.kafka_topic), ("target_table", task.topic_or_table)],
            "mqtt": [("mqtt_topic", task.mqtt_topic), ("target_table", task.topic_or_table)],
            "rabbitmq": [("mq_queue", task.mq_queue), ("target_table", task.topic_or_table)],
        }.get(source_type, [])
        checks = [
            _check(name, bool(value), f"{name} 已配置" if value else f"缺少必要配置: {name}")
            for name, value in required
        ]
        if source_type == "api" and task.api_url:
            parsed = urlparse(task.api_url)
            checks.append(_check("api_url", parsed.scheme in ("http", "https") and bool(parsed.netloc), "API URL 格式有效"))
        return checks or [_check("configuration", True, "未发现需要额外检查的配置")]

    def preview(self, task, source, table_name: str | None, limit: int) -> dict:
        source_type = source.type.lower()
        if source_type in self.relational_types:
            return self._preview_relational(task, source, table_name, limit)
        if source_type == "mongodb":
            return self._preview_mongo(task, source, table_name, limit)
        if source_type == "api":
            return self._preview_api(task, limit)
        return {
            "supported": False,
            "source_type": source_type,
            "message": "该类型预览可能启动消费或下载文件，仅提供配置预检",
            "rows": [],
        }

    def _preview_relational(self, task, source, table_name: str | None, limit: int) -> dict:
        engine = create_engine(build_db_url(source), pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                if task.collect_mode == "custom_sql":
                    sql = (task.custom_sql or "").strip().rstrip(";")
                    if not sql or not _READ_ONLY_SQL.match(sql) or _MUTATING_SQL.search(sql):
                        raise ValueError("预览只允许只读 SELECT/WITH 查询")
                    rows = conn.execute(text(sql)).mappings().fetchmany(limit)
                    selected_name = "custom_sql"
                else:
                    inspector = inspect(engine)
                    schema = source.username.upper() if source.type.lower() in ("dm", "oracle") else None
                    available = inspector.get_table_names(schema=schema)
                    selected_name = table_name or next(iter(task.sync_tables or []), None) or next(iter(available), None)
                    if not selected_name or selected_name not in available:
                        raise ValueError(f"源表不存在: {selected_name}")
                    metadata = MetaData()
                    table = Table(selected_name, metadata, schema=schema, autoload_with=engine)
                    rows = conn.execute(select(table).limit(limit)).mappings().all()
            return {
                "supported": True,
                "source_type": source.type.lower(),
                "object_name": selected_name,
                "limit": limit,
                "rows": [_json_value(dict(row)) for row in rows],
            }
        finally:
            engine.dispose()

    def _preview_mongo(self, task, source, table_name: str | None, limit: int) -> dict:
        client = self._mongo_client(source)
        try:
            database = client[source.db_name]
            available = database.list_collection_names()
            selected_name = table_name or next(iter(task.sync_tables or []), None) or next(iter(available), None)
            if not selected_name or selected_name not in available:
                raise ValueError(f"集合不存在: {selected_name}")
            rows = list(database[selected_name].find({}).limit(limit))
            return {
                "supported": True,
                "source_type": "mongodb",
                "object_name": selected_name,
                "limit": limit,
                "rows": [_json_value(row) for row in rows],
            }
        finally:
            client.close()

    def _preview_api(self, task, limit: int) -> dict:
        if (task.api_method or "GET").upper() != "GET":
            return {
                "supported": False,
                "source_type": "api",
                "message": "为避免产生副作用，预览只允许 GET API",
                "rows": [],
            }
        response = httpx.get(
            task.api_url,
            headers=task.api_headers or {},
            params=task.api_body or {},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            rows = payload[:limit]
        else:
            rows = [payload]
        return {
            "supported": True,
            "source_type": "api",
            "object_name": task.api_url,
            "limit": limit,
            "rows": _json_value(rows),
        }


task_preflight_service = TaskPreflightService()
