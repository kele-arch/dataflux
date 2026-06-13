# SNMP/Socket服务模拟

## 一、SNMP

新建一个目录（例如 `snmp_data`），在里面新建一个文件叫 `public.snmprec`。 注意：文件名 `public` 就是你的 SNMP Community 字符串

将以下内容填入 `snmp_data/public.snmprec`：

```Plaintext
# 格式: OID|类型|值
# 模拟系统描述 (sysDescr)
1.3.6.1.2.1.1.1.0|4|Mocked Defense Router V1.0
# 模拟系统运行时间 (sysUpTime)
1.3.6.1.2.1.1.3.0|67|123456789
# 模拟系统名称 (sysName)
1.3.6.1.2.1.1.5.0|4|Core-Switch-01
# 模拟一个自定义接口流量数据 (IfInOctets)
1.3.6.1.2.1.2.2.1.10.1|65|4294967295
```

在同级运行 `snmpsim-command-responder --data-dir=./snmp_data --agent-udpv4-endpoint=127.0.0.1:1161`

其中连接参数为：

```json
{
  "name": "本地虚拟交换机",
  "type": "snmp",
  "host": "127.0.0.1",
  "port": 1161,
  "db_name": "public",
  "username": "",
  "password": ""
}
```

## 二、Socket

创建py文件：

```python
import asyncio
import json
import random
from datetime import datetime


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[Socket Server] 收到来自采集引擎 {addr} 的连接")
    try:
        while True:
            # 模拟硬件设备生成遥测数据
            mock_data = {
                "device_id": "SIM-SENSOR-8809",
                "timestamp": datetime.now().isoformat(),
                "cpu_usage": round(random.uniform(10.0, 95.0), 2),
                "temperature": round(random.uniform(30.0, 85.0), 2),
                "status": "online" if random.random() > 0.05 else "warning"  # 5%概率出现告警
            }

            # 转换为 JSON 字符串，并加上换行符 \n 作为粘包拆包的边界符号
            msg = json.dumps(mock_data) + "\n"

            writer.write(msg.encode('utf-8'))
            await writer.drain()  # 确保数据发送入网卡缓冲区

            print(f"[Socket Server] 发送数据: {msg.strip()}")
            await asyncio.sleep(2)  # 模拟设备每 2 秒上报一次

    except asyncio.CancelledError:
        pass
    except ConnectionResetError:
        print(f"[Socket Server] 采集引擎 {addr} 强行断开了连接")
    except Exception as e:
        print(f"[Socket Server] 连接异常: {e}")
    finally:
        print(f"[Socket Server] 关闭与 {addr} 的连接")
        writer.close()
        await writer.wait_closed()


async def main():
    # 监听本地 9999 端口
    host, port = '127.0.0.1', 9999
    server = await asyncio.start_server(handle_client, host, port)

    print(f"Socket 模拟设备已启动，监听 tcp://{host}:{port}")
    print("等待采集引擎接入...")

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务已手动停止")
```

直接运行

下面是参数：

```json
{
  "name": "本地模拟传感器-9999",
  "type": "socket",
  "host": "127.0.0.1",
  "port": 9999,
  "db_name": "device_01",
  "username": "",
  "password": ""
}
```

