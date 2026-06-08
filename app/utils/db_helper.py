# -- coding: utf-8 --
# @Author: 胡H
# @File: db_helper.py
# @Created: 2026/6/5 16:23
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from urllib.parse import quote_plus
from pymongo import MongoClient

from sqlalchemy.engine.url import URL


def build_db_url(source_data) -> str:
    """
    通过 SQLAlchemy URL 工厂构建连接串
    """
    db_type = source_data.type.lower()
    username = getattr(source_data, "username", "")
    password = getattr(source_data, "password", "")

    # 映射驱动名称
    driver_map = {
        "mysql": "mysql+pymysql",
        "postgresql": "postgresql+psycopg2",
        "oracle": "oracle+cx_oracle"
    }

    driver = driver_map.get(db_type)
    if not driver:
        raise ValueError(f"暂不支持的数据库类型: {db_type}")

    config = getattr(source_data, "config_json", {}) or {}
    charset = config.get("charset", "utf8mb4")

    url = URL.create(
        drivername=driver,
        username=username,
        password=password,
        host=source_data.host,
        port=source_data.port,
        database=source_data.db_name
    )

    # 只有 MySQL 需要附加 charset 参数
    if db_type == "mysql":
        url = url.set(query={"charset": charset})

    return url.render_as_string(hide_password=False)


def get_mongo_collections(host: str, port: int, db_name: str,
                          username: str = None, password: str = None) -> list:
    """
    用 pymongo 获取 MongoDB 的集合列表,对应关系型的"表列表"
    """
    safe_password = quote_plus(password or "")
    if username:
        url = f"mongodb://{username}:{safe_password}@{host}:{port}/{db_name}?authSource=admin"
    else:
        url = f"mongodb://{host}:{port}/{db_name}"

    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    try:
        collections = client[db_name].list_collection_names()
        # 过滤系统集合
        return [c for c in collections if not c.startswith("system.")]
    finally:
        client.close()


def _get_mongo_collections_detail(source) -> list:
    """
    MongoDB 没有固定表结构,采样每个集合的第一条文档推断字段列表
    """
    from pymongo import MongoClient
    from urllib.parse import quote_plus
    from bson import ObjectId
    from datetime import datetime

    safe_password = quote_plus(source.password or "")
    if source.username:
        url = f"mongodb://{source.username}:{safe_password}@{source.host}:{source.port}/{source.db_name}?authSource=admin"
    else:
        url = f"mongodb://{source.host}:{source.port}/{source.db_name}"

    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    result = []

    try:
        mongo_db = client[source.db_name]
        collections = [c for c in mongo_db.list_collection_names()
                       if not c.startswith("system.")]

        for col_name in collections:
            # 采样一条文档推断字段
            sample_doc = mongo_db[col_name].find_one()
            columns = []

            if sample_doc:
                for field_name, field_val in sample_doc.items():
                    # 推断字段类型
                    if isinstance(field_val, ObjectId):
                        field_type = "ObjectId"
                    elif isinstance(field_val, datetime):
                        field_type = "datetime"
                    elif isinstance(field_val, bool):
                        field_type = "bool"
                    elif isinstance(field_val, int):
                        field_type = "int"
                    elif isinstance(field_val, float):
                        field_type = "float"
                    elif isinstance(field_val, dict):
                        field_type = "object"
                    elif isinstance(field_val, list):
                        field_type = "array"
                    else:
                        field_type = "string"

                    columns.append({
                        "name": field_name,
                        "type": field_type,
                        "comment": ""  # MongoDB 没有字段注释
                    })

            result.append({
                "table_name": col_name,
                "table_comment": f"MongoDB Collection（采样自首条文档，共 {mongo_db[col_name].estimated_document_count()} 条）",
                "columns": columns
            })

    finally:
        client.close()

    return result
