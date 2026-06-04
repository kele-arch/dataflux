# -- coding: utf-8 --
# @Author: 胡H
# @File: app/core/logger_route.py
# @Created: 2026/2/28 16:12
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 全局操作日志拦截器 (基于 APIRoute)
import time
from typing import Callable
from fastapi import Request, Response
from fastapi.routing import APIRoute
from jose import jwt, JWTError
import asyncio

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.otherModel import SysLog


def save_log_to_db(log_data: dict):
    """ 异步保存日志到数据库的函数 """
    db = SessionLocal()  # 开启一个独立的数据库会话
    try:
        sys_log = SysLog(**log_data)
        db.add(sys_log)
        db.commit()
    except Exception as e:
        print(f"日志保存失败: {e}")
    finally:
        db.close()


class OperationLogRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            # 开始计时
            start_time = time.time()

            # 获取请求基本信息
            req_body = await request.body()
            oper_param = req_body.decode("utf-8") if req_body else ""
            oper_ip = request.client.host

            # 解析操作人 (从 Header 提取 Token)
            oper_name = "匿名访问"
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                try:
                    # 解析 JWT，获取 sub (我们存的是手机号)
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    # 这里也可以去数据库查真实的 real_name，为了性能这里直接存手机号
                    oper_name = payload.get("sub", "未知用户")
                except JWTError:
                    pass

            # 获取模块名和操作名 (从 router 的 tags 和 summary 中提取)
            # tags 通常长这样: ["用户管理"]
            title = self.tags[0] if self.tags else "未知模块"
            # summary 通常长这样: "新增用户"
            action = self.summary if self.summary else "未知操作"

            # 推断业务类型 (1新增 2修改 3删除 0其他)
            business_type = 0
            if "新增" in action or "创建" in action or request.method == "POST":
                business_type = 1
            if "修改" in action or "更新" in action or request.method == "PUT":
                business_type = 2
            if "删除" in action or request.method == "DELETE":
                business_type = 3
            if "查询" in action or "列表" in action or request.method == "GET":
                business_type = 0

            #  执行真正的业务代码
            error_msg = ""
            status = 0  # 0正常 1异常
            try:
                response: Response = await original_route_handler(request)
                json_result = response.body.decode("utf-8") if response.body else ""
            except Exception as e:
                status = 1
                error_msg = str(e)
                json_result = ""
                raise e  # 抛出异常让全局异常处理器接管
            finally:
                # 无论成功失败，组装日志数据并使用 asyncio 放入后台执行，不阻塞当前请求
                cost_time = int((time.time() - start_time) * 1000)  # 耗时(毫秒)

                # 过滤掉登录接口的密码等敏感信息 (可选)
                if "login" in request.url.path:
                    oper_param = "******"

                log_data = {
                    "title": f"{title} - {action}",  # 例如: "用户管理 - 新增用户"
                    "business_type": business_type,
                    "oper_name": oper_name,
                    "oper_ip": oper_ip,
                    "oper_param": oper_param[:2000],  # 截断防止超长
                    "json_result": json_result[:2000],
                    "status": status,
                    "error_msg": error_msg[:2000]
                }

                # 创建后台任务写入数据库
                asyncio.create_task(asyncio.to_thread(save_log_to_db, log_data))

            return response

        return custom_route_handler
