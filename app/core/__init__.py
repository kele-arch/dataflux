# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/__init__.py
# @Created: 2025/11/19 10:37
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:

import socket
from pathlib import Path
from .log import logger


# ----------------- 全局工具变量 -----------------
current_file = Path(__file__).parent
project_rootpath = current_file.parent.parent  # 根目录
hostname = socket.gethostname()
