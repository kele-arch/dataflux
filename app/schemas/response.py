# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/response.py
# @Created: 2026/1/18 20:28
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc:
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, model_serializer

from app.core.config import settings
from app.utils.encryptDecrypt import encrypt_to_web

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    code: int = 1
    msg: str = "success"
    # data: Optional[Any] = None
    data: Optional[T] = None

    # 自定义序列化逻辑
    @model_serializer(mode='wrap')
    def encrypt_data_serializer(self, handler) -> dict:
        # 先按正常逻辑序列化成字典 (此时 data 还是明文)
        serialized_data = handler(self)

        # 检查全局配置开关
        # 如果 settings.ENABLE_ENCRYPT 为 False 直接返回明文 不执行加密
        if not settings.ENABLE_ENCRYPT:
            return serialized_data

        # 获取原始 data 数据
        original_data = serialized_data.get('data')

        # 如果 data 存在，且开关开启，则进行加密替换
        if original_data is not None:
            # 调用加密工具
            encrypted_content = encrypt_to_web(original_data)
            serialized_data['data'] = encrypted_content

        return serialized_data
