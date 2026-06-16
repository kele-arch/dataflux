# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/ftp_explorer.py
# @Created: 2026/6/17
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: FTP/SFTP/FTPS 目录结构勘探：支持逐级懒加载与限深递归，树形结构返回

import stat
import ssl
from ftplib import FTP, FTP_TLS, error_perm
from typing import List, Dict, Any

import paramiko

from app.core import logger


class FtpExplorer:
    """
    FTP / FTPS / SFTP 远程文件目录树形结构勘探器
    所有同步 I/O 操作均通过 asyncio.to_thread 包裹，绝不阻塞主事件循环
    """

    def __init__(self, host: str, port: int, username: str, password: str,
                 protocol: str = "ftp", passive: bool = True, timeout: int = 15):
        self.host = host
        self.port = port
        self.username = username or "anonymous"
        self.password = password or ""
        self.protocol = protocol.lower()  # "ftp" | "ftps" | "sftp"
        self.passive = passive
        self.timeout = timeout

    def get_dir_tree(
            self,
            remote_path: str = "/",
            recursive: bool = False,
            max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        获取目录树（在 asyncio.to_thread 中执行）
        :param remote_path: 起始勘探路径
        :param recursive:   是否递归向下探测
        :param max_depth:   递归最大深度，防止海量文件撑爆内存
        """
        if not remote_path:
            remote_path = "/"

        if self.protocol == "sftp":
            return self._explore_sftp(remote_path, recursive, max_depth, current_depth=1)
        else:
            return self._explore_ftp(remote_path, recursive, max_depth, current_depth=1)

    #  FTP / FTPS 实现

    def _connect_ftp(self) -> FTP:
        """ 连接 FTP / FTPS，自动检测 TLS 加密 """
        ftp = FTP()
        try:
            ftp.connect(host=self.host, port=self.port or 21, timeout=self.timeout)
            ftp.login(user=self.username, passwd=self.password)
        except error_perm as e:
            if "503" in str(e) or "AUTH" in str(e).upper():
                # 服务器要求安全连接，自动切换 FTPS
                ftp.close()
                logger.info(f"FTP 源 [{self.host}] 要求安全连接，切换 FTPS")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                # TLS 会话复用补丁
                class FTP_TLS_Reused(FTP_TLS):
                    def ntransfercmd(self, cmd, rest=None):
                        conn, size = super(FTP_TLS, self).ntransfercmd(cmd, rest)
                        if self._prot_p:
                            conn = self.context.wrap_socket(
                                conn, server_hostname=self.host, session=self.sock.session)
                        return conn, size

                ftp = FTP_TLS_Reused(context=ctx)
                ftp.connect(host=self.host, port=self.port or 21, timeout=self.timeout)
                ftp.login(user=self.username, passwd=self.password)
                ftp.prot_p()
            else:
                raise

        if self.passive:
            ftp.set_pasv(True)
        else:
            ftp.set_pasv(False)

        return ftp

    def _explore_ftp(self, path: str, recursive: bool, max_depth: int,
                     current_depth: int) -> List[Dict[str, Any]]:
        nodes = []
        ftp = None
        try:
            ftp = self._connect_ftp()
            ftp.cwd(path)

            lines = []
            ftp.dir(lines.append)

            for line in lines:
                parts = line.split(None, 8)
                if len(parts) < 9:
                    continue

                info = parts[0]
                name = parts[8]
                if name in (".", ".."):
                    continue

                is_dir = info.startswith("d")
                full_path = f"{path.rstrip('/')}/{name}"

                node = {
                    "title": name,
                    "key": full_path,
                    "is_dir": is_dir,
                    "isLeaf": not is_dir,
                    "children": [] if is_dir else None,
                }

                if is_dir and recursive and current_depth < max_depth:
                    try:
                        node["children"] = self._explore_ftp(
                            full_path, recursive, max_depth, current_depth + 1
                        )
                    except Exception as e:
                        logger.warning(f"FTP 递归扫描子目录失败 [{full_path}]: {e}")
                        node["children"] = []

                nodes.append(node)

        except Exception as e:
            logger.error(f"FTP 目录勘探失败 [host={self.host}, path={path}]: {e}")
            raise RuntimeError(f"FTP 连接或读取失败: {e}")
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass

        # 排序：目录在前，文件在后；同类按名称字母序
        nodes.sort(key=lambda n: (not n["is_dir"], n["title"].lower()))
        return nodes

    #  SFTP 实现 (paramiko)
    def _explore_sftp(self, path: str, recursive: bool, max_depth: int,
                      current_depth: int) -> List[Dict[str, Any]]:
        nodes = []
        transport = None
        try:
            transport = paramiko.Transport((self.host, self.port or 22))
            transport.connect(username=self.username, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)

            for attr in sftp.listdir_attr(path):
                name = attr.filename
                if name in (".", ".."):
                    continue

                is_dir = stat.S_ISDIR(attr.st_mode)
                full_path = f"{path.rstrip('/')}/{name}"

                node = {
                    "title": name,
                    "key": full_path,
                    "is_dir": is_dir,
                    "isLeaf": not is_dir,
                    "children": [] if is_dir else None,
                }

                if is_dir and recursive and current_depth < max_depth:
                    try:
                        node["children"] = self._explore_sftp(
                            full_path, recursive, max_depth, current_depth + 1
                        )
                    except Exception as e:
                        logger.warning(f"SFTP 递归扫描子目录失败 [{full_path}]: {e}")
                        node["children"] = []

                nodes.append(node)

            sftp.close()
        except Exception as e:
            logger.error(f"SFTP 目录勘探失败 [host={self.host}, path={path}]: {e}")
            raise RuntimeError(f"SFTP 连接或读取失败: {e}")
        finally:
            if transport:
                transport.close()

        # 排序：目录在前，文件在后
        nodes.sort(key=lambda n: (not n["is_dir"], n["title"].lower()))
        return nodes
