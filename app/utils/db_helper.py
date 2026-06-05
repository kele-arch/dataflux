# -- coding: utf-8 --
# @Author: 胡H
# @File: db_helper.py
# @Created: 2026/6/5 16:23
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from urllib.parse import quote_plus

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
