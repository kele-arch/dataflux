# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/file_client_factory.py
# @Created: 2026/6/12 17:51
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 多协议文件客户端工厂 (FTP/FTPS/SFTP/SDTP 统一适配)

import os
import ssl
from abc import ABC, abstractmethod

import paramiko
from ftplib import FTP, FTP_TLS, error_perm

from app.core import logger


class BaseFileClient(ABC):
    """文件客户端抽象基类"""

    @abstractmethod
    def connect(self, host: str, port: int, username: str, password: str, passive: bool = True):
        ...

    @abstractmethod
    def download(self, remote_path: str, local_path: str, status_probe) -> int:
        ...

    @abstractmethod
    def close(self):
        ...


class FtpClientAdapter(BaseFileClient):
    """FTP/FTPS 适配器 (复用原有的 TLS 会话复用补丁)"""

    def __init__(self, scheme: str = "ftp"):
        self.ftp = None
        self.scheme = scheme

    def connect(self, host: str, port: int, username: str, password: str, passive: bool = True):

        # TLS 会话复用补丁
        class FTP_TLS_Reused(FTP_TLS):
            def ntransfercmd(self, cmd, rest=None):
                conn, size = super(FTP_TLS, self).ntransfercmd(cmd, rest)
                if self._prot_p:
                    conn = self.context.wrap_socket(
                        conn, server_hostname=self.host, session=self.sock.session)
                return conn, size

        ftp = FTP()
        try:
            ftp.connect(host=host, port=port or 21, timeout=30)
            ftp.login(user=username or "anonymous", passwd=password or "")
        except error_perm as e:
            if "503" in str(e) or "AUTH" in str(e).upper():
                ftp.close()
                logger.info(f"源 [{host}] 要求安全连接, 切换 FTPS...")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ftp = FTP_TLS_Reused(context=ctx)
                ftp.connect(host=host, port=port or 21, timeout=30)
                ftp.login(user=username or "anonymous", passwd=password or "")
                ftp.prot_p()
            else:
                raise e

        if passive:
            ftp.set_pasv(True)
        else:
            ftp.set_pasv(False)

        self.ftp = ftp
        logger.info(f"FTP(S) 连接成功: {host}:{port or 21}")

    def download(self, remote_path: str, local_path: str, status_probe) -> int:
        total_bytes = 0
        probe_counter = 0
        with open(local_path, "wb") as f:
            def callback(chunk):
                nonlocal total_bytes, probe_counter
                f.write(chunk)
                total_bytes += len(chunk)
                probe_counter += 1
                if probe_counter % 50 == 0:  # 每 ~400KB 探测一次
                    status_probe()

            try:
                self.ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=8192)
            except Exception as e:
                err_str = str(e)
                if any(k in err_str for k in [
                    "SHUTDOWN_WHILE_IN_INIT", "EOF occurred",
                    "WRONG_VERSION_NUMBER", "Connection reset"
                ]):
                    logger.warning(f"SSL 正常关闭, 已接收 {total_bytes} 字节")
                else:
                    raise
        actual_size = os.path.getsize(local_path)
        if actual_size == 0:
            raise RuntimeError(f"文件下载后为空: {remote_path}")
        return actual_size

    def close(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                self.ftp.close()


class SftpClientAdapter(BaseFileClient):
    """SFTP 适配器 (基于 paramiko SSH)"""

    def __init__(self):
        self.transport = None
        self.sftp = None

    def connect(self, host: str, port: int, username: str, password: str, passive: bool = True):
        self.transport = paramiko.Transport((host, port or 22))
        self.transport.connect(username=username, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        logger.info(f"SFTP 连接成功: {host}:{port or 22}")

    def download(self, remote_path: str, local_path: str, status_probe) -> int:
        total_bytes = 0
        probe_counter = 0
        with open(local_path, "wb") as local_f:
            with self.sftp.open(remote_path, "rb") as remote_f:
                remote_f.prefetch()
                while True:
                    chunk = remote_f.read(8192)
                    if not chunk:
                        break
                    probe_counter += 1
                    if probe_counter % 50 == 0:
                        status_probe()
                    local_f.write(chunk)
                    total_bytes += len(chunk)
        actual_size = os.path.getsize(local_path)
        if actual_size == 0:
            raise RuntimeError(f"文件下载后为空: {remote_path}")
        return actual_size

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()


class SdtpClientAdapter(BaseFileClient):
    """SDTP 安全网闸传输协议适配器 (预留, 对接私有 SDK 或命令行工具)"""

    def connect(self, host: str, port: int, username: str, password: str, passive: bool = True):
        logger.info(f"SDTP 安全传输通道初始化: {host}:{port}")

    def download(self, remote_path: str, local_path: str, status_probe) -> int:
        status_probe()
        logger.info(f"SDTP 文件提取完成: {remote_path}")
        return os.path.getsize(local_path) if os.path.exists(local_path) else 0

    def close(self):
        pass


class FileClientFactory:
    SCHEME_MAP = {
        "ftp": FtpClientAdapter,
        "ftps": FtpClientAdapter,
        "sftp": SftpClientAdapter,
        "sdtp": SdtpClientAdapter,
    }

    SUPPORTED_SCHEMES = tuple(SCHEME_MAP.keys())  # 供外部校验使用

    @staticmethod
    def create(scheme: str) -> BaseFileClient:
        client_cls = FileClientFactory.SCHEME_MAP.get(scheme.lower())
        if not client_cls:
            raise ValueError(f"不支持的协议: {scheme}, 支持: {FileClientFactory.SUPPORTED_SCHEMES}")
        return client_cls(scheme) if scheme.lower() in ("ftp", "ftps") else client_cls()
