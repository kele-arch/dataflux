# -- coding: utf-8 --
# @Author: 胡H
# @File: app/models/__init__.py
# @Created: 2025/11/19 10:37
# @LastModified:
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc: ORM 模型

from app.models.bashModel import BaseModelMixin, generate_uuid
from app.models.collectRecordModel import CollectRecord
from app.models.collectTaskModel import CollectTask
from app.models.dataSourceModel import DataSource
from app.models.otherModel import SysLog
from app.models.taskLogModel import TaskLog, SyncExecutionLog, FtpFileRecord, OssFileRecord
