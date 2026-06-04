# -- coding: utf-8 --
# @Author: 胡H
# @File: app/schemas/base.py
# @Created: 2026/2/9 16:05
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 请求体解密基类
from pydantic import BaseModel, model_validator
import json

from app.core.config import settings
from app.utils.encryptDecrypt import decrypt_to_web  # 引入解密工具


class BaseDecryptReq(BaseModel):
    """
    统一解密基类
    所有继承此类的 Request Model，在校验前会自动尝试解密
    """

    @model_validator(mode='before')
    @classmethod
    def decrypt_request_body(cls, values):
        if isinstance(values, dict) and "data" in values:
            payload = values["data"]
        else:
            payload = values  # 兼容没包 data 的老请求

        # 判断是否开启解密
        if not settings.ENABLE_ENCRYPT:
            # 如果关闭加密，前端传的 {"data": {"page_num": 1}}
            # 此时 payload 就是 {"page_num": 1}，直接返回给接口使用
            return payload

        # 如果开启了加密，此时 payload 必须是字符串密文
        if not isinstance(payload, str):
            raise ValueError("系统已开启强制加密，请在 data 字段传入加密后的字符串!")
        # 执行解密
        try:
            # decrypt_to_web 返回的可能是 字典 或 JSON字符串
            decrypted_data = decrypt_to_web(payload)

            # 如果解出来还是字符串 尝试转成 Python 字典
            if isinstance(decrypted_data, str):
                return json.loads(decrypted_data)

            return decrypted_data

        except Exception as e:
            raise ValueError(f"请求参数解密失败: {str(e)}")


"""
使用为让所有需要解密的请求体继承 BaseDecryptReq

"""
