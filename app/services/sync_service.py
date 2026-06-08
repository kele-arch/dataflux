# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/sync_service.py
# @Created: 2026/6/5 10:07
# @LastModified: 2026/6/5
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 数据库全量同步服务: 反射源库结构

import time
from datetime import datetime

from sqlalchemy import create_engine, MetaData, select, Table, text, Text, String, Integer, DateTime, Boolean, JSON, \
    Date, Numeric
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from urllib.parse import quote_plus

from app.core import logger
from app.db.session import engine as global_target_engine
from app.schemas.tsync import DBSyncReq
from app.services.dialects import get_dialect_handler
from app.services.task_control import get_task_status, save_watermark, TASK_PAUSED, TASK_CANCELLED
from app.exceptions import TaskPausedException, TaskCancelledException
from app.core.config import settings


class DatabaseSyncEngine:
    """ 异构数据库同步引擎核心类
    负责管理数据库连接、表结构反射清洗、以及流式数据合并
    """

    def __init__(self, req: DBSyncReq, target_engine=global_target_engine):
        self.req = req
        self.target_engine = target_engine
        self.sync_mode = req.sync_mode
        self.batch_size = settings.BATCH_SIZE

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
        elif db_type == "dm":
            return f"dm+dmPython://{self.req.username}:{safe_password}@{self.req.host}:{self.req.port}"
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

        # 达梦专属: 反射时必须指定 schema = username.toUpperCase()
        reflect_kwargs = {"bind": self.source_engine}
        if self.req.db_type.lower() == "dm":
            reflect_kwargs["schema"] = self.req.username.upper()

        # sync_tables 指定了就只反射这些表, 否则整库反射
        if self.req.sync_tables:
            if self.req.db_type.lower() == "dm":
                # 达梦适配: 用 inspect 查出物理表名, 做大小写不敏感匹配
                from sqlalchemy import inspect as sa_inspect
                inspector = sa_inspect(self.source_engine)
                actual_tables = inspector.get_table_names(schema=self.req.username.upper())
                # 构建 {小写名: 物理名} 映射
                table_map = {t.lower(): t for t in actual_tables}
                # 用物理名反射
                only_tables = []
                for t in self.req.sync_tables:
                    physical = table_map.get(t.lower())
                    if physical:
                        only_tables.append(physical)
                    else:
                        logger.warning(f"源库中不存在表: {t}, 已跳过")
                if not only_tables:
                    logger.error("所有指定的表在源库中都不存在")
                    return []
                logger.info(f"采用 [指定多表] 模式, 物理表名: {only_tables}")
            else:
                only_tables = self.req.sync_tables
                logger.info(f"采用 [指定多表] 模式, 目标: {only_tables}")

            reflect_kwargs["only"] = only_tables
            self.source_metadata.reflect(**reflect_kwargs)
        else:
            logger.info("采用 [整库反射] 模式")
            self.source_metadata.reflect(**reflect_kwargs)

        table_names = list(self.source_metadata.tables.keys())
        logger.info(f"成功读取到 {len(table_names)} 张源表: {table_names}")
        return table_names

    def _resolve_target_name(self, source_name: str) -> str:
        """ 根据 table_mapping 将源表名映射为目标表名, 无映射则同名 """
        mapping = self.req.table_mapping or {}
        # 先精确匹配
        if source_name in mapping:
            return mapping[source_name]
        # 达梦适配: 大小写不敏感匹配 (用户可能传 DEVICE, 实际是 device)
        if self.req.db_type.lower() == "dm":
            lower_name = source_name.lower()
            for k, v in mapping.items():
                if k.lower() == lower_name:
                    return v
        return source_name

    def _prepare_target_schema(self):
        """ 步骤二: 类型归一化与约束清洗, 在目标库建表 """

        if self.req.collect_mode == "custom_sql":  # 拦截
            # 仅反射目标那 1 张表, 极大提升启动速度
            if self.req.target_table:
                self.target_metadata.reflect(bind=self.target_engine, only=[self.req.target_table])
            else:
                self.target_metadata.reflect(bind=self.target_engine)
            return

        logger.info("正在进行列类型归一化, 并彻底剥离源端约束...")
        from sqlalchemy import Column as SAColumn

        for table_name, source_table in self.source_metadata.tables.items():
            clean_columns = []
            for c in source_table.columns:
                # 调用方言处理器进行类型翻译
                col_type = self.dialect_handler.normalize_type(c.type)

                # 彻底清理排序规则 (DM/MySQL 源库可能带 utf8mb3_general_ci 等 PG 不认识的 collation)
                if hasattr(col_type, 'collation'):
                    col_type.collation = None

                # 达梦适配: 列名转小写 (达梦默认大写, PG 默认小写)
                col_name = c.name.lower() if self.req.db_type.lower() == "dm" else c.name

                # 创建全新的 Column (避免 Column.copy() 浅拷贝污染源表元数据)
                new_col = SAColumn(col_name, col_type, nullable=True)

                clean_columns.append(new_col)

            # 达梦反射出的表名格式为 'SCHEMA.TABLE_NAME', 需要清洗为纯表名
            pure_name = table_name.split('.')[-1] if '.' in table_name else table_name
            # 应用表名映射
            target_name = self._resolve_target_name(pure_name)
            Table(target_name, self.target_metadata, *clean_columns)

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

            # 写完之后再探测,保证这批数据已安全落库
            self._check_task_status()

        return total_inserted

    def _migrate_data(self) -> tuple:
        """ 步骤三: 流式读取与微批次写入 (支持动态查询与水位线记录) """
        logger.info(f"开始进行数据流式搬运, 冲突策略: [{self.sync_mode}], 采集模式: [{self.req.collect_mode}] ...")
        total_records_migrated = 0
        global_max_watermark = None  # 全局最大水位线, 用于记录整个迁移过程的最高时间戳
        table_details = []  # 收集每张表的执行明细

        with self.source_engine.connect() as s_conn, self.target_engine.begin() as t_conn:

            if self.req.collect_mode == "custom_sql":
                start_time = time.time()
                total = self._migrate_custom_sql(s_conn, t_conn)
                elapsed = round(time.time() - start_time, 2)
                table_details.append({
                    "name": self.req.target_table,
                    "records": total,
                    "cost_seconds": elapsed
                })
                return total, None, table_details

            for table_name, source_table in self.source_metadata.tables.items():

                self._check_task_status(global_max_watermark)  # 每张表开始前探测

                # 达梦反射出的表名格式为 'SCHEMA.TABLE_NAME', 清洗为纯表名
                pure_name = table_name.split('.')[-1] if '.' in table_name else table_name
                target_name = self._resolve_target_name(pure_name)
                logger.info(f"->正在同步表: [{table_name}] -> [{target_name}] ...")
                start_time = time.time()

                target_table = self.target_metadata.tables[target_name]
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

                    clean_dict = self._clean_row_data(row_dict, target_table)  # 数据清洗

                    batch_data.append(clean_dict)

                    # 如果是增量模式, 找出这批数据中的最大值
                    if self.req.collect_mode in ["inc_id", "inc_time"] and self.req.incremental_column:
                        # 达梦适配: 行数据中的 key 是大写, 需要转换
                        wm_col = self.req.incremental_column.upper() if self.req.db_type.lower() == "dm" else self.req.incremental_column
                        val = row_dict.get(wm_col)
                        if val is not None:
                            if current_max_watermark is None or val > current_max_watermark:
                                current_max_watermark = val

                    # 满一批次就入库
                    if len(batch_data) >= self.batch_size:
                        self._execute_upsert(t_conn, target_table, batch_data, pk_cols)
                        inserted_count += len(batch_data)
                        batch_data.clear()

                        # 使用当前表的最高水位线,或者回退到全局水位线
                        self._check_task_status(current_max_watermark or global_max_watermark)

                # 尾部处理
                if batch_data:
                    self._execute_upsert(t_conn, target_table, batch_data, pk_cols)
                    inserted_count += len(batch_data)

                total_records_migrated += inserted_count
                elapsed = round(time.time() - start_time, 2)

                # 收集单表执行明细
                table_details.append({
                    "name": table_name,
                    "target_name": target_name,
                    "records": inserted_count,
                    "cost_seconds": elapsed,
                    "high_watermark": str(current_max_watermark) if current_max_watermark else None
                })

                watermark_log = f" (产生新水位线: {current_max_watermark})" if current_max_watermark else ""
                logger.info(f"   [{table_name}] 完成！迁移 {inserted_count} 条, 耗时 {elapsed} 秒{watermark_log}")

                if current_max_watermark:
                    if global_max_watermark is None or current_max_watermark > global_max_watermark:
                        global_max_watermark = current_max_watermark

        return total_records_migrated, global_max_watermark, table_details

    def _build_extract_query(self, source_table, task_config):
        """
        根据前端配置的采集模式, 动态生成源库查询语句
        """
        mode = task_config.collect_mode
        base_query = select(source_table)  # 构造基础的 Select 语句

        # 1. 全量采集
        if mode == "full":
            logger.info("采用 [全量] 模式进行提取")
            return base_query

        # 达梦适配: 列名强转大写 (达梦默认大写存储)
        col_name = task_config.incremental_column
        if task_config.db_type.lower() == "dm" and col_name:
            col_name = col_name.upper()

        # 2. 增量 - 自增列模式
        if mode == "inc_id" and col_name and task_config.last_watermark:
            logger.info(f"采用 [自增列] 增量提取, 水位线: {task_config.last_watermark}")
            inc_col = getattr(source_table.c, col_name)
            return base_query.where(inc_col > task_config.last_watermark)

        # 3. 增量 - 时间戳模式
        if mode == "inc_time" and col_name and task_config.last_watermark:
            logger.info(f"采用 [时间戳] 增量提取, 水位线: {task_config.last_watermark}")
            time_col = getattr(source_table.c, col_name)
            return base_query.where(time_col > task_config.last_watermark)

        # 默认回退到全量
        return base_query

    def _clean_row_data(self, row_dict: dict, target_table) -> dict:
        """
        清洗单行数据, 适配目标表结构与类型兜底
        解决跨库同步时的列缺失、NOT NULL 冲突和类型转换崩溃问题
        """
        cleaned = {}
        is_dm = self.req.db_type.lower() == "dm"

        for col in target_table.columns:
            col_name = col.name
            # 达梦适配: 源数据 key 是大写, 目标列名是小写, 需要双向匹配
            # 不能用 or, 因为 0、""、False 会被当作 falsy 丢弃
            val = row_dict.get(col_name)
            if val is None and is_dm:
                val = row_dict.get(col_name.upper())

            # 源数据有值, 且不是 None, 直接保留
            if val is not None:
                cleaned[col_name] = val
                continue

            # 源数据为 None 或完全缺失
            # 如果目标列允许为空(nullable), 或者数据库层面有默认值(default/server_default)
            if col.nullable:
                # 目标表允许为空，统一强塞 None（数据库会存为 NULL）
                cleaned[col_name] = None
            else:
                # 情况 3：目标表 NOT NULL，必须在代码层给一个极其安全的真实兜底值
                if isinstance(col.type, (String, Text)):
                    cleaned[col_name] = ""
                elif isinstance(col.type, (Integer, Numeric)):
                    cleaned[col_name] = 0
                elif isinstance(col.type, Boolean):
                    cleaned[col_name] = False
                elif isinstance(col.type, (DateTime, Date)):
                    cleaned[col_name] = datetime.now()  # 或赋予一个极小值如 datetime(1970,1,1)
                elif isinstance(col.type, JSON):
                    cleaned[col_name] = {}
                else:
                    # 极其冷门的类型
                    cleaned[col_name] = None

        return cleaned

    def _check_task_status(self, current_watermark=None):
        """
        探测 Redis 状态位, 决定是否中断。
        在每个安全的 batch 边界调用, 确保中断时数据已落库且连接可安全释放
        """

        task_id = str(self.req.task_id)

        status = get_task_status(task_id)

        if status == TASK_PAUSED:
            save_watermark(task_id, current_watermark)
            logger.warning(f"任务 [{task_id}] 接收到暂停指令, 已保存断点水位线: {current_watermark}")
            raise TaskPausedException(f"任务已暂停, 水位线保存至: {current_watermark}")

        if status == TASK_CANCELLED:
            logger.warning(f"任务 [{task_id}] 接收到取消指令, 强制终止搬运")
            raise TaskCancelledException("任务已被用户取消")

    def main(self) -> dict:
        """ """
        safe_password = quote_plus(self.req.password)
        safe_url = self.source_url.replace(safe_password, '******')
        logger.info(f"启动数据迁移引擎, 源端: {safe_url}")

        try:
            table_names = self._reflect_source_schema()
            self._prepare_target_schema()
            total_records, new_watermark, table_details = self._migrate_data()

            logger.info(f"全库同步完成！共迁移 {len(table_names)} 张表, {total_records} 条记录")
            return {
                "status": "success",
                "tables_synced": len(table_names),
                "total_records": total_records,
                "new_watermark": new_watermark,
                "table_details": table_details
            }
        except TaskPausedException as e:
            # 捕获暂停
            return {"status": "paused", "message": str(e)}

        except TaskCancelledException as e:
            # 捕获取消
            return {"status": "cancelled", "message": str(e)}

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
