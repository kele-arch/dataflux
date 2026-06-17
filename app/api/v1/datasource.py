# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/datasource.py
# @Created: 2026/6/5 15:25
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, inspect
from typing import List, Dict, Any
import boto3
from botocore.config import Config as BotoConfig
from botocore import UNSIGNED

from app.db.session import get_db
from app.models.dataSourceModel import DataSource
from app.schemas.response import BaseResponse
from app.schemas.datasource import (
    DataSourceCreateReq, DataSourceUpdateReq, DataSourceIdReq,
    DataSourcePageQueryReq, DataSourceOut, DataSourceBase, DataSourcePageOut,
    FtpExploreReq, OssTreeReq
)
from app.crud.crud_datasource import crud_datasource
from app.services.ftp_explorer import FtpExplorer
from app.utils.db_helper import build_db_url, get_mongo_collections, _get_mongo_collections_detail

router = APIRouter(prefix="/datasource", tags=["数据源管理"])


@router.post("/test_connect", summary="测试数据库连接", response_model=BaseResponse)
def test_db_connection(req: DataSourceBase):
    try:
        if req.type.lower() == "mongodb":
            get_mongo_collections(
                host=req.host,
                port=req.port,
                db_name=req.db_name,
                username=req.username,
                password=req.password
            )
            return BaseResponse(msg="连接成功！MongoDB 通信正常")

        if req.type.lower() == "api":
            return BaseResponse(code=0, msg="接口采集不需要测试连接，请在任务中配置 api_url 后直接执行")

        if req.type.lower() in ("snmp", "socket", "kafka", "mqtt", "rabbitmq"):
            return BaseResponse(code=0,
                                msg="SNMP/Socket/Kafka/MQTT/RabbitMQ 采集不需要测试连接，请在任务中配置相关参数后直接执行")

        if req.type.lower() == "oss":
            try:
                import boto3
                from botocore.config import Config as BotoConfig
                config = req.config_json or {}
                client = boto3.client(
                    "s3",
                    endpoint_url=config.get("endpoint") or f"https://{req.host}",
                    aws_access_key_id=req.username or "",
                    aws_secret_access_key=req.password or "",
                    region_name=config.get("region") or "us-east-1",
                    config=BotoConfig(s3={"addressing_style": "virtual"}, signature_version="s3v4"),
                )
                client.list_buckets()
                return BaseResponse(msg="连接成功！OSS/S3 通信正常")
            except Exception as e:
                return BaseResponse(code=0, msg=f"连接失败: {str(e)}")

        if req.type.lower() == "ftp":
            from ftplib import FTP, FTP_TLS, error_perm
            ftp = FTP()
            try:
                ftp.connect(host=req.host, port=req.port or 21, timeout=5)
                ftp.login(user=req.username or "anonymous", passwd=req.password or "")
            except error_perm as e:
                if "503" in str(e) or "AUTH" in str(e).upper():
                    ftp.close()
                    ftp = FTP_TLS()
                    ftp.connect(host=req.host, port=req.port or 21, timeout=5)
                    ftp.login(user=req.username or "anonymous", passwd=req.password or "")
                    ftp.prot_p()
                else:
                    raise e
            ftp.quit()
            return BaseResponse(msg="连接成功！FTP(S) 通信正常")

        url = build_db_url(req)

        # dmPython / SQLite 不支持 connect_args 超时参数, 不传
        if req.type.lower() in ("dm", "sqlite"):
            engine = create_engine(url)
        else:
            engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            with engine.connect():
                pass
        finally:
            engine.dispose()

        return BaseResponse(msg="连接成功！数据库通信正常。")

    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


@router.post("/add", summary="新增数据源", response_model=BaseResponse)
def add_datasource(req: DataSourceCreateReq, db: Session = Depends(get_db)):
    obj = crud_datasource.create(db, req)
    return BaseResponse(data={"id": obj.id}, msg="数据源保存成功")


@router.post("/update", summary="修改数据源", response_model=BaseResponse)
def update_datasource(req: DataSourceUpdateReq, db: Session = Depends(get_db)):
    success = crud_datasource.update(db, req)
    if not success:
        return BaseResponse(code=0, msg=f"该场景下已存在名为 [{req.name}] 的实体")
    return BaseResponse(msg="数据源更新成功")


@router.post("/delete", summary="删除数据源", response_model=BaseResponse)
def delete_datasource(req: DataSourceIdReq, db: Session = Depends(get_db)):
    success = crud_datasource.delete(db, req.source_id)
    if not success:
        return BaseResponse(code=0, msg="删除失败")
    return BaseResponse(msg="数据源已删除")


@router.post("/list", summary="获取数据源列表", response_model=BaseResponse[DataSourcePageOut])
def get_datasource_list(req: DataSourcePageQueryReq, db: Session = Depends(get_db)):
    # 直接拿到 total 和 ORM 对象列表 (items)
    total, items = crud_datasource.get_list(db, req)

    return BaseResponse(data={"total": total, "items": items}, msg="获取成功")


@router.post("/tables", summary="获取该数据源下的所有表名", response_model=BaseResponse[List[str]])
def get_datasource_tables(req: DataSourceIdReq, db: Session = Depends(get_db)):
    source = crud_datasource.get_by_id(db, req.source_id)
    if not source:
        return BaseResponse(code=0, msg="数据源不存在")

    try:
        if source.type.lower() == "mongodb":
            collections = get_mongo_collections(
                host=source.host,
                port=source.port,
                db_name=source.db_name,
                username=source.username,
                password=source.password
            )
            return BaseResponse(data=collections, msg="获取成功")

        if source.type.lower() == "api":
            return BaseResponse(code=0, msg="接口采集不支持表查询")

        if source.type.lower() in ("snmp", "socket", "kafka", "mqtt", "rabbitmq", "oss"):
            return BaseResponse(code=0, msg="SNMP/Socket/Kafka/MQTT/RabbitMQ/OSS 采集不支持表查询")

        if source.type.lower() == "ftp":
            return BaseResponse(code=0, msg="FTP 数据源不支持表查询，请在任务中配置 ftp_path")

        url = build_db_url(source)
        engine = create_engine(url) if source.type.lower() in ("dm", "sqlite") else create_engine(url, connect_args={
            "connect_timeout": 3})
        try:
            inspector = inspect(engine)
            return BaseResponse(data=inspector.get_table_names(), msg="获取成功")
        finally:
            engine.dispose()
    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


@router.post("/tables/detail", summary="获取表结构详情(含表注释和字段注释)",
             response_model=BaseResponse[List[Dict[str, Any]]])
def get_datasource_tables_detail(req: DataSourceIdReq, db: Session = Depends(get_db)):
    """返回每张表的表名、表注释、字段名、字段类型、字段注释"""
    source = crud_datasource.get_by_id(db, req.source_id)
    if not source:
        return BaseResponse(code=0, msg="数据源不存在")

    try:
        if source.type.lower() == "mongodb":
            return BaseResponse(
                data=_get_mongo_collections_detail(source),
                msg="获取成功"
            )

        if source.type.lower() == "api":
            return BaseResponse(code=0, msg="接口采集不支持表结构查询")

        if source.type.lower() in ("snmp", "socket", "kafka", "mqtt", "rabbitmq", "oss"):
            return BaseResponse(code=0, msg="SNMP/Socket/Kafka/MQTT/RabbitMQ/OSS 采集不支持表结构查询")

        if source.type.lower() == "ftp":
            return BaseResponse(code=0, msg="FTP 数据源不支持表结构查询")

        url = build_db_url(source)
        engine = create_engine(url) if source.type.lower() in ("dm", "sqlite") else create_engine(url, connect_args={
            "connect_timeout": 3})
        try:
            inspector = inspect(engine)
            result = []

            for table_name in inspector.get_table_names():
                # 表注释
                table_comment = (inspector.get_table_comment(table_name) or {}).get("text") or ""

                # 字段信息
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        "name": col["name"],
                        "type": str(col["type"]),
                        "comment": col.get("comment") or ""
                    })

                result.append({
                    "table_name": table_name,
                    "table_comment": table_comment,
                    "columns": columns
                })

            return BaseResponse(data=result, msg="获取成功")
        finally:
            engine.dispose()
    except Exception as e:
        return BaseResponse(code=0, msg=f"连接失败: {str(e)}")


# region ---- FTP/SFTP 目录树勘探 ----
@router.post("/ftp/dir_tree", summary="获取FTP/SFTP数据源文件目录树")
async def get_ftp_dir_tree(req: FtpExploreReq, db: Session = Depends(get_db)):
    """
    通过数据源ID安全地连接远程服务器并获取文件目录树形结构
    - 支持 FTP / FTPS / SFTP 三种协议, 通过数据源 config_json.protocol 指定
    - 默认懒加载模式（只返回当前层级）,前端展开节点时再次请求下级
    - 所有同步网络 I/O 切入 asyncio.to_thread, 绝不阻塞主事件循环
    """

    # 校验数据源
    datasource = crud_datasource.get_by_id(db, req.datasource_id)
    if not datasource:
        return BaseResponse(code=0, msg="未找到对应的数据源记录", data=[])

    if datasource.type != "ftp":
        return BaseResponse(code=0, msg="该数据源不是 FTP/SFTP 类型,无法进行文件勘探", data=[])

    config = datasource.config_json or {}
    protocol = config.get("protocol", "ftp").lower()
    if protocol not in ("ftp", "ftps", "sftp"):
        return BaseResponse(code=0, msg=f"不支持的协议类型: {protocol}，可选: ftp / ftps / sftp", data=[])

    # FTP/FTPS 路径去掉前导 /，SFTP 保留绝对路径
    remote_path = req.remote_path or "/"
    if protocol in ("ftp", "ftps") and remote_path.startswith("/"):
        remote_path = remote_path.lstrip("/") or "."

    try:
        explorer = FtpExplorer(
            host=datasource.host,
            port=datasource.port,
            username=datasource.username or "",
            password=datasource.password or "",
            protocol=protocol,
        )

        tree_data = await asyncio.to_thread(
            explorer.get_dir_tree,
            remote_path=remote_path,
            recursive=req.recursive,
            max_depth=req.max_depth,
        )

        return {
            "msg": "获取成功",
            "data": tree_data,
        }

    except Exception as e:
        return {
            "code": 0,
            "msg": f"文件目录树获取失败: {str(e)}",
            "data": [],
        }


# endregion


# region ---- OSS/MinIO 目录树勘探 ----
@router.post("/oss/tree", summary="获取OSS/MinIO指定层级的目录树")
def get_oss_tree(req: OssTreeReq, db: Session = Depends(get_db)):
    source = db.query(DataSource).filter(DataSource.id == req.source_id).first()
    if not source or source.type != "oss":
        return BaseResponse(code=0, msg="数据源不存在或不是OSS类型")

    try:
        # 动态鉴权配置（免密兜底）
        if not source.username or not source.password:
            boto_config = BotoConfig(signature_version=UNSIGNED, retries={"max_attempts": 2})
            ak, sk = None, None
        else:
            boto_config = BotoConfig(signature_version="s3v4", retries={"max_attempts": 2})
            ak, sk = source.username, source.password

        # 寻址风格推断
        addressing_style = "path" if "127.0.0.1" in source.host or ":9000" in source.host else "virtual"
        boto_config.s3 = {"addressing_style": addressing_style}

        client = boto3.client(
            "s3",
            endpoint_url=source.host,
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            config=boto_config
        )

        # 调用 S3 接口,传入 Body 里的 prefix
        resp = client.list_objects_v2(
            Bucket=source.db_name,
            Prefix=req.prefix,
            Delimiter='/'  # 核心：按目录折叠
        )

        nodes = []

        # 解析子目录
        for cp in resp.get("CommonPrefixes", []):
            folder_path = cp["Prefix"]
            folder_name = folder_path[len(req.prefix):].strip('/')
            nodes.append({
                "type": "folder",
                "name": folder_name,
                "full_path": folder_path,
                "is_leaf": False
            })

        # 解析当前目录下的文件
        for obj in resp.get("Contents", []):
            file_path = obj["Key"]
            if file_path == req.prefix:
                continue

            file_name = file_path[len(req.prefix):]
            nodes.append({
                "type": "file",
                "name": file_name,
                "full_path": file_path,
                "size": obj.get("Size", 0),
                "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                "is_leaf": True
            })

        return BaseResponse(msg="获取成功", data=nodes)

    except Exception as e:
        return BaseResponse(code=0, msg=f"获取目录树失败: {str(e)}")

# endregion
