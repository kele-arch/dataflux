# -- coding: utf-8 --
# @Author: 胡H
# @File: app/utils/cron_helper.py
# @Created: 2026/6/6 16:21
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Cron表达式生成器与校验器

from apscheduler.triggers.cron import CronTrigger


def generate_cron_expression(schedule_type: str, schedule_value: str) -> str:
    """
    根据用户输入的调度类型和数值,生成标准的 Cron 表达式字符串
    """
    if not schedule_type or schedule_type == "none" or not schedule_value:
        return ""

    if schedule_type == "cron":
        try:
            CronTrigger.from_crontab(schedule_value, timezone="Asia/Shanghai")

        except Exception:
            raise ValueError(f"Cron 表达式格式非法: {schedule_value}，标准格式如 '0 2 * * *'")

        return schedule_value

    if schedule_type == "interval_min":
        try:
            val = int(schedule_value)

        except (ValueError, TypeError):
            raise ValueError(f"分钟间隔必须是整数，收到: {schedule_value}")

        if val < 1 or val > 59:
            raise ValueError("分钟间隔必须在 1-59 之间")

        return f"*/{val} * * * *"

    if schedule_type == "daily":
        try:
            hh, mm = schedule_value.split(":")
            hour, minute = int(hh), int(mm)

        except Exception:
            raise ValueError("daily 模式必须为 HH:MM 格式，例如 02:30")

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"时间范围非法: {schedule_value}")

        return f"{minute} {hour} * * *"

    if schedule_type == "weekly":
        try:
            day, time_str = schedule_value.split(" ")
            hh, mm = time_str.split(":")
            hour, minute, weekday = int(hh), int(mm), int(day)

        except Exception:
            raise ValueError("weekly 模式格式应为 '周几 HH:MM'，例如 '1 02:30'")

        if weekday not in range(0, 7):
            raise ValueError("周几必须为 0-6（0=周一, 6=周日）")

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"时间范围非法: {time_str}")

        return f"{minute} {hour} * * {weekday}"

    raise ValueError(f"不支持的调度类型: {schedule_type}")
