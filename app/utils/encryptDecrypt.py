# -- coding: utf-8 --
# @Author: 胡H
# @File: app/utils/encryptDecrypt.py
# @Created: 2026/3/2 14:57
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 封装好的简单 AES加密解密工具 适用于前后端数据传输加密
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import json
from datetime import datetime, date

server_key = b'-=ujnk2kl38jhk-='  # 示例密钥（必须为16字节）
web_key = b'-=asdj2kl3-=srrf'


class DateEncoder(json.JSONEncoder):
    """ 通用的日期时间JSON编码器 """

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super(DateEncoder, self).default(obj)


def encrypt_to_web(data):
    """
    通用加密函数：支持 str, dict, list, int 等任意类型
    """
    # 判断类型，自动序列化
    if isinstance(data, str):
        # 如果本来就是字符串，直接用
        plain_text = data
    else:
        # 如果是 字典、列表、数字等，先转成 JSON 字符串
        # ensure_ascii=False: 保证中文不乱码
        # cls=DateEncoder: 自动处理时间字段
        plain_text = json.dumps(data, cls=DateEncoder, ensure_ascii=False)

    # 加密过程 (AES需要bytes类型)
    cipher = AES.new(server_key, AES.MODE_CBC, server_key)

    # 此时 plain_text 绝对是字符串，.encode('utf-8') 安全
    encrypted_bytes = cipher.encrypt(pad(plain_text.encode('utf-8'), AES.block_size))

    # 转 Base64 返回
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def decrypt_to_web(base64_encrypted_text: str) -> str:
    # return base64_encrypted_text
    print("入参：", datetime.now())
    print(base64_encrypted_text)
    # 将 Base64 编码的密文解码为原始字节数据
    encrypted_data = base64.b64decode(base64_encrypted_text)

    # 创建 AES 解密器
    cipher = AES.new(web_key, AES.MODE_CBC, web_key)

    # 解密并去除填充
    decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    return json.loads(decrypted_data.decode('utf-8'))
