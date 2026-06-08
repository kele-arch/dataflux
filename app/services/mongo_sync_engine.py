# -- coding: utf-8 --
# @Author: 胡H
# @File: pp/services/mongo_sync_engine.py
# @Created: 2026/6/8 9:56
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: MongoDB 数据抽取引擎实现

import time
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient, ASCENDING
from urllib.parse import quote_plus
from dateutil.parser import parse as parse_dt

from app.core import logger
from app.core.config import settings
from app.db.session import engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.task_control import get_task_status, save_watermark, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException

from sqlalchemy import Table, Column, Text, MetaData
from sqlalchemy.dialects.postgresql import insert as pg_insert, JSON


class MongoSyncEngine:
    """ MongoDB 数据抽取引擎
    文档序列化为原生 json 存入目标库 (保留原始写入格式和键顺序)
    目标表结构固定为两列: _id (TEXT), raw_doc (JSON)
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.batch_size = settings.MONGO_BATCH_SIZE  # MongoDB 文档通常比关系型行更大, 批次适当调小
        self.client = None

    def _build_mongo_url(self) -> str:
        """
        构建 MongoDB 连接 URL
        """
        safe_password = quote_plus(self.req.password)
        if self.req.username:
            return f"mongodb://{self.req.username}:{safe_password}@{self.req.host}:{self.req.port}/{self.req.db_name}?authSource=admin"
        return f"mongodb://{self.req.host}:{self.req.port}/{self.req.db_name}"

    def _get_client(self) -> MongoClient:
        """
        获取 MongoDB 客户端实例,使用连接池管理连接
         - 连接池参数: maxPoolSize=100, minPoolSize=0, maxIdleTimeMS=300000 (5分钟)
        """
        if not self.client:
            self.client = MongoClient(
                self._build_mongo_url(),
                serverSelectionTimeoutMS=10000,  # 10秒连接超时
                connectTimeoutMS=10000
            )
        return self.client

    #  序列化

    def _serialize_doc(self, doc: dict) -> dict:
        """
        递归序列化 MongoDB 文档中的特殊类型: 
        - ObjectId  -> str
        - datetime  -> ISO 8601 字符串
        - bytes     -> hex 字符串
        """
        result = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, bytes):
                result[k] = v.hex()
            elif isinstance(v, dict):
                result[k] = self._serialize_doc(v)  # 递归处理嵌套文档
            elif isinstance(v, list):
                result[k] = self._serialize_list(v)  # 递归处理数组
            else:
                result[k] = v
        return result

    def _serialize_list(self, lst: list) -> list:
        """ 递归序列化数组中的特殊类型 """
        result = []
        for item in lst:
            if isinstance(item, ObjectId):
                result.append(str(item))
            elif isinstance(item, datetime):
                result.append(item.isoformat())
            elif isinstance(item, dict):
                result.append(self._serialize_doc(item))
            elif isinstance(item, list):
                result.append(self._serialize_list(item))
            else:
                result.append(item)
        return result

    def _build_query_filter(self) -> dict:
        """
        根据采集模式生成 MongoDB filter
        """
        mode = self.req.collect_mode

        if mode == "full":
            logger.info("MongoDB 采用 [全量] 模式")
            return {}

        if mode == "inc_id" and self.req.last_watermark:
            try:
                last_oid = ObjectId(self.req.last_watermark)
                logger.info(f"MongoDB 采用 [_id 增量] 模式, 水位线: {self.req.last_watermark}")
                return {"_id": {"$gt": last_oid}}
            except InvalidId:
                logger.warning(f"last_watermark [{self.req.last_watermark}] 不是合法 ObjectId, 回退全量")
                return {}

        if mode == "inc_time" and self.req.incremental_column and self.req.last_watermark:
            try:
                watermark_val = parse_dt(self.req.last_watermark)
                logger.info(
                    f"MongoDB 采用 [时间戳增量] 模式, 字段: {self.req.incremental_column}, 水位线(datetime): {watermark_val}")
            except (ValueError, TypeError):
                # 解析失败说明不是时间字符串, 用原始字符串（比如数字字符串）
                watermark_val = self.req.last_watermark
                logger.warning(f"水位线无法解析为 datetime, 使用原始值: {watermark_val}")

            return {self.req.incremental_column: {"$gt": watermark_val}}

        # 兜底全量
        logger.warning("增量条件不完整, 回退全量模式")
        return {}

    def _resolve_target_name(self, source_name: str) -> str:
        """ 根据 table_mapping 将源集合名映射为目标表名, 无映射则同名 """
        mapping = self.req.table_mapping or {}
        return mapping.get(source_name, source_name)

    def _prepare_target_table(self, collection_name: str) -> Table:
        """
        在 PG 中为每个 Collection 准备一张固定结构的目标表:
            _id     TEXT PRIMARY KEY
            raw_doc JSON
        如果表已存在则跳过
        """
        target_table_name = self._resolve_target_name(collection_name)

        metadata = MetaData()
        table = Table(
            target_table_name,
            metadata,
            Column("_id", Text, primary_key=True),
            Column("raw_doc", JSON, nullable=False),  # 已替换为原生 JSON
        )
        metadata.create_all(bind=self.target_engine, checkfirst=True)
        logger.info(f"目标表 [{target_table_name}] 已就绪（_id TEXT PK + raw_doc JSON）")
        return table

    #  状态探测
    def _check_task_status(self, current_watermark=None):
        """
        在迁移过程中定期检查任务状态, 支持暂停和取消功能
         - 暂停: 保存当前水位线, 抛出 TaskPausedException
         - 取消: 抛出 TaskCancelledException
         - 正常: 继续迁移
         - 注意: 频率不宜过高, 避免对性能造成过大影响
         - current_watermark: 当前迁移进度的水位线, 用于暂停时保存断点
        """
        task_id = str(self.req.task_id)
        status = get_task_status(task_id)

        if status == TASK_PAUSED:
            save_watermark(task_id, current_watermark)
            logger.warning(f"任务 [{task_id}] 暂停, 断点水位线: {current_watermark}")
            raise TaskPausedException(f"任务已暂停, 水位线: {current_watermark}")

        if status == TASK_CANCELLED:
            logger.warning(f"任务 [{task_id}] 取消")
            raise TaskCancelledException("任务已被用户取消")

    def _migrate_collection(self, collection_name: str) -> dict:
        """
        迁移单个 Collection -> PG 目标表
        返回该集合的迁移统计
        """
        logger.info(f"开始迁移 Collection: [{collection_name}]")
        start_time = time.time()

        db_source = self._get_client()[self.req.db_name]
        collection = db_source[collection_name]

        query_filter = self._build_query_filter()
        # _id 升序排列, 保证增量水位线单调递增
        cursor = collection.find(query_filter).sort("_id", ASCENDING).batch_size(self.batch_size)

        target_table = self._prepare_target_table(collection_name)

        batch_data = []
        inserted_count = 0
        current_max_watermark = None

        with self.target_engine.begin() as t_conn:
            for doc in cursor:
                # 序列化整个文档
                serialized = self._serialize_doc(doc)

                # _id 单独提出来作为主键列, raw_doc 存完整文档
                row = {
                    "_id": serialized.pop("_id"),  # pop 出来, raw_doc 里不重复存
                    "raw_doc": serialized
                }
                batch_data.append(row)

                # 追踪水位线
                if self.req.collect_mode == "inc_id":
                    current_max_watermark = row["_id"]
                elif self.req.collect_mode == "inc_time" and self.req.incremental_column:
                    val = serialized.get(self.req.incremental_column)
                    if val and (current_max_watermark is None or val > current_max_watermark):
                        current_max_watermark = val

                # 攒批写入
                if len(batch_data) >= self.batch_size:
                    self._upsert_batch(t_conn, target_table, batch_data)
                    inserted_count += len(batch_data)
                    batch_data.clear()

                    # 批次边界探测暂停/取消信号
                    self._check_task_status(current_max_watermark)

            # 尾部处理
            if batch_data:
                self._upsert_batch(t_conn, target_table, batch_data)
                inserted_count += len(batch_data)

        elapsed = time.time() - start_time
        target_name = self._resolve_target_name(collection_name)
        logger.info(
            f"Collection [{collection_name}] -> [{target_name}] 完成, 迁移 {inserted_count} 条, 耗时 {elapsed:.2f}s")

        return {
            "name": collection_name,
            "target_name": target_name,
            "records": inserted_count,
            "high_watermark": str(current_max_watermark) if current_max_watermark else None
        }

    def _upsert_batch(self, conn, table: Table, batch_data: list):
        """
        PG upsert: _id 冲突时更新 raw_doc
        """
        stmt = pg_insert(table).values(batch_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["_id"],
            set_={"raw_doc": stmt.excluded.raw_doc}
        )
        conn.execute(stmt)

    #  获取待迁移的 Collection 列表

    def _get_collections(self) -> list:
        """
        如果 req.sync_tables 指定了集合名, 就只迁移这些；
        否则列出整个库的所有集合（排除系统集合）
        """
        if self.req.sync_tables:
            logger.info(f"指定集合模式: {self.req.sync_tables}")
            return self.req.sync_tables

        db_source = self._get_client()[self.req.db_name]
        all_collections = db_source.list_collection_names()
        # 过滤掉 MongoDB 系统集合
        user_collections = [c for c in all_collections if not c.startswith("system.")]
        logger.info(f"整库模式, 发现 {len(user_collections)} 个集合: {user_collections}")
        return user_collections

    def _build_target_mongo_url(self) -> str:
        if self.req.target_username:
            safe_password = quote_plus(self.req.target_password or "")
            return f"mongodb://{self.req.target_username}:{safe_password}@{self.req.target_host}:{self.req.target_port}/{self.req.target_db_name}?authSource=admin"
        return f"mongodb://{self.req.target_host}:{self.req.target_port}/{self.req.target_db_name}"

    def _migrate_collection_to_mongo(self, collection_name: str, target_client: MongoClient) -> dict:
        """
        迁移单个 Collection -> 目标 MongoDB
        策略: 原始文档直接写入, 不做任何结构改变
        """
        target_name = self._resolve_target_name(collection_name)
        logger.info(f"开始迁移 Collection [{collection_name}] -> [{target_name}] (目标 MongoDB)")
        start_time = time.time()

        source_col = self._get_client()[self.req.db_name][collection_name]
        target_col = target_client[self.req.target_db_name][target_name]

        query_filter = self._build_query_filter()
        cursor = source_col.find(query_filter).sort("_id", ASCENDING).batch_size(self.batch_size)

        batch_data = []
        inserted_count = 0
        current_max_watermark = None

        for doc in cursor:
            batch_data.append(doc)  # MongoDB -> MongoDB 不需要序列化, 直接传原始文档

            # 追踪水位线
            if self.req.collect_mode == "inc_id":
                current_max_watermark = str(doc["_id"])
            elif self.req.collect_mode == "inc_time" and self.req.incremental_column:
                val = doc.get(self.req.incremental_column)
                if val and (current_max_watermark is None or val > current_max_watermark):
                    current_max_watermark = val

            if len(batch_data) >= self.batch_size:
                self._upsert_batch_mongo(target_col, batch_data)
                inserted_count += len(batch_data)
                batch_data.clear()

                # 批次边界探测
                self._check_task_status(current_max_watermark)

        # 尾部处理
        if batch_data:
            self._upsert_batch_mongo(target_col, batch_data)
            inserted_count += len(batch_data)

        elapsed = time.time() - start_time
        logger.info(
            f"Collection [{collection_name}] -> [{target_name}] 完成, 迁移 {inserted_count} 条, 耗时 {elapsed:.2f}s")

        return {
            "name": collection_name,
            "target_name": target_name,
            "records": inserted_count,
            "high_watermark": str(current_max_watermark) if current_max_watermark else None
        }

    def _upsert_batch_mongo(self, target_col, batch_data: list):
        """
        MongoDB upsert: 按 _id 匹配, 存在则替换, 不存在则插入
        使用 bulk_write 保证批量性能
        """
        from pymongo import ReplaceOne
        operations = [
            ReplaceOne(
                filter={"_id": doc["_id"]},
                replacement=doc,
                upsert=True
            )
            for doc in batch_data
        ]
        target_col.bulk_write(operations, ordered=False)

    def main(self) -> dict:
        safe_url = f"mongodb://{self.req.host}:{self.req.port}/{self.req.db_name}"
        logger.info(f"启动 MongoDB 抽取引擎, 源端: {safe_url}, 目标类型: {self.req.target_type}")

        target_mongo_client = None

        try:
            # 目标为 MongoDB 时, 提前建立目标连接并验证
            if self.req.target_type == "mongodb":
                if not all([self.req.target_host, self.req.target_db_name]):
                    raise ValueError("目标类型为 MongoDB 时, target_host 和 target_db_name 不能为空")
                target_mongo_client = MongoClient(
                    self._build_target_mongo_url(),
                    serverSelectionTimeoutMS=10000
                )
                # ping 一下验证连接
                target_mongo_client.admin.command("ping")
                logger.info(f"目标 MongoDB 连接成功: {self.req.target_host}:{self.req.target_port}")

            collections = self._get_collections()
            if not collections:
                logger.warning("未找到任何可迁移的集合")
                return {"status": "success", "tables_synced": 0, "total_records": 0,
                        "new_watermark": None, "table_details": []}

            table_details = []
            global_max_watermark = None

            for collection_name in collections:
                self._check_task_status(global_max_watermark)

                # ↓ 根据目标类型路由到不同的迁移方法
                if self.req.target_type == "postgresql":
                    detail = self._migrate_collection(collection_name)
                else:
                    detail = self._migrate_collection_to_mongo(collection_name, target_mongo_client)

                table_details.append(detail)

                wm = detail.get("high_watermark")
                if wm and (global_max_watermark is None or wm > global_max_watermark):
                    global_max_watermark = wm

            total_records = sum(d["records"] for d in table_details)
            logger.info(f"MongoDB 抽取完成, {len(collections)} 个集合, {total_records} 条文档")

            return {
                "status": "success",
                "tables_synced": len(collections),
                "total_records": total_records,
                "new_watermark": global_max_watermark,
                "table_details": table_details
            }

        except (TaskPausedException, TaskCancelledException):
            raise

        except Exception as e:
            logger.error(f"MongoDB 抽取引擎异常: {e}")
            raise

        finally:
            if self.client:
                self.client.close()
            if target_mongo_client:
                target_mongo_client.close()
                logger.info("目标 MongoDB 连接已关闭")
