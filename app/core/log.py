# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/log.py
# @Created: 2025/11/19 10:38
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:
import sys
from loguru import logger
from pathlib import Path

log_dir = Path(__file__).parent.parent.parent
log_dir.mkdir(parents=True, exist_ok=True)

logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{file}:{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)

logger.add(
    log_dir / "init.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}.{function}:{line} - {message}",
    level="DEBUG"
)
