# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/sync_service.py
# @Created: 2026/6/5 10:07
# @LastModified: 2026/6/5
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据库全量同步服务: 反射源库结构

import time
from sqlalchemy import create_engine, MetaData, select, Table, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from urllib.parse import quote_plus

from app.core import logger
from app.db.session import engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.dialects import get_dialect_handler


class DatabaseSyncEngine:
    """ 异构数据库同步引擎核心类
    负责管理数据库连接、表结构反射清洗、以及流式数据合并
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.sync_mode = req.sync_mode
        self.batch_size = 1000

        # 动态构建数据源 URL
        self.source_url = self._build_sqlalchemy_url()
        self.source_engine = create_engine(self.source_url)

        # 获取对应的方言清洗器 (Strategy Pattern)
        self.dialect_handler = get_dialect_handler(self.req.db_type)

        # 初始化元数据容器
        self.source_metadata = MetaData()
        self.target_metadata = MetaData()

    def _build_sqlalchemy_url(self) -> str:
        """ 根据传来的表单构建连接串 """
        db_type = self.req.db_type.lower()
        safe_password = quote_plus(self.req.password)

        if db_type == "mysql":
            return f"mysql+pymysql://{self.req.username}:{safe_password}@{self.req.host}:{self.req.port}/{self.req.db_name}?charset={self.req.charset}"
        elif db_type == "postgresql":
            return f"postgresql+psycopg2://{self.req.username}:{safe_password}@{self.req.host}:{self.req.port}/{self.req.db_name}"
        else:
            raise ValueError(f"暂不支持的数据库类型: {self.req.db_type}")

    def _execute_upsert(self, conn, table, batch_data: list, pk_cols: list):
        """ 根据策略执行 PG 专属的 Upsert 逻辑 """
        stmt = pg_insert(table).values(batch_data)

        # 策略 1: 严格新增 (或表无主键)
        if not pk_cols or self.sync_mode == "insert":
            conn.execute(stmt)
            return

        # 策略 2: 跳过 (ON CONFLICT DO NOTHING)
        if self.sync_mode == "skip":
            stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            conn.execute(stmt)
            return

        # 策略 3: 覆盖 (ON CONFLICT DO UPDATE)
        if self.sync_mode == "overwrite":
            update_dict = {
                c.name: c
                for c in stmt.excluded
                if c.name not in pk_cols
            }
            if update_dict:
                stmt = stmt.on_conflict_do_update(
                    index_elements=pk_cols,
                    set_=update_dict
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            conn.execute(stmt)

    def _reflect_source_schema(self) -> list:
        """ 步骤一: 反射源库表结构 """
        if self.req.collect_mode == "custom_sql":
            return []

        logger.info("正在反射源数据库表结构...")
        self.source_metadata.reflect(bind=self.source_engine)
        table_names = list(self.source_metadata.tables.keys())
        logger.info(f"成功读取到 {len(table_names)} 张源表: {table_names}")
        return table_names

    def _prepare_target_schema(self):
        """ 步骤二: 类型归一化与约束清洗, 在目标库建表 """

        if self.req.collect_mode == "custom_sql":  # 拦截
            self.target_metadata.reflect(bind=self.target_engine)  # 仅反射目标库现有表结构用于后续写入
            return

        logger.info("正在进行列类型归一化, 并彻底剥离源端约束...")

        for table_name, source_table in self.source_metadata.tables.items():
            clean_columns = []
            for c in source_table.columns:
                new_col = c.copy()

                # 调用方言处理器进行类型翻译和挂件清理
                new_col.type = self.dialect_handler.normalize_type(new_col.type)
                new_col = self.dialect_handler.clean_column(new_col)

                clean_columns.append(new_col)

            # 在目标 Metadata 中组装干净的表
            Table(table_name, self.target_metadata, *clean_columns)

        # 执行建表操作 (如果存在则忽略)
        self.target_metadata.create_all(bind=self.target_engine)
        logger.info("目标库纯净表结构初始化完成")

    def _migrate_custom_sql(self, s_conn, t_conn) -> int:
        """ 处理 Custom SQL 的提取逻辑 (使用原生 fetchmany 替代 yield_per) """
        if not self.req.target_table:
            raise ValueError("采用自定义 SQL 模式时, 必须指定 target_table (目标表名)")

        target_table_name = self.req.target_table
        if target_table_name not in self.target_metadata.tables:
            raise ValueError(f"目标库不存在表: {target_table_name}。请先建表")

        target_table = self.target_metadata.tables[target_table_name]
        pk_cols = [c.name for c in target_table.primary_key.columns]

        logger.info(f"->正在执行自定义 SQL 并抽取数据至: [{target_table_name}] ...")
        result_proxy = s_conn.execute(text(self.req.custom_sql))

        total_inserted = 0
        while True:
            # 原生流式获取替代 yield_per
            rows = result_proxy.fetchmany(self.batch_size)
            if not rows:
                break

            batch_data = [dict(row._mapping) for row in rows]
            self._execute_upsert(t_conn, target_table, batch_data, pk_cols)
            total_inserted += len(batch_data)

        return total_inserted

    def _migrate_data(self) -> int:
        """ 步骤三: 流式读取与微批次写入 (支持动态查询与水位线记录) """
        logger.info(f"开始进行数据流式搬运, 冲突策略: [{self.sync_mode}], 采集模式: [{self.req.collect_mode}] ...")
        total_records_migrated = 0

        with self.source_engine.connect() as s_conn, self.target_engine.begin() as t_conn:

            if self.req.collect_mode == "custom_sql":
                return self._migrate_custom_sql(s_conn, t_conn)

            # 如果指定了单表, 就只过滤那张表; 否则还是遍历全表
            tables_to_sync = {
                name: table for name, table in self.source_metadata.tables.items()
                if not self.req.target_table or name == self.req.target_table
            }

            for table_name, source_table in tables_to_sync.items():
                logger.info(f"->正在同步表: [{table_name}] ...")
                start_time = time.time()

                target_table = self.target_metadata.tables[table_name]
                pk_cols = [c.name for c in target_table.primary_key.columns]

                # 调用查询生成器, 替代之前的硬编码 select()
                # 把 self.req 作为 task_config 传进去
                query = self._build_extract_query(source_table, self.req)

                # 执行动态生成的查询
                result_proxy = s_conn.execute(query).yield_per(self.batch_size)

                batch_data = []
                inserted_count = 0

                # 用于记录本次采集的高水位线
                current_max_watermark = None

                for row in result_proxy:
                    row_dict = dict(row._mapping)
                    batch_data.append(row_dict)

                    # 如果是增量模式, 找出这批数据中的最大值
                    if self.req.collect_mode in ["inc_id", "inc_time"] and self.req.incremental_column:
                        val = row_dict.get(self.req.incremental_column)
                        if val is not None:
                            # 简单的最大值打擂台比对
                            if current_max_watermark is None or val > current_max_watermark:
                                current_max_watermark = val

                    # 满一批次就入库
                    if len(batch_data) >= self.batch_size:
                        self._execute_upsert(t_conn, target_table, batch_data, pk_cols)
                        inserted_count += len(batch_data)
                        batch_data.clear()

                # 尾部处理
                if batch_data:
                    self._execute_upsert(t_conn, target_table, batch_data, pk_cols)
                    inserted_count += len(batch_data)

                total_records_migrated += inserted_count
                elapsed = time.time() - start_time

                watermark_log = f" (产生新水位线: {current_max_watermark})" if current_max_watermark else ""
                logger.info(f"   [{table_name}] 完成！迁移 {inserted_count} 条, 耗时 {elapsed:.2f} 秒{watermark_log}")

        return total_records_migrated

    def _build_extract_query(self, source_table, task_config):
        """
        根据前端配置的采集模式, 动态生成源库查询语句
        """
        mode = task_config.collect_mode

        # 1. 自定义 SQL 模式 (最高优先级)
        if mode == "custom_sql" and task_config.custom_sql:
            logger.info("采用 [自定义SQL] 模式进行提取")
            # 使用 text() 执行原生 SQL
            return text(task_config.custom_sql)

        # 构造基础的 Select 语句
        base_query = select(source_table)

        # 2. 全量采集
        if mode == "full":
            logger.info("采用 [全量] 模式进行提取")
            return base_query

        # 3. 增量 - 自增列模式
        if mode == "inc_id" and task_config.incremental_column and task_config.last_watermark:
            logger.info(f"采用 [自增列] 增量提取, 水位线: {task_config.last_watermark}")
            inc_col = getattr(source_table.c, task_config.incremental_column)
            # WHERE id > last_watermark
            return base_query.where(inc_col > task_config.last_watermark)

        # 4. 增量 - 时间戳模式
        if mode == "inc_time" and task_config.incremental_column and task_config.last_watermark:
            logger.info(f"采用 [时间戳] 增量提取, 水位线: {task_config.last_watermark}")
            time_col = getattr(source_table.c, task_config.incremental_column)
            # WHERE update_time > '2026-06-04 12:00:00'
            return base_query.where(time_col > task_config.last_watermark)

        # 默认回退到全量
        return base_query

    def main(self) -> dict:
        """ """
        safe_url = self.source_url.replace(self.req.password, '******')
        logger.info(f"启动数据迁移引擎, 源端: {safe_url}")

        try:
            table_names = self._reflect_source_schema()
            self._prepare_target_schema()
            total_records = self._migrate_data()

            logger.info(f"全库同步完美收官！共迁移 {len(table_names)} 张表, {total_records} 条记录")
            return {
                "status": "success",
                "tables_synced": len(table_names),
                "total_records": total_records
            }

        except SQLAlchemyError as e:
            logger.error(f"数据库迁移引擎引发异常: {str(e)}")
            raise e
        finally:
            # 释放源库连接池
            self.source_engine.dispose()


def sync_database_architecture_and_data(req: DBSyncReq) -> dict:
    """
    将请求交给 OOP 引擎处理, 隐藏内部的复杂状态流转
    """
    engine = DatabaseSyncEngine(req)
    return engine.main()
