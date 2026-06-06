# -- coding: utf-8 --
# @Author: 胡H
# @File: app/exceptions.py
# @Created: 2026/6/6 10:42
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 自定义异常类, 以便在任务执行过程中更清晰地处理不同的异常情况

class TaskPausedException(Exception):
    """任务被用户暂停 , 属于正常中断"""
    pass


class TaskCancelledException(Exception):
    """任务被用户取消 , 属于正常中断"""
    pass
