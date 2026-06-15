# -- coding: utf-8 --
# @Author: 胡H
# @File:  app/services/engine_factory.py
# @Created: 2026/6/8 9:58
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据库同步引擎工厂类,根据用户请求的数据库类型返回对应的同步引擎实例

from app.schemas.tsync import DBSyncReq
from app.services.api_sync_engine import ApiSyncEngine
from app.services.ftp_sync_engine import FtpSyncEngine
from app.services.snmp_sync_engine import SnmpSyncEngine
from app.services.socket_sync_engine import SocketSyncEngine
from app.services.sync_service import DatabaseSyncEngine
from app.services.mongo_sync_engine import MongoSyncEngine


class EngineFactory:
    @staticmethod
    def create(req: DBSyncReq):
        db_type = req.db_type.lower()
        if db_type == "mongodb":
            return MongoSyncEngine(req)
        elif db_type == "ftp":
            return FtpSyncEngine(req)
        elif db_type == "api":
            return ApiSyncEngine(req)
        elif db_type == "snmp":
            return SnmpSyncEngine(req)
        elif db_type == "socket":
            return SocketSyncEngine(req)
        elif db_type in ("mysql", "postgresql", "dm", "oracle", "sqlserver", "sqlite"):
            return DatabaseSyncEngine(req)
        else:
            raise ValueError(f"不支持的数据库类型: {req.db_type}")
