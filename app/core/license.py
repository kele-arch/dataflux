# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/license.py
# @Created: 2025/11/19 10:38
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: 启动许可验证模块（Ed25519 非对称签名版） 读取 license.key 文件并校验签名、机器绑定、有效期

import base64
import json
import subprocess
import uuid
from datetime import date, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from app.core import logger, project_rootpath

#  内嵌公钥 
# 由 script/generate_license.py --gen-keys 生成后复制到此处
# 私钥由开发者自行保管, 此处只存公钥, 泄露也无法伪造许可
_EMBEDDED_PUBLIC_KEY = """
MCowBQYDK2VwAyEAzjAl3tT9MRIA3CPf5BAQE4kAfZP9xtt9RCyY5Kv+Kdw=
"""


def _load_public_key() -> "Ed25519PublicKey | None":
    """从内嵌字符串加载公钥（自动补 PEM 头尾）"""

    try:
        key_text = _EMBEDDED_PUBLIC_KEY.strip()
        if "-----BEGIN PUBLIC KEY-----" not in key_text:
            key_text = "-----BEGIN PUBLIC KEY-----\n" + key_text + "\n-----END PUBLIC KEY-----"
        return serialization.load_pem_public_key(key_text.encode("utf-8"))
    except Exception as e:
        logger.error(f"[许可验证] 公钥加载失败")
        return None


#  机器指纹 
def _get_machine_id() -> str:
    """取主板序列号作为机器指纹；取不到则回退到主 MAC 地址"""
    try:
        output = subprocess.check_output(
            ["wmic", "baseboard", "get", "serialnumber"],
            shell=True, timeout=5,
        ).decode("utf-8", errors="ignore")
        for line in output.splitlines():
            s = line.strip()
            if s and s.lower() != "serialnumber":
                return s
    except Exception:
        pass
    return format(uuid.getnode(), "x")


#  签名校验 
def _verify_signature(public_key: "Ed25519PublicKey", payload_b64: str, sig_b64: str) -> bool:
    """
    校验 Ed25519 签名
    payload_b64: base64url 编码的 canonical JSON 字符串
    sig_b64:     base64url 编码的 64 字节签名
    """
    try:
        canonical = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)).decode("utf-8")
        signature = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        public_key.verify(signature, canonical.encode("utf-8"))
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        logger.error(f"[许可验证] 签名校验异常")
        return False


def check_license(license_path: Path | None = None) -> bool:
    """
    读取 license.key 并验证
    返回 True 表示通过；False 表示未通过（原因打印到日志）

    license.key 格式:
        <base64url(payload_json)>.<base64url(ed25519_signature)>
    """
    if license_path is None:
        license_path = Path(project_rootpath) / "license.key"

    #  文件读取 
    if not license_path.exists():
        logger.warning(f"[许可验证] 未找到 license.key 文件  期望路径: {license_path}")
        return False

    raw = license_path.read_text(encoding="utf-8").strip()
    if not raw:
        logger.warning("[许可验证] license.key 文件为空")
        return False

    #  格式解析：payload_b64 + "." + sig_b64 
    parts = raw.split(".")
    if len(parts) != 2:
        logger.warning("[许可验证] license.key 格式无效（应为 payload.signature）")
        return False

    payload_b64, sig_b64 = parts

    try:
        canonical = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)).decode("utf-8")
        payload: dict = json.loads(canonical)
    except Exception as e:
        logger.error(f"[许可验证] payload 解析失败")
        return False

    #  加载公钥 
    public_key = _load_public_key()
    if public_key is None:
        return False

    #  Ed25519 签名校验 
    if not _verify_signature(public_key, payload_b64, sig_b64):
        logger.warning("[许可验证] 许可签名无效, 文件可能已被篡改或使用了错误的密钥")
        return False

    #  机器绑定校验 
    bound_machine = payload.get("machine_id")
    if bound_machine:
        current_machine = _get_machine_id()
        if bound_machine != current_machine:
            logger.warning(
                f"[许可验证] 许可绑定机器不匹配  "
                f"许可绑定: {bound_machine}  "
                f"当前机器: {current_machine}"
            )
            return False

    #  有效期校验 
    expiry_str = payload.get("expiry")
    xkzWarnin = ""
    if expiry_str and expiry_str != "permanent":
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            today = date.today()
            if today > expiry_date:
                logger.warning(f"[许可验证] 许可已过期 (到期日: {expiry_str})")
                return False
            days_left = (expiry_date - today).days
            if days_left <= 7:
                xkzWarnin = f"[许可验证] 许可即将过期, 剩余 {days_left} 天 (到期日: {expiry_str}), 请尽快续期"
                # logger.warning(
                #
                # )
        except ValueError:
            logger.warning(f"[许可验证] 许可到期日格式错误: {expiry_str}")
            return False

    logger.success("[许可验证] 许可验证通过")
    if xkzWarnin: logger.warning(xkzWarnin)
    return True
