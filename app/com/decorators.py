# -- coding: utf-8 --
# @Author: 胡H
# @File: app/com/decorators.py
# @Created: 2025/11/19 14:18
# @LastModified: 
# Copyright (c) 2025 by 胡H, All Rights Reserved.
# @desc:
import time
import random
import functools

from app.core import logger


def retry_request(max_retries=3, delay=1, backoff=3, exceptions=(Exception,)):
    """ 请求重试装饰器
    :param max_retries: 最大重试次数
    :param delay: 初始延迟
    :param backoff: 延迟倍数
    :param exceptions: 捕获的异常类型
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"重试次数达到最大值 {func.__name__}: {str(e)}")
                        raise

                    sleep_time = delay * (backoff ** (attempt - 1)) + random.uniform(0, 1)
                    logger.warning(
                        f"尝试 {attempt}/{max_retries} 不适用于 {func.__name__}: {str(e)}. "
                        f"在重试 {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)

        return wrapper

    return decorator


def measure_time(func):
    """获取函数执行时间"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.info(f"函数 {func.__name__} 执行时间: {end - start:.6f} 秒")
        return result

    return wrapper
