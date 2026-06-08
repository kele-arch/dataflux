# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/config.py
# @Created: 2025/11/19 10:37
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:
from pydantic_settings import BaseSettings

from app.core import project_rootpath


class Settings(BaseSettings):
    """ Pydantic BaseSettings 会自动从 .env 覆盖默认值. 如果没有值则使用默认值"""
    ENV: str = "development"
    DB_SCHEMA: str = "public"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:654321@localhost:5432/test"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8011
    LOG_LEVEL: str = "info"

    SECRET_KEY: str = "abc123xyz456def789ghi012jkl345mno678pqr901stu234vwx567yz"
    ALGORITHM: str = "HS256"

    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1天

    MONGO_URL: str = "mongodb://localhost:27017"  # MongoDB 连接 URL
    MONGO_DB_NAME: str = "dataflux"  # MongoDB 数据库名称

    ENABLE_DB_CHECK: bool = False  # 是否校验数据库连接

    ENABLE_ENCRYPT: bool = False  # 是否启用响应数据加密

    ENABLE_TOKEN: bool = False  # 是否启动登陆验证

    BATCH_SIZE: int = 10  # 批处理大小,默认 10 (任务中每次处理的记录数,处理一批则暂停检测状态)
    MONGO_BATCH_SIZE: int = 100  # MongoDB 批处理大小,默认 100 (MongoDB 连接相对较慢,适当增加批处理大小)

    TIMEZONE: str = "Asia/Shanghai"  # 默认时区,用于日志时间戳等显示

    # 数据库连接池配置
    DB_POOL_SIZE: int = 10  # 基础连接数默认 10
    DB_MAX_OVERFLOW: int = 20  # 最大溢出连接数默认 20
    DB_POOL_TIMEOUT: int = 30  # 获取连接超时时间默认 30 秒
    DB_POOL_RECYCLE: int = 1800  # 连接回收时间默认半小时
    DB_POOL_PRE_PING: bool = True  # 默认开启预检断连

    class Config:
        env_file = project_rootpath / '.env'
        env_file_encoding = "utf-8"
        extra = "ignore"  # 允许 .env 中有额外的字段不报错

    @property
    def database_url(self) -> str:
        """ 保持统一接口,项目中统一用 settings.database_url
        :return:
        """
        return self.DATABASE_URL


settings = Settings()
