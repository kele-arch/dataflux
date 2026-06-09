# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/ftp_sync_engine.py
# @Created: 2026/6/9 10:51
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: FTP 文件采集: 支持文件下载、MD5去重、结构化文件解析入库

import csv
import hashlib
import json
import os
import ssl
import time
import uuid
from datetime import datetime
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import Table, Column, Text, MetaData, String, JSON, inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import logger, project_rootpath
from app.core.config import settings
from app.db.session import engine as global_target_engine, SessionLocal
from app.models.taskLogModel import FtpFileRecord
from app.schemas.tsync import DBSyncReq
from app.services.task_control import get_task_status, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException


class FtpSyncEngine:
    """
    FTP 文件采集
      - 单文件下载 + MD5 去重
      - 结构化文件解析入库（CSV / JSON / YAML）
      - 二进制/任意文件仅存储本地 + 记录元数据
    """

    DEFAULT_SAVE_DIR = Path(project_rootpath, settings.FTP_LOCAL_SAVE_DIR)
    DEFAULT_SAVE_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = getattr(settings, "BATCH_SIZE", 1000)

        # 如果传了完整 FTP URL, 自动解析覆盖各字段
        if getattr(self.req, "ftp_url", None):
            self._parse_ftp_url(self.req.ftp_url)

    def _parse_ftp_url(self, ftp_url: str):
        """
        解析标准 FTP URL, 覆盖 req 里的连接字段
        支持: ftp://user:pass@host:port/path
              ftp://user@host/path
              ftp://host/path
              ftps://...
        """
        from urllib.parse import urlparse, unquote

        parsed = urlparse(ftp_url)

        if parsed.scheme.lower() not in ("ftp", "ftps"):
            raise ValueError(f"不支持的协议: {parsed.scheme}, 仅支持 ftp:// 或 ftps://")

        if parsed.hostname:
            self.req.host = parsed.hostname
        if parsed.port:
            self.req.port = parsed.port
        if parsed.username:
            self.req.username = unquote(parsed.username)
        if parsed.password:
            self.req.password = unquote(parsed.password)
        if parsed.path:
            self.req.ftp_path = parsed.path

        logger.info(
            f"FTP URL 解析完成: host={self.req.host}, port={self.req.port or 21}, user={self.req.username}, path={self.req.ftp_path}")

    #  FTP 连接

    def _connect(self) -> FTP:
        """
        建立 FTP 连接, 支持主动/被动模式及自动识别 FTPS 加密 (带 TLS 会话复用补丁)
        """

        # 修复 Python 标准库与 FileZilla 等服务端的 TLS 会话复用不兼容 Bug
        class FTP_TLS_Reused(FTP_TLS):
            def ntransfercmd(self, cmd, rest=None):
                # 用 super(FTP_TLS, self) 而不是 FTP.ntransfercmd(self, ...)
                conn, size = super(FTP_TLS, self).ntransfercmd(cmd, rest)
                if self._prot_p:
                    conn = self.context.wrap_socket(
                        conn,
                        server_hostname=self.host,
                        session=self.sock.session
                    )
                return conn, size

        ftp = FTP()
        try:
            ftp.connect(host=self.req.host, port=self.req.port or 21, timeout=30)
            ftp.login(
                user=self.req.username or "anonymous",
                passwd=self.req.password or ""
            )
        except error_perm as e:
            if "503" in str(e) or "AUTH" in str(e).upper():
                ftp.close()
                logger.info(f"源 FTP [{self.req.host}] 要求安全连接, 正在切换至 FTPS (带会话复用补丁)...")

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                # 使用打过补丁的类建立连接
                ftp = FTP_TLS_Reused(context=ctx)
                ftp.connect(host=self.req.host, port=self.req.port or 21, timeout=30)
                ftp.login(
                    user=self.req.username or "anonymous",
                    passwd=self.req.password or ""
                )
                ftp.prot_p()  # 必须调用：保护数据连接
            else:
                raise e

        # 设置被动/主动模式 (转为 int 判断, 兼容 PostgreSQL 的设定)
        if getattr(self.req, "ftp_passive", 1) == 1:
            ftp.set_pasv(True)
        else:
            ftp.set_pasv(False)

        logger.info(f"FTP(S) 连接成功: {self.req.host}:{self.req.port or 21}")
        return ftp

    #  MD5 计算

    def _compute_md5(self, filepath: str) -> str:
        """ 流式计算本地文件 MD5, 支持大文件 """
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    #  文件下载

    def _build_local_path(self, remote_path: str) -> str:
        """
        根据远程路径生成本地存储路径
        规则: {save_dir}/{task_id}/{文件名}
        """
        save_dir = getattr(self.req, "local_save_dir", None) or self.DEFAULT_SAVE_DIR
        task_dir = os.path.join(save_dir, str(self.req.task_id))
        Path(task_dir).mkdir(parents=True, exist_ok=True)

        file_name = os.path.basename(remote_path)
        return os.path.join(task_dir, file_name)

    def _download_file(self, ftp, remote_path: str, local_path: str) -> int:
        """

        """
        total_bytes = 0
        with open(local_path, "wb") as f:
            def callback(chunk):
                nonlocal total_bytes
                f.write(chunk)
                total_bytes += len(chunk)

            try:
                ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=8192)
            except Exception as e:
                err_str = str(e)
                if any(k in err_str for k in [
                    "SHUTDOWN_WHILE_IN_INIT", "EOF occurred",
                    "WRONG_VERSION_NUMBER", "Connection reset"
                ]):
                    logger.warning(f"SSL 数据连接正常关闭, 已接收 {total_bytes} 字节")
                else:
                    raise

        actual_size = os.path.getsize(local_path)
        if actual_size == 0:
            raise RuntimeError(f"文件下载后为空: {remote_path}, 请检查路径或权限")

        logger.info(f"下载完成: {remote_path} -> {local_path} ({actual_size} bytes)")
        return actual_size

    #  JSONB 序列化清洗

    def _sanitize_for_jsonb(self, obj):
        """ 递归清洗对象, 确保所有值都能被 JSON 接受 """
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return str(obj)

    #  文件类型识别

    def _detect_file_type(self, file_name: str) -> str:
        """
        根据文件扩展名识别类型
        auto 模式下自动判断
        """
        file_type = getattr(self.req, "file_type", "auto") or "auto"
        if file_type != "auto":
            return file_type.lower()

        ext = Path(file_name).suffix.lower().lstrip(".")
        type_map = {
            "csv": "csv",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
        }
        return type_map.get(ext, "binary")

    #  结构化文件解析入库

    def _prepare_parse_target_table(self, table_name: str) -> Table:
        """
        为结构化文件内容准备目标表
        统一用两列结构: id(UUID PK) + raw_doc(JSON)
        如果表已存在则跳过建表
        """
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("id", String(32), primary_key=True),
            Column("raw_doc", JSON, nullable=False),
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"解析目标表 [{table_name}] 已就绪")
        return table

    def _parse_csv(self, local_path: str) -> list:
        """
        解析 CSV 文件, 每行转为 dict
        自动处理 UTF-8 / GBK 编码
        """
        rows = []
        encodings = ["utf-8-sig", "gbk", "utf-8"]
        for encoding in encodings:
            try:
                with open(local_path, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rows.append(dict(row))
                logger.info(f"CSV 解析成功, 编码: {encoding}, 共 {len(rows)} 行")
                return rows
            except UnicodeDecodeError:
                continue
        raise ValueError(f"CSV 文件编码识别失败, 尝试了: {encodings}")

    def _parse_json(self, local_path: str) -> list:
        """
        解析 JSON 文件
        支持顶层数组 [...] 和单个对象 {...}
        """
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = [data]
        else:
            raise ValueError(f"不支持的 JSON 顶层结构: {type(data)}")

        logger.info(f"JSON 解析成功, 共 {len(rows)} 条")
        return rows

    def _parse_yaml(self, local_path: str) -> list:
        """
        解析 YAML 文件（支持多文档 YAML, 即 --- 分隔）
        """
        rows = []
        with open(local_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        for doc in docs:
            if doc is None:
                continue
            if isinstance(doc, list):
                rows.extend(doc)
            elif isinstance(doc, dict):
                rows.append(doc)
            else:
                rows.append({"value": str(doc)})

        logger.info(f"YAML 解析成功, 共 {len(rows)} 条")
        return rows

    def _ingest_rows(self, rows: list, target_table_name: str) -> int:
        """
        将解析出的行列表批量写入目标表
        每行存为一个 JSON raw_doc
        """
        if not rows:
            return 0

        target_table = self._prepare_parse_target_table(target_table_name)
        total_inserted = 0

        with self.target_engine.begin() as conn:
            for i in range(0, len(rows), self.batch_size):
                # 探测暂停/取消信号
                self._check_task_status()

                batch = rows[i: i + self.batch_size]
                batch_data = [{"id": uuid.uuid4().hex, "raw_doc": row} for row in batch]

                stmt = pg_insert(target_table).values(batch_data)
                conn.execute(stmt)
                total_inserted += len(batch)

        return total_inserted

    def _parse_and_ingest(self, local_path: str, file_type: str) -> int:
        """
        解析结构化文件并写入目标表
        """
        target_table_name = getattr(self.req, "target_table", None)
        if not target_table_name:
            file_stem = Path(local_path).stem  # 文件名去掉扩展名
            target_table_name = f"ftp_{file_stem}"
            logger.info(f"未指定 target_table, 自动使用表名: {target_table_name}")

        logger.info(f"开始解析文件: {local_path}, 类型: {file_type}, 目标表: {target_table_name}")
        target_table = self._prepare_parse_target_table(target_table_name)
        total_inserted = 0

        # 流式处理 CSV (防 OOM
        if file_type == "csv":
            encodings = ["utf-8-sig", "gbk", "utf-8"]
            for encoding in encodings:
                try:
                    with open(local_path, "r", encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        batch_data = []
                        with self.target_engine.begin() as conn:
                            for row in reader:
                                batch_data.append(
                                    {"id": uuid.uuid4().hex, "raw_doc": self._sanitize_for_jsonb(dict(row))})
                                # 满一批次落盘并清空内存
                                if len(batch_data) >= self.batch_size:
                                    self._check_task_status()
                                    conn.execute(pg_insert(target_table).values(batch_data))
                                    total_inserted += len(batch_data)
                                    batch_data.clear()
                            # 尾部处理
                            if batch_data:
                                conn.execute(pg_insert(target_table).values(batch_data))
                                total_inserted += len(batch_data)
                    logger.info(f"CSV 流式解析入库成功, 编码: {encoding}, 共 {total_inserted} 行")
                    return total_inserted
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"CSV 文件编码识别失败, 尝试了: {encodings}")

        # 处理 JSON
        elif file_type == "json":
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else [data]
            total_inserted = self._ingest_memory_rows(rows, target_table)
            logger.info(f"JSON 解析成功, 共 {total_inserted} 条")
            return total_inserted

        # 处理 YAML
        elif file_type == "yaml":
            rows = []
            with open(local_path, "r", encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if doc is None: continue
                if isinstance(doc, list):
                    rows.extend(doc)
                elif isinstance(doc, dict):
                    rows.append(doc)
                else:
                    rows.append({"value": str(doc)})
            total_inserted = self._ingest_memory_rows(rows, target_table)
            logger.info(f"YAML 解析成功, 共 {total_inserted} 条")
            return total_inserted

        else:
            logger.info(f"文件类型 [{file_type}] 不支持解析, 仅存储文件本身")
            return 0

    def _ingest_memory_rows(self, rows: list, target_table: Table) -> int:
        """ 辅助方法：将内存中的 list (JSON/YAML) 分批写入 """
        if not rows: return 0
        total = 0
        with self.target_engine.begin() as conn:
            for i in range(0, len(rows), self.batch_size):
                self._check_task_status()
                batch = [{"id": uuid.uuid4().hex, "raw_doc": self._sanitize_for_jsonb(row)} for row in
                         rows[i: i + self.batch_size]]
                conn.execute(pg_insert(target_table).values(batch))
                total += len(batch)
        return total

    #  数据库记录管理

    def _get_file_record(self, db, task_id: str, remote_path: str) -> Optional[FtpFileRecord]:
        """ 查询历史下载记录 """
        return db.query(FtpFileRecord).filter(
            FtpFileRecord.task_id == task_id,
            FtpFileRecord.remote_path == remote_path
        ).first()

    def _save_file_record(self, db, record_data: dict):
        """ 新增或更新文件记录 """
        existing = self._get_file_record(
            db, record_data["task_id"], record_data["remote_path"]
        )
        if existing:
            for k, v in record_data.items():
                setattr(existing, k, v)
            existing.update_time = datetime.now()
        else:
            record = FtpFileRecord(**record_data, downloaded_at=datetime.now())
            db.add(record)
        db.commit()

    #  状态探测

    def _check_task_status(self):
        task_id = str(self.req.task_id)
        status = get_task_status(task_id)
        if status == TASK_PAUSED:
            raise TaskPausedException("FTP 任务已暂停")
        if status == TASK_CANCELLED:
            raise TaskCancelledException("FTP 任务已取消")

    #  对外入口

    def main(self) -> dict:
        remote_path = getattr(self.req, "ftp_path", None) or self.req.db_name
        if not remote_path:
            raise ValueError("FTP 采集必须指定 ftp_path（远程文件路径）")

        file_name = os.path.basename(remote_path)
        local_path = self._build_local_path(remote_path)
        file_type = self._detect_file_type(file_name)
        task_id = str(self.req.task_id)

        logger.info(f"启动 FTP 采集, 源: ftp://{self.req.host}{remote_path}")

        db = SessionLocal()
        ftp = None
        start_time = time.time()

        try:
            # 查历史记录
            existing_record = self._get_file_record(db, task_id, remote_path)

            # 连接 FTP
            # ftp, is_ftps = self._connect()
            ftp = self._connect()

            # 下载文件
            self._check_task_status()
            file_size = self._download_file(ftp, remote_path, local_path)

            # 计算 MD5
            new_md5 = self._compute_md5(local_path)
            logger.info(f"文件 MD5: {new_md5}")

            # MD5 去重判断
            if existing_record and existing_record.md5 == new_md5:
                logger.info(f"文件未变更（MD5 相同）, 跳过处理: {remote_path}")
                return {
                    "status": "skipped",
                    "message": "文件 MD5 未变更, 跳过",
                    "tables_synced": 0,
                    "total_records": 0,
                    "new_watermark": new_md5,
                    "table_details": []
                }

            # 更新文件记录
            self._save_file_record(db, {
                "task_id": task_id,
                "remote_path": remote_path,
                "local_path": local_path,
                "file_name": file_name,
                "file_size": file_size,
                "md5": new_md5,
                "file_type": file_type,
                "is_parsed": 0,
                "parsed_rows": 0,
            })

            # 结构化文件解析入库
            parsed_rows = 0
            file_parse = getattr(self.req, "file_parse", False)

            if file_parse and file_type != "binary":
                self._check_task_status()
                parsed_rows = self._parse_and_ingest(local_path, file_type)

                # 更新解析状态
                self._save_file_record(db, {
                    "task_id": task_id,
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "file_name": file_name,
                    "file_size": file_size,
                    "md5": new_md5,
                    "file_type": file_type,
                    "is_parsed": 1,
                    "parsed_rows": parsed_rows,
                })

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"FTP 采集完成, 耗时 {elapsed}s, 解析行数: {parsed_rows}")

            return {
                "status": "success",
                "tables_synced": 1 if parsed_rows > 0 else 0,
                "total_records": parsed_rows,
                "new_watermark": new_md5,  # 用 MD5 作为水位线
                "table_details": [{
                    "name": file_name,
                    "target_name": getattr(self.req, "target_table", None) or f"ftp_{Path(local_path).stem}",
                    "records": parsed_rows,
                    "cost_seconds": elapsed,
                    "high_watermark": new_md5
                }]
            }

        except (TaskPausedException, TaskCancelledException):
            raise

        except error_perm as e:
            logger.error(f"FTP 权限错误: {e}")
            raise RuntimeError(f"FTP 访问失败: {e}")

        except Exception as e:
            logger.error(f"FTP 采集异常: {e}")
            raise

        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
                logger.info("FTP 连接已关闭")
            db.close()
