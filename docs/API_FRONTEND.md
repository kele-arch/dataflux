# 接口对接文档

> BaseURL: `http://0.0.0.0:8028/api/v1`

---

## 一、数据源管理 `/datasource`

### 1. 测试连接

`POST /datasource/test_connect`

```json
{
  "name": "产线A_MySQL",
  "type": "mysql",
  "host": "192.168.1.100",
  "port": 3306,
  "db_name": "factory_db",
  "username": "root",
  "password": "123456",
  "config_json": {"charset": "utf8mb4"}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源名称 |
| type | string | ✅ | 类型：`mysql` / `postgresql` / `oracle` / `sqlserver` / `dm` / `sqlite` / `mongodb` / `ftp` / `api` / `snmp` / `socket` / `kafka` / `mqtt` / `rabbitmq` / `oss` |
| host | string | ✅ | 主机地址 |
| port | int | ✅ | 端口 |
| db_name | string | ✅ | 数据库名 |
| username | string | ❌ | 用户名 |
| password | string | ❌ | 密码 |
| config_json | object | ❌ | 高级配置，如 `{"charset":"utf8mb4"}` |

---

### 2. 新增数据源

`POST /datasource/add`

请求体同「测试连接」。

响应：

```json
{"code": 1, "msg": "数据源保存成功", "data": {"id": "550e8400e29b41d4a716446655440000"}}
```

---

### 3. 修改数据源

`POST /datasource/update`

在「测试连接」的基础上多一个 `source_id`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | 数据源 UUID（32位） |
| 其他字段 | - | ❌ | 同「测试连接」，只传需要改的字段 |

```json
{
  "source_id": "550e8400e29b41d4a716446655440000",
  "name": "产线A_MySQL_改名",
  "host": "192.168.1.200"
}
```

---

### 4. 删除数据源

`POST /datasource/delete`

```json
{"source_id": "550e8400e29b41d4a716446655440000"}
```

---

### 5. 数据源列表

`POST /datasource/list`

```json
{"page": 1, "size": 10, "name": "产线", "type": "mysql", "sort_by": "create_time", "sort_order": "desc"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | ❌ | 页码，默认 1 |
| size | int | ❌ | 每页条数，默认 10 |
| name | string | ❌ | 按名称模糊搜索 |
| type | string | ❌ | 按类型过滤 |
| sort_by | string | ❌ | 排序字段：`create_time`（默认）/ `name` |
| sort_order | string | ❌ | 排序方向：`desc`（默认）/ `asc` |
| db_type | string | ❌ | 数据源筛选 |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "total": 25,
    "items": [
      {
        "id": "550e8400e29b41d4a716446655440000",
        "name": "产线A_MySQL",
        "type": "mysql",
        "host": "192.168.1.100",
        "port": 3306,
        "db_name": "factory_db",
        "username": "root",
        "config_json": {"charset": "utf8mb4"}
      }
    ]
  }
}
```

---

### 6. 获取数据源下的表名

`POST /datasource/tables`

```json
{"source_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": ["users", "orders", "products"]
}
```

---

### 7. 获取表结构详情（含注释）

`POST /datasource/tables/detail`

返回每张表的表名、表注释、字段名、字段类型、字段注释。

```json
{"source_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    {
      "table_name": "users",
      "table_comment": "用户信息表",
      "columns": [
        {"name": "id", "type": "BIGINT", "comment": "主键ID"},
        {"name": "username", "type": "VARCHAR(50)", "comment": "用户名"},
        {"name": "phone", "type": "VARCHAR(20)", "comment": "手机号"}
      ]
    },
    {
      "table_name": "orders",
      "table_comment": "订单表",
      "columns": [
        {"name": "id", "type": "BIGINT", "comment": "主键ID"},
        {"name": "user_id", "type": "BIGINT", "comment": "关联用户ID"},
        {"name": "amount", "type": "DECIMAL(10,2)", "comment": "订单金额"}
      ]
    }
  ]
}
```

---

## 二、同步任务管理 `/tsync`

> ### ⚠️ 核心字段语义说明（必读）
>
> | 字段 | 必填 | 含义 | 说明 |
> |------|------|------|------|
> | `sync_tables` | ❌ | **源库**要同步的表名列表 | 从源数据库中反射哪些表。不传 = 整库同步 |
> | `topic_or_table` | ❌ | `custom_sql` 模式下目标库写入表名 | **普通模式不需要传**，只在 `custom_sql` 模式下必填 |
>
> **普通模式（full/inc_id/inc_time）：** 只需传 `sync_tables` 指定源表，`topic_or_table` 不用传。
>
> **custom_sql 模式：** `topic_or_table` 必填，指定目标库中**已存在**的写入表名。

---

### 1. 全量克隆（直接同步）

`POST /tsync/database`

不走任务系统，直接传连接信息执行同步。

```json
{
  "db_type": "mysql",
  "host": "192.168.1.100",
  "port": 3306,
  "username": "root",
  "password": "123456",
  "db_name": "factory_db",
  "sync_tables": ["users", "orders"],
  "sync_mode": "overwrite",
  "collect_mode": "full"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| db_type | string | ✅ | `mysql` / `postgresql` / `oracle` / `sqlserver` / `dm` / `sqlite` / `mongodb` / `mqtt` / `rabbitmq` / `oss` |
| host | string | ✅ | 主机地址 |
| port | int | ✅ | 端口 |
| username | string | ✅ | 用户名 |
| password | string | ✅ | 密码 |
| db_name | string | ✅ | 数据库名 |
| charset | string | ❌ | 字符集，默认 `utf8mb4` |
| sync_tables | string[] | ❌ | 源库要同步的表名列表。不传 = 整库同步 |
| target_table | string | ❌ | `custom_sql` 模式下必填，目标库写入哪张表。普通模式不用传 |
| sync_mode | string | ❌ | 冲突策略：`overwrite`(覆盖) / `skip`(跳过) / `insert`(纯新增)，默认 `overwrite` |
| collect_mode | string | ❌ | 采集模式：`full`(全量) / `inc_id`(自增列增量) / `inc_time`(时间戳增量) / `custom_sql`，默认 `full` |
| incremental_column | string | ❌ | 增量依赖的字段名，如 `id` 或 `update_time` |
| last_watermark | string | ❌ | 上次采集的最大水位线 |
| custom_sql | string | ❌ | 自定义提取 SQL（`collect_mode=custom_sql` 时使用） |

---

### 2. 新增任务

`POST /tsync/add`

```json
{
  "task_name": "每日同步用户表",
  "source_id": "550e8400e29b41d4a716446655440000",
  "sync_tables": ["users", "orders"],
  "sync_mode": "overwrite",
  "collect_mode": "inc_time",
  "incremental_column": "update_time",
  "schedule_type": "daily",
  "schedule_value": "02:30",
  "status": 1,
  "remark": "每天凌晨2点增量同步"
}
```

响应：

```json
{"code": 1, "msg": "任务创建成功", "data": {"id": "550e8400e29b41d4a716446655440000"}}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_name | string | ✅ | 任务名称 |
| source_id | string | ❌ | 关联的数据源 UUID |
| topic_or_table | string | ❌ | `custom_sql` 模式下必填，指定目标库写入表名。普通模式不用传 |
| sync_tables | string[] | ❌ | **源库**要同步的表名列表（必须是源库中真实存在的表）。不传 = 整库同步 |
| table_mapping | object | ❌ | 表名映射：`{"源表名":"目标表名"}`，不传则同名写入。见下方详解 |
| sync_mode | string | ❌ | 冲突策略，默认 `overwrite` |
| collect_mode | string | ❌ | 采集模式，默认 `full` |
| incremental_column | string | ❌ | 增量字段名 |
| last_watermark | string | ❌ | 水位线 |
| custom_sql | string | ❌ | 自定义 SQL |
| schedule_type | string | ❌ | 调度类型，见下方说明，默认 `none`（不调度） |
| schedule_value | string | ❌ | 配合 `schedule_type` 使用的值，见下方说明 |
| status | int | ❌ | 0=停用, 1=启用，默认 1 |
| remark | string | ❌ | 备注 |
| target_type | string | ❌ | 目标库类型：`postgresql`（默认）/ `mongodb`，详见第五章 |
| target_host | string | ❌ | 目标库主机（仅 `target_type=mongodb` 时生效） |
| target_port | int | ❌ | 目标库端口（仅 `target_type=mongodb` 时生效） |
| target_username | string | ❌ | 目标库账号（仅 `target_type=mongodb` 时生效） |
| target_password | string | ❌ | 目标库密码（仅 `target_type=mongodb` 时生效） |
| target_db_name | string | ❌ | 目标库名（仅 `target_type=mongodb` 时生效） |
| clean_policy | string | ❌ | 清理策略：`none`（默认）/ `by_days` / `by_count`。⚠️ 分支功能，详见[DLM](#15-数据生命周期管理dlm) |
| clean_keep_days | int | ❌ | `by_days` 模式：保留最近 N 天数据 |
| clean_keep_count | int | ❌ | `by_count` 模式：保留最新 N 条数据 |
| clean_cron | string | ❌ | 自动清理 Cron 表达式，如 `"0 3 * * *"` |

#### 采集模式详解 (`collect_mode`)

| collect_mode | 说明 | 是否需要 `incremental_column` | 是否需要 `last_watermark` |
|---|---|---|---|
| `full` | 每次全量抽取所有数据 | ❌ 不需要 | ❌ 不需要 |
| `inc_id` | 按数字列增量（自增主键、业务ID等） | ✅ 必填 | ❌ 首次不填，系统自动记录 |
| `inc_time` | 按时间列增量（更新时间、创建时间等） | ✅ 必填 | ❌ 首次不填，系统自动记录 |
| `custom_sql` | 执行自定义 SQL | ❌ 不需要 | ❌ 不需要 |

**⚠️ 重要限制：** `incremental_column` 是**任务级**的单一字段，对 `sync_tables` 里的**所有表**生效。

- 如果所有表都有同名列（如 `update_time`）→ 可以用增量模式
- 如果各表列名不同 → 只能用 `full` 全量，或按列名分组建多个任务
- 如果填了 `incremental_column` 但某张表没有这个列 → 引擎报错

**示例：**

```json
// ✅ 正确：所有表都有 update_time
{
  "sync_tables": ["orders", "users", "products"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}

// ✅ 正确：按列名分组建任务
{
  "task_name": "有update_time的表",
  "sync_tables": ["orders", "users"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}
{
  "task_name": "只有id的表",
  "sync_tables": ["products"],
  "collect_mode": "inc_id",
  "incremental_column": "id"
}

// ✅ 正确：全量模式，不需要 incremental_column
{
  "sync_tables": ["orders", "users", "products"],
  "collect_mode": "full"
}

// ❌ 错误：products 表没有 update_time，会报错
{
  "sync_tables": ["orders", "users", "products"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}
```

#### `incremental_column` 字段说明

指定用源表中的**哪一列**作为增量判断依据。可以是任意列名，不限于主键：

| 场景 | collect_mode | incremental_column 填什么 |
|---|---|---|
| 按自增主键拉新增行 | `inc_id` | `"id"` |
| 按业务编号拉新增行 | `inc_id` | `"order_no"` |
| 按更新时间拉新增+修改行 | `inc_time` | `"update_time"` |
| 按创建时间只拉新增行 | `inc_time` | `"create_time"` |

#### `last_watermark` 字段说明

记录上次同步的"断点"，用于增量模式下次执行时过滤数据。

- **首次执行：** 不传，引擎全量抽取，完成后自动记录水位线
- **后续执行：** 不传，引擎自动从任务表读取上次的水位线
- **手动指定：** 传值（如 `"2026-06-08 10:00:00"` 或 `"1000"`），覆盖自动记录

**水位线记录规则：**

| collect_mode | 水位线值 | 示例 |
|---|---|---|
| `inc_id` | 最后一条的列值 | `"1000"` |
| `inc_time` | 最后一条的时间值 | `"2026-06-08 10:00:00"` |
| `full` | 不记录 | `null` |
| `custom_sql` | 不记录 | `null` |

#### `custom_sql` 字段说明

仅在 `collect_mode = "custom_sql"` 时生效。在**源库**执行自定义 SQL，结果写入目标库。

```json
{
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM orders WHERE status = 'active' AND create_time > '2026-01-01'",
  "topic_or_table": "active_orders"
}
```

- `custom_sql`：在源库执行的 SQL 语句
- `topic_or_table`：目标库中**已存在**的写入表名（必填）
- `sync_tables`：不传，由 SQL 决定查什么

#### 表名映射详解 (`table_mapping`)

同步时源表名和目标表名默认一致。如果需要改名，传入 `table_mapping` 字典：

```json
{
  "sync_tables": ["users", "orders", "products"],
  "table_mapping": {"users": "t_users", "orders": "t_orders"}
}
```

**效果：**

| 源表名 | 目标表名 | 说明 |
|--------|----------|------|
| `users` | `t_users` | 映射生效 |
| `orders` | `t_orders` | 映射生效 |
| `products` | `products` | 未在映射中，保持同名 |

**使用场景：**

| 场景 | 示例 |
|------|------|
| 源表名和目标表名冲突（同库同步） | `{"users": "bak_users"}` |
| 源表名不规范，想重命名 | `{"t_1": "user_info", "t_2": "order_info"}` |
| 多数据源汇聚到同一目标库，加前缀区分 | `{"users": "src_a_users", "orders": "src_a_orders"}` |
| 全部同名（不传 table_mapping） | 不传此字段即可 |

**注意事项：**
- 只需要映射的表写进去，不需要映射的不用写
- MongoDB 同样支持（集合名映射）
- 映射后的表名如果目标库已存在，按 `sync_mode` 策略处理（overwrite/skip/insert）

#### 调度类型详解

| schedule_type | schedule_value | 说明 | 生成的 Cron | 示例 |
|---------------|----------------|------|-------------|------|
| `none` | 不传 | 不自动调度，仅手动执行 | 无 | — |
| `cron` | 标准 Cron 表达式 | 自定义完整 Cron | 原样使用 | `"0 2 * * *"` = 每天 02:00 |
| `interval_min` | 整数（1-59） | 每 N 分钟执行一次 | `*/N * * * *` | `"5"` = 每 5 分钟 |
| `daily` | `HH:MM` | 每天固定时间执行 | `MM HH * * *` | `"02:30"` = 每天 02:30 |
| `weekly` | `周几 HH:MM` | 每周固定时间执行 | `MM HH * * 周几` | `"1 02:30"` = 每周一 02:30 |

**Cron 表达式标准格式：** `分 时 日 月 周`

```
*    *    *    *    *
┬    ┬    ┬    ┬    ┬
│    │    │    │    │
│    │    │    │    └── 星期几 (0=周一, 6=周日)
│    │    │    └─────── 月份 (1-12)
│    │    └──────────── 日 (1-31)
│    └───────────────── 时 (0-23)
└────────────────────── 分 (0-59)
```

**常用 Cron 示例：**

| 表达式 | 含义 |
|--------|------|
| `0 2 * * *` | 每天凌晨 2:00 |
| `0 */2 * * *` | 每 2 小时整点 |
| `30 8 * * 1-5` | 工作日早上 8:30 |
| `0 0 * * 0` | 每周日 0:00 |
| `*/10 * * * *` | 每 10 分钟 |

#### 使用场景示例

**场景 1：指定源表同步**

```json
{
  "task_name": "同步用户和订单表",
  "source_id": "7328215a0a3744b7ab6bcccb52bf6f7b",
  "sync_tables": ["users", "orders"],
  "collect_mode": "full",
  "sync_mode": "overwrite"
}
```

> 只传 `sync_tables`，不用传 `topic_or_table`。

**场景 2：整库同步**

```json
{
  "task_name": "整库全量同步",
  "source_id": "7328215a0a3744b7ab6bcccb52bf6f7b",
  "collect_mode": "full",
  "sync_mode": "overwrite"
}
```

> `sync_tables` 不传 = 源库所有表都同步。

**场景 3：自定义 SQL 抽取**

```json
{
  "task_name": "抽取活跃订单",
  "source_id": "7328215a0a3744b7ab6bcccb52bf6f7b",
  "topic_or_table": "target_orders",
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM orders WHERE status='active'"
}
```

> `custom_sql` 在源库执行，`topic_or_table` 指定目标库中**已存在**的写入表名（此场景必填）。

---

### 3. 修改任务

`POST /tsync/update`

在「新增任务」基础上多一个 `task_id`，其他字段只传需要改的：

```json
{
  "task_id": "550e8400e29b41d4a716446655440000",
  "task_name": "改名后的任务",
  "status": 0
}
```

---

### 4. 删除任务

`POST /tsync/delete`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

---

### 5. 切换任务启用/停用

`POST /tsync/change_status`

```json
{"task_id": "550e8400e29b41d4a716446655440000", "status": 0}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 UUID |
| status | int | ✅ | 0=停用, 1=启用 |

响应：

```json
{"code": 1, "msg": "任务已停用", "data": null}
```

---

### 6. 手动执行任务

`POST /tsync/run`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

| 情况 | 响应 |
|------|------|
| 正常入队 | `{"code":1, "msg":"任务已进入执行队列", "data":{"log_id":"xxx", "status":"pending"}}` |
| 任务正运行中 | `{"code":0, "msg":"任务正在排队或执行中, 请勿重复触发"}` |
| 任务停用 | `{"code":0, "msg":"任务处于停用状态, 无法执行"}` |
| 队列未就绪 | `{"code":0, "msg":"系统队列服务未就绪, 下发失败"}` |

**`/run` 内部流程：**

```
1. 校验任务存在 + 启用状态
2. 前置防抖：检查 Redis 分布式锁 → 锁还在 → 拒绝"请勿重复"
3. 清除 Redis 中残留的 paused/cancelled 标记
4. ORM 删除该任务旧的 pending 僵尸日志
5. 创建新 pending 状态占坑日志
6. 推入 ARQ 队列 → Worker 接管
```

**任务状态机：**

```
pending → running → success
                  → failed
                  → paused
                  → cancelled
```

| status | 含义 | 前端处理 |
|--------|------|----------|
| `pending` | 🟡 排队中 | 继续轮询，3s/次 |
| `running` | 🔵 运行中 | 继续轮询 |
| `success` | 🟢 成功 | 停止轮询 |
| `failed` | 🔴 失败 | 停止轮询，展示 error_msg |
| `paused` | ⏸️ 暂停 | 用户手动暂停 |
| `cancelled` | ❌ 取消 | 用户手动取消 |

**前端轮询示例：**

```javascript
// 点击执行后拿到 log_id 和 status
const { log_id } = response.data;
const timer = setInterval(async () => {
  const res = await fetch(`/api/v1/tasklog/detail?log_id=${log_id}`);
  const { status, error_msg } = res.data;
  if (status === 'success') { clearInterval(timer); /* 成功处理 */ }
  if (status === 'failed')  { clearInterval(timer); /* 展示 error_msg */ }
}, 3000);
```

---

### 7. 暂停正在执行的任务

`POST /tsync/pause`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{"code": 1, "msg": "暂停指令已下发, 任务将在当前批次完成后暂停", "data": null}
```

> 引擎在当前批次落盘后检测到暂停信号 → 将水位线保存到 Redis → 抛出 `TaskPausedException` → Worker 将 TaskLog 状态更新为 `paused`。恢复时调用 `/resume`，水位线从 Redis 回写到数据库。

---

### 8. 取消正在执行的任务

`POST /tsync/cancel`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{"code": 1, "msg": "取消指令已下发, 任务将立即终止", "data": null}
```

> 引擎在当前批次检测到取消信号 → 不保存水位线 → 抛出 `TaskCancelledException` → Worker 将 TaskLog 更新为 `cancelled`。取消后需重新全量执行（水位线已丢失）。

---

### 9. 恢复已暂停的任务

`POST /tsync/resume`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{
  "code": 1,
  "msg": "任务断点已恢复,成功重新入队运行",
  "data": {"log_id": "aabbccdd...", "status": "pending"}
}
```

**`/resume` 完整流程：**

```
1. 从 Redis 打捞暂停时保存的断点水位线 → 回写到任务表的 last_watermark
2. 清除 Redis 中的 paused/cancelled 控制信号
3. 创建 pending 状态占坑日志
4. 自动入队 ARQ，Worker 接管后续执行
```

> 无需再点 `/run`，`/resume` 已自动完成入队。Worker 从数据库读取 `last_watermark`，从断点继续增量同步。

---

### 10. 强制重置卡死任务

`POST /tsync/clean`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应：

```json
{"code": 1, "msg": "任务锁已解开，僵尸状态已强制重置，可以重新点击执行", "data": null}
```

**使用场景：** 系统崩溃重启后，任务卡死在 `running`/`pending` 状态，前端按钮一直是 `[暂停]` 无法操作。

**`/clean` 执行动作：**

```
1. 删除 Redis 分布式锁 sync_task_lock:{task_id}
2. 删除 Redis 控制信号 task_control:{task_id}
3. 删除数据库中该任务所有 pending/running 状态的日志
```

> 建议在前端任务列表的操作列中加一个 **【解锁】** 按钮，仅在 `run_status` 异常卡死时显示。

**系统也具备自动清理能力：** 每次重启时，会自动将所有 `pending`/`running` 日志标记为 `failed`，避免残留僵尸状态。

---

### 11. 任务列表

`POST /tsync/list`

```json
{"page": 1, "size": 10, "task_name": "用户", "collect_mode": "inc_time", "sort_by": "create_time", "sort_order": "desc"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | ❌ | 页码，默认 1 |
| size | int | ❌ | 每页条数，默认 10 |
| task_name | string | ❌ | 按任务名模糊搜索 |
| collect_mode | string | ❌ | 按采集模式过滤 |
| sort_by | string | ❌ | 排序字段：`create_time`（默认）/ `update_time` / `task_name` |
| sort_order | string | ❌ | 排序方向：`desc`（默认）/ `asc` |

响应：

```json
{
  "code": 1,
  "msg": "获取列表成功",
  "data": {
    "total": 8,
    "items": [
      {
        "id": "550e8400e29b41d4a716446655440000",
        "task_name": "每日同步用户表",
        "source_id": "aabbccdd...",
        "topic_or_table": "users",
        "status": 1,
        "db_type": "mysql",
        "run_status": "running",
        "current_log_id": "log-uuid-xxx",
        "sync_mode": "overwrite",
        "collect_mode": "inc_time",
        "incremental_column": "update_time",
        "last_watermark": "2026-06-05 12:00:00",
        "remark": "每天凌晨2点",
        "sync_tables": ["users", "orders"],
        "create_time": "2026-06-05T10:00:00",
        "update_time": "2026-06-05T10:00:00"
      },
      {
        "id": "550e8400e29b41d4...",
        "task_name": "Kafka流消费",
        "source_id": "kafka-src-id",
        "status": 1,
        "db_type": "kafka",
        "run_status": "running",
        "current_log_id": null
      }
    ]
  }
}
```

| run_status | 含义 | 触发条件 | 前端按钮状态 |
|-----------|------|----------|------------|
| `idle` | 空闲 | 没有任何日志，或最近一次日志是 `success`/`failed`/`cancelled` | 🔵 **[执行]** |
| `pending` | 排队中 | API 已下发，但 Worker 尚未拿到锁 | ⏳ 按钮全部置灰 |
| `running` | 运行中 | Worker 已获取锁（常规任务）或 Kafka Consumer 正在消费 | 🟡 **[暂停]** + **[取消]** |
| `paused` | 已暂停 | 用户点击暂停，引擎在当前批次后中断 | 🟠 **[恢复]** |
| `cancelled` | 已取消 | 用户点击取消，引擎立即终止 | 自动变回 `idle` |
| `stopped` | 已停止 | **仅 Kafka 任务**，Consumer 未在运行 | 🔵 **[启动]** |
| `success` | 已完成 | 最近一次执行成功 | 自动变回 `idle` |
| `failed` | 已失败 | 最近一次执行失败 | 自动变回 `idle` |

**`run_status` 判定逻辑（后端）：**

```
第一步：查数据源类型 (source_type_map)
  ↓
  db_type == "kafka" ?
    ├─ 是 → 直接查 kafka_manager.status() 内存状态
    │       ├─ running → "running"
    │       └─ stopped → "stopped"
    └─ 否 → 常规任务
            ├─ 查 Redis 锁 sync_task_lock:{task_id}
            │   └─ 存在 → "running"（即使 DB 日志已结束）
            └─ 锁不存在 → 查最新 TaskLog
                ├─ pending/running/paused/cancelled → 直接用
                └─ success/failed → "idle"
```

> `db_type` 由后端批量查询 DataSource 表后动态注入，前端无需额外请求。`current_log_id` 仅对常规任务有效（Kafka 常驻消费无日志 ID 概念）。

---

### 12. 任务详情

`POST /tsync/detail`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应同列表中单条 item 结构。

---

### 13. 仪表盘统计

`POST /tsync/dashboard`

无参数。

```json
{}
```

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "total_tasks": 12,
    "active_tasks": 8,
    "today_records": 56000,
    "success_rate": 92.5
  }
}
```

| 字段 | 说明 |
|------|------|
| total_tasks | 任务总数 |
| active_tasks | 启用中的任务数 |
| today_records | 今日同步总条数 |
| success_rate | 今日成功率（百分比） |

---

### 14. 文件同步记录查询

`POST /tsync/record/list`

查询 OSS / FTP 任务的**文件级**同步明细——每个文件是否下载成功、MD5 是否变化（跳过）、解析了多少行。后端根据任务类型自动路由到 `oss_file_record` 或 `ftp_file_record` 表。

```json
{
  "task_id": "550e8400e29b41d4a716446655440000",
  "file_type": "csv",
  "page": 1,
  "page_size": 10
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 UUID（32位）。仅支持 `oss` / `ftp` 类型 |
| file_type | string | ❌ | 按文件类型过滤：`csv` / `json` / `yaml` / `xlsx` / `xml` / `binary` |
| page | int | ❌ | 页码，默认 `1` |
| page_size | int | ❌ | 每页条数，默认 `10` |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "total": 156,
    "page": 1,
    "page_size": 10,
    "items": [
      {
        "id": "a1b2c3d4...",
        "file_name": "report_202606.csv",
        "file_path": "reports/2026/06/report_202606.csv",
        "file_size": 1048576,
        "md5": "d41d8cd98f00b204e9800998ecf8427e",
        "file_type": "csv",
        "is_parsed": 1,
        "parsed_rows": 5000,
        "create_time": "2026-06-17 10:30:00"
      }
    ]
  }
}
```

| 响应字段 | 类型 | 说明 |
|----------|------|------|
| file_name | string | 文件名（提取自路径末段） |
| file_path | string | 远程路径：OSS=object_key，FTP=remote_path |
| file_size | int | 文件大小（字节） |
| md5 | string | 文件 MD5 哈希，用于增量去重判断 |
| file_type | string | 文件类型标识 |
| is_parsed | int | `0`=仅下载未解析 `1`=已解析入库 |
| parsed_rows | int | 解析写入的行数 |
| create_time | string | 下载时间 |

**典型使用场景：**

```
1. OSS 批量采集任务执行完毕 → 前端轮询 /tasklog/detail 拿到最终状态
2. 自动或用户手动打开「文件明细」面板 → 调 /record/list 分页展示每条文件记录
3. 前端表格可直接渲染：
   - file_name 列，可点击跳转
   - file_size 列，格式化为 KB/MB
   - is_parsed=1 → 绿色徽章"已解析"；=0 → 灰色"仅下载"
   - parsed_rows 列展示解析行数
   - md5 列可 hover 查看完整哈希
```

---

### 15. 数据生命周期管理（DLM）

> ⚠️ **分支状态：** 此功能目前在 `feature/clean` 分支，尚未合并 `master`。数据库需执行 `ALTER TABLE sys_collect_task ADD COLUMN ...` 后方可使用（SQL 见本章末尾）。

平台支持两种数据清理模式：**手动清理**（大扫除）和**定时自动清理**（扫地机器人）。清理操作覆盖三个层面：采集数据表、元数据日志（`ftp_file_record` / `oss_file_record`）、本地物理文件。

---

#### 15.1 手动清理（大扫除模式）

`POST /tsync/clean`

用户在前端点击"清理数据"按钮，选择清理方式，后台即时执行。

```json
// TRUNCATE — 清空表数据，保留表结构
{
  "task_id": "550e8400e29b41d4a716446655440000",
  "action": "truncate",
  "clean_files": true
}

// DROP — 彻底删除整张表
{
  "task_id": "550e8400e29b41d4a716446655440000",
  "action": "drop",
  "clean_files": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 UUID（32位） |
| action | string | ✅ | `truncate`=清空数据保留结构 / `drop`=删除整张表 |
| clean_files | bool | ❌ | 是否同时清理本地下载缓存文件，默认 `true` |

响应：

```json
{
  "code": 1,
  "msg": "清理完成",
  "data": {
    "tables_cleaned": [
      {"status": "success", "action": "truncate", "table": "ftp_batch_data"}
    ],
    "file_records_deleted": 156,
    "local_files_deleted": 52,
    "task_id": "550e8400e29b41d4a716446655440000",
    "cleaned_at": "2026-06-22T15:30:00"
  }
}
```

**三层清理联动：**

```
POST /tsync/clean
  ├─ 1. 解析目标表 → TRUNCATE 或 DROP
  │     └─ 动态表名场景：自动扫描采集库 ftp_*/oss_* 前缀，防止遗漏
  ├─ 2. 清理 ftp_file_record + oss_file_record 元数据日志
  └─ 3. 删除 ftp_files/{task_id}/ 和 data/oss_files/{task_id}/ 本地缓存
```

---

#### 15.2 定时自动清理（扫地机器人模式）

用户在创建/编辑任务时勾选"开启数据生命周期管理"，配置保留策略和清理时间。后台 `APScheduler` + `ARQ Worker` 自动执行，无需人工干预。

**任务创建时配置清理策略：**

```json
POST /tsync/add
{
  "task_name": "每日传感器日志",
  "...": "...",
  "clean_policy": "by_days",
  "clean_keep_days": 30,
  "clean_cron": "0 3 * * *"
}
```

**清理策略字段（新增）：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| clean_policy | string | ❌ | `"none"` | 清理策略：`none`=不清理 / `by_days`=按天保留 / `by_count`=按条数保留 |
| clean_keep_days | int | ❌ | — | `by_days` 模式：保留最近 N 天的数据 |
| clean_keep_count | int | ❌ | — | `by_count` 模式：保留最新 N 条数据 |
| clean_cron | string | ❌ | — | 自动清理的 Cron 表达式（如 `"0 3 * * *"` 每天凌晨 3 点） |

> **注意：** `clean_cron` 会在 API 层做格式合法性校验，非法表达式（如 `* * * * * *`）创建时直接拦截。

**两种保留策略对比：**

| 策略 | clean_policy | 依赖字段 | 工作原理 |
|------|-------------|----------|----------|
| 按天保留 | `"by_days"` | `clean_keep_days` + `clean_cron` | `DELETE WHERE collected_at < now() - N天` |
| 按条数保留 | `"by_count"` | `clean_keep_count` + `clean_cron` | 子查询找出第 N 条的 `collected_at` 边界，删除更早的数据 |

**定时清理完整链路：**

```
APScheduler(clean_cron 到点)
  → trigger_clean_job(task_id)
    → ARQ enqueue_job('run_clean_job', task_id)
      → Worker.run_clean_job
        → 读 clean_policy / keep_days / keep_count
        → CleanService.clean_task_data()
          ├─ DELETE FROM table WHERE collected_at < cutoff
          ├─ 删 ftp_file_record / oss_file_record
          └─ 删本地文件目录
```

**前端 UI 建议：**

```
任务创建/编辑表单底部新增「数据生命周期管理」区域：
  ┌─────────────────────────────────────────┐
  │ ☐ 开启数据生命周期管理                   │
  │   保留策略: [按天保留 ▼]                 │
  │   保留天数: [30]                         │
  │   清理时间: [每天 03:00 ▼]               │
  └─────────────────────────────────────────┘

任务列表操作列新增「清理数据」按钮：
  点击 → 弹出确认对话框 → 选择 truncate / drop → 执行
```

---

#### 15.3 数据库变更 SQL

```sql
-- 清理策略字段
ALTER TABLE sys_collect_task
    ADD COLUMN IF NOT EXISTS clean_policy      VARCHAR(20),
    ADD COLUMN IF NOT EXISTS clean_keep_days   INTEGER,
    ADD COLUMN IF NOT EXISTS clean_keep_count  INTEGER,
    ADD COLUMN IF NOT EXISTS clean_cron        VARCHAR(50);

-- 已有采集表补 collected_at 列（DLM 按天/按条数删除必需）
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND (tablename LIKE 'ftp_%' OR tablename LIKE 'oss_%'
            OR tablename LIKE 'mq_%' OR tablename LIKE 'kafka_%'
            OR tablename LIKE 'api_%' OR tablename LIKE 'socket_%'
            OR tablename LIKE 'mqtt_%' OR tablename LIKE 'rabbitmq_%'
            OR tablename LIKE 'snmp_%')
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name=r.tablename
              AND column_name='collected_at'
        ) THEN
            EXECUTE format('ALTER TABLE %I ADD COLUMN collected_at VARCHAR(30)', r.tablename);
        END IF;
    END LOOP;
END $$;
```

---

## 三、任务执行日志 `/tasklog`

### 1. 日志列表

`POST /tasklog/task-list`

```json
{"task_id": "550e8400e29b41d4a716446655440000", "page": 1, "size": 10, "status": "success", "task_name": "同步", "sort_by": "start_time", "sort_order": "desc"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ❌ | 按任务 UUID 过滤，不传则查全量日志 |
| task_name | string | ❌ | 按任务名模糊搜索 |
| page | int | ❌ | 页码，默认 1 |
| size | int | ❌ | 每页条数，默认 10 |
| status | string | ❌ | 过滤：`pending` / `running` / `success` / `failed` / `paused` / `cancelled` |
| sort_by | string | ❌ | 排序字段：`start_time`（默认）/ `end_time` / `task_name` |
| sort_order | string | ❌ | 排序方向：`desc`（默认）/ `asc` |

响应：

```json
{
  "code": 1,
  "msg": "获取日志成功",
  "data": {
    "total": 30,
    "items": [
      {
        "id": "aabbccdd...",
        "task_id": "550e8400...",
        "task_name": "每日同步用户表",
        "status": "success",
        "start_time": "2026-06-05T02:00:00",
        "end_time": "2026-06-05T02:03:25",
        "tables_synced": 2,
        "total_records": 15000,
        "error_msg": null,
        "create_time": "2026-06-05T02:00:00"
      },
      {
        "id": "eeff0011...",
        "task_id": "550e8400...",
        "task_name": "每日同步用户表",
        "status": "failed",
        "start_time": "2026-06-04T02:00:00",
        "end_time": "2026-06-04T02:00:15",
        "tables_synced": 0,
        "total_records": 0,
        "error_msg": "Connection refused",
        "create_time": "2026-06-04T02:00:00"
      }
    ]
  }
}
```

---

### 2. 日志详情

`POST /tasklog/detail`

```
POST /tasklog/detail?log_id=aabbccdd...
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| log_id | string (query) | ✅ | 日志记录 UUID |

响应：

```json
{
  "code": 1,
  "msg": "获取日志详情成功",
  "data": {
    "id": "aabbccdd...",
    "task_id": "550e8400...",
    "task_name": "每日同步用户表",
    "status": "success",
    "start_time": "2026-06-05T02:00:00",
    "end_time": "2026-06-05T02:03:25",
    "tables_synced": 2,
    "total_records": 17000,
    "error_msg": null,
    "create_time": "2026-06-05T02:00:00",
    "detail_json": {
      "sync_mode": "overwrite",
      "collect_mode": "inc_time",
      "incremental_column": "update_time",
      "source_type": "mysql",
      "source_db": "factory_db",
      "watermark_before": "2026-06-01 00:00:00",
      "watermark_after": "2026-06-05 02:03:20",
      "tables": [
        {"name": "users", "records": 5000, "cost_seconds": 1.23, "high_watermark": "2026-06-05 02:02:00"},
        {"name": "orders", "records": 12000, "cost_seconds": 2.45, "high_watermark": "2026-06-05 02:03:18"}
      ]
    }
  }
}
```


---

## 四、表级同步日志 `/execlog`

### 1. 表级日志列表

`POST /execlog/list`

查询每张表的同步执行记录（血缘映射流水）。

```json
{"task_id": "550e8400...", "page": 1, "size": 10}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ❌ | 按任务 ID 过滤 |
| log_id | string | ❌ | 按某次执行的 TaskLog ID 过滤 |
| target_table | string | ❌ | 按目标表名模糊搜索 |
| status | string | ❌ | 按状态过滤：`success` / `failed` |
| page | int | ❌ | 页码，默认 1 |
| size | int | ❌ | 每页条数，默认 10 |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "total": 5,
    "items": [
      {
        "id": "aabbccdd...",
        "log_id": "eeff0011...",
        "task_id": "550e8400...",
        "source_table": "users",
        "target_table": "users",
        "sync_mode": "overwrite",
        "collect_mode": "inc_time",
        "records_count": 5000,
        "cost_seconds": 1.23,
        "watermark": "2026-06-06 10:02:00",
        "status": "success",
        "error_msg": null,
        "create_time": "2026-06-06T10:00:00"
      }
    ]
  }
}
```


---

## 五、MongoDB 同步专项

> MongoDB 源库的 `db_type` 固定为 `"mongodb"`。目标库通过 `target_type` 控制：默认写入 PostgreSQL，也可指定写入另一个 MongoDB。

### 1. 创建 MongoDB 数据源

```json
{
  "name": "生产MongoDB",
  "type": "mongodb",
  "host": "192.168.1.100",
  "port": 27017,
  "db_name": "factory_db",
  "username": "admin",
  "password": "123456"
}
```

> 测试连接、获取集合列表、获取集合字段详情均支持 MongoDB 类型。

---

### 2. MongoDB → PostgreSQL（默认）

最简写法，目标库默认为 PostgreSQL，自动写入本地 PG 的 `dataflux` 库。

```json
{
  "task_name": "Mongo同步到PG",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["users", "orders"],
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| target_type | 不传 | 默认 `"postgresql"` |
| target_host/port/db_name | 不传 | 不需要，目标是本地 PG |
| sync_tables | `["users","orders"]` | 指定同步哪些集合 |
| collect_mode | `"full"` | 全量抽取 |

**目标表结构：** 每个集合在 PG 中生成一张固定结构的表：

| 列名 | 类型 | 说明 |
|------|------|------|
| `_id` | TEXT PRIMARY KEY | MongoDB 文档的 `_id`（转为字符串） |
| `raw_doc` | JSON | 完整文档（ObjectId/datetime 已序列化为字符串） |

---

### 3. MongoDB → MongoDB（同机对拷）

目标 MongoDB 在同一台机器上，只需指定 `target_type: "mongodb"`，其他 target 字段自动用源库连接信息兜底。

```json
{
  "task_name": "Mongo同机对拷",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["a1"],
  "target_type": "mongodb",
  "collect_mode": "full"
}
```

| 字段 | 值 | 默认兜底 |
|------|------|----------|
| target_type | `"mongodb"` | 必传 |
| target_host | 不传 | 自动用源库 host |
| target_port | 不传 | 自动用源库 port |
| target_db_name | 不传 | 自动用 `.env` 中的 `MONGO_DB_NAME` |
| target_username | 不传 | 自动用源库 username |
| target_password | 不传 | 自动用源库 password |

**写入策略：** 按 `_id` 匹配，存在则替换，不存在则插入（`ReplaceOne + upsert`）。

---

### 4. MongoDB → MongoDB（跨机同步）

目标 MongoDB 在另一台服务器上，需要显式指定所有 target 连接信息。

```json
{
  "task_name": "Mongo跨机同步",
  "source_id": "源端MongoDB数据源ID",
  "sync_tables": ["users", "logs"],
  "target_type": "mongodb",
  "target_host": "192.168.2.200",
  "target_port": 27017,
  "target_username": "admin",
  "target_password": "654321",
  "target_db_name": "backup_db",
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| target_type | `"mongodb"` | 必传 |
| target_host | `"192.168.2.200"` | 目标 MongoDB 地址 |
| target_port | `27017` | 目标 MongoDB 端口 |
| target_username | `"admin"` | 目标 MongoDB 账号 |
| target_password | `"654321"` | 目标 MongoDB 密码 |
| target_db_name | `"backup_db"` | 目标 MongoDB 数据库名 |

---

### 5. MongoDB 增量采集（inc_id）

基于 `_id`（ObjectId）增量，适合文档自动生成 `_id` 的场景。

```json
{
  "task_name": "Mongo增量同步",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["events"],
  "collect_mode": "inc_id"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_id"` | 按 `_id` 增量 |
| last_watermark | 不传 | 首次全量，之后自动记录 ObjectId 水位线 |

**原理：** 首次全量抽取，完成后水位线记录为最后一条文档的 `_id`（ObjectId 字符串）。下次执行时自动过滤 `_id > 上次水位线`。

---

### 6. MongoDB 增量采集（inc_time）

基于时间字段增量，适合文档中有 `update_time`、`created_at` 等时间字段的场景。

```json
{
  "task_name": "Mongo时间增量",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["orders"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_time"` | 按时间字段增量 |
| incremental_column | `"update_time"` | 源文档中的时间字段名 |
| last_watermark | 不传 | 首次全量，之后自动记录最大时间值 |

**原理：** 过滤 `update_time > 上次水位线`，水位线支持 ISO 8601 字符串和 datetime 类型自动解析。

---

### 7. MongoDB 整库同步（不指定集合）

不传 `sync_tables`，自动同步源库所有集合（排除 `system.*`）。

```json
{
  "task_name": "Mongo整库同步",
  "source_id": "你的MongoDB数据源ID",
  "target_type": "mongodb",
  "collect_mode": "full"
}
```

---

### 8. MongoDB 集合名映射

MongoDB 同样支持 `table_mapping`，将源集合名映射为目标集合名（或目标表名）。

**MongoDB → PG 改表名：**

```json
{
  "task_name": "Mongo到PG改名",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["users", "orders"],
  "table_mapping": {"users": "t_mongo_users", "orders": "t_mongo_orders"},
  "target_type": "postgresql",
  "collect_mode": "full"
}
```

**MongoDB → MongoDB 改集合名：**

```json
{
  "task_name": "Mongo对拷改名",
  "source_id": "你的MongoDB数据源ID",
  "sync_tables": ["a1", "a2"],
  "table_mapping": {"a1": "backup_a1", "a2": "backup_a2"},
  "target_type": "mongodb",
  "collect_mode": "full"
}
```

---

### 9. MongoDB 自定义 SQL（仅限目标为 PG）

MongoDB 不支持 SQL 查询，但可以用 `collect_mode: "custom_sql"` 配合 `target_table` 将自定义查询结果写入 PG 指定表。

> 注意：`custom_sql` 模式对 MongoDB 无效（MongoDB 没有 SQL），此模式仅适用于关系型源库。

---

### collect_mode 兼容矩阵

| collect_mode | 源库 → PG | 源库 → MongoDB | 说明 |
|--------------|-----------|----------------|------|
| `full` | ✅ | ✅ | 全量抽取，无条件过滤 |
| `inc_id` | ✅ 自增列增量 | ✅ ObjectId 增量 | PG 模式需要 `incremental_column`；MongoDB 模式自动用 `_id`，不需要传 |
| `inc_time` | ✅ 时间戳增量 | ✅ 时间戳增量 | 都需要传 `incremental_column`（如 `update_time`） |
| `custom_sql` | ✅ | ❌ 不支持 | MongoDB 没有 SQL，仅限关系型源库 |

**各模式详细参数：**

| collect_mode | incremental_column | last_watermark | 效果 |
|--------------|-------------------|----------------|------|
| `full` | 不传 | 不传 | 每次全量抽取 |
| `inc_id`（PG） | 传（如 `"id"`） | 不传 | 首次全量，之后 `id > 上次水位线` |
| `inc_id`（MongoDB） | 不传 | 不传 | 首次全量，之后 `_id > 上次ObjectId` |
| `inc_time` | 传（如 `"update_time"`） | 不传 | 首次全量，之后 `update_time > 上次水位线` |
| `custom_sql` | 不传 | 不传 | 执行自定义 SQL，结果写入 `target_table` |

> `last_watermark` 一般不手动传，系统在每次执行后自动记录并回写。

---

### target_* 字段默认值汇总

| 字段 | 用户没传时的默认值 | 适用场景 |
|------|-------------------|----------|
| target_type | `"postgresql"` | 默认写入本地 PG |
| target_host | 源库的 host | 同机 MongoDB 对拷 |
| target_port | 源库的 port | 同机 MongoDB 对拷 |
| target_username | 源库的 username | 同机 MongoDB 对拷 |
| target_password | 源库的 password | 同机 MongoDB 对拷 |
| target_db_name | `.env` 中的 `MONGO_DB_NAME` | 默认写入 `dataflux` 库 |



---

## 六、DM(达梦) 同步专项

> 达梦数据库基于 Oracle 架构，默认大写存储表名和列名，使用 `username` 作为 schema。同步引擎已做全面适配，前端传参大小写均可。

### 1. 创建达梦数据源

```json
{
  "name": "生产达梦",
  "type": "dm",
  "host": "192.168.1.100",
  "port": 5236,
  "db_name": "SYSDBA",
  "username": "SYSDBA",
  "password": "SYSDBA123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"dm"` |
| host | string | ✅ | 达梦服务器地址 |
| port | int | ✅ | 达梦端口，默认 `5236` |
| db_name | string | ✅ | 数据库名（实际不参与连接，仅做标识） |
| username | string | ✅ | 用户名（同时作为 schema 名） |
| password | string | ✅ | 密码 |

> **注意：** 达梦连接不需要 `db_name` 参数，连接串为 `dm+dmPython://user:pwd@host:port`。但前端仍需传 `db_name` 用于标识和展示。

---

### 2. 达梦 → PostgreSQL（全量同步）

最简写法，前端只需指定源表名：

```json
{
  "task_name": "达梦全量同步",
  "source_id": "你的达梦数据源ID",
  "sync_tables": ["DEVICE", "USER_INFO"],
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| sync_tables | `["DEVICE","USER_INFO"]` | 表名大小写均可，引擎自动匹配物理名 |
| collect_mode | `"full"` | 全量抽取 |
| target_type | 不传 | 默认 `"postgresql"` |

**目标表结构：**
- 所有列自动转小写（`DEVICE_CODE` → `device_code`）
- 所有列默认 `nullable=True`（避免源库 NULL 值导致插入失败）
- MySQL 风格的 collation（如 `utf8mb3_general_ci`）自动剥离
- 达梦 `VARCHAR2` → PG `VARCHAR`，`NUMBER` → `NUMERIC`，`CLOB` → `TEXT`

---

### 3. 达梦增量采集（inc_id）

基于自增列增量：

```json
{
  "task_name": "达梦自增列增量",
  "source_id": "你的达梦数据源ID",
  "sync_tables": ["ORDERS"],
  "collect_mode": "inc_id",
  "incremental_column": "id"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_id"` | 按自增列增量 |
| incremental_column | `"id"` | 源表中的自增列名（大小写均可，引擎自动转大写匹配达梦物理列名） |
| last_watermark | 不传 | 首次全量，之后自动记录水位线 |

**原理：** 首次全量，完成后水位线记录为最后一条的 `id` 值。下次执行时自动过滤 `ID > 上次水位线`。

---

### 4. 达梦增量采集（inc_time）

基于时间字段增量：

```json
{
  "task_name": "达梦时间增量",
  "source_id": "你的达梦数据源ID",
  "sync_tables": ["ORDERS"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_time"` | 按时间字段增量 |
| incremental_column | `"update_time"` | 源表中的时间字段名（大小写均可） |
| last_watermark | 不传 | 首次全量，之后自动记录最大时间值 |

**原理：** 过滤 `UPDATE_TIME > 上次水位线`，水位线支持 datetime 和字符串自动解析。

---

### 5. 达梦整库同步（不指定表）

不传 `sync_tables`，自动同步用户 schema 下所有表：

```json
{
  "task_name": "达梦整库同步",
  "source_id": "你的达梦数据源ID",
  "collect_mode": "full"
}
```

> 引擎自动用 `inspect` 获取 `username.upper()` schema 下的全部表名。

---

### 6. 达梦表名映射

支持将达梦源表名映射到 PG 目标表名：

```json
{
  "task_name": "达梦改名同步",
  "source_id": "你的达梦数据源ID",
  "sync_tables": ["DEVICE", "USER_INFO"],
  "table_mapping": {"DEVICE": "t_device", "USER_INFO": "t_user_info"},
  "collect_mode": "full"
}
```

| 源表名（达梦） | 目标表名（PG） | 说明 |
|----------------|----------------|------|
| `DEVICE` | `t_device` | 映射生效 |
| `USER_INFO` | `t_user_info` | 映射生效 |

> 映射匹配大小写不敏感，`DEVICE`、`device`、`Device` 都能匹配到。

---

### 7. 达梦 + custom_sql 模式

用自定义 SQL 从达梦抽取数据，写入 PG 指定表：

```json
{
  "task_name": "达梦SQL抽取",
  "source_id": "你的达梦数据源ID",
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM SYSDBA.DEVICE WHERE STATUS = '1'",
  "topic_or_table": "active_devices"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"custom_sql"` | 自定义 SQL 模式 |
| custom_sql | `"SELECT ..."` | 在达梦源库执行的 SQL |
| topic_or_table | `"active_devices"` | PG 目标库中已存在的表名（必填） |

> **注意：** SQL 中的表名和列名必须使用达梦的物理名（通常是大写）。

---

### 达梦适配机制汇总

| 适配项 | 处理方式 |
|--------|----------|
| 连接串 | `dm+dmPython://user:pwd@host:port`（不含 database） |
| schema | 反射时自动注入 `schema=username.upper()` |
| 表名大小写 | `inspect` 查物理名，前端传 `DEVICE` 或 `device` 均可 |
| 列名大小写 | 反射后自动转小写，行数据用大写/小写双匹配 |
| collation | 自动剥离 `utf8mb3_general_ci` 等 PG 不支持的排序规则 |
| NOT NULL | 目标表所有列强制 `nullable=True`，避免源库 NULL 值插入失败 |
| `VARCHAR2` | 归一化为 `VARCHAR` |
| `NUMBER` | 归一化为 `NUMERIC` |
| `CLOB` | 归一化为 `TEXT` |
| `DATE`/`TIMESTAMP` | 归一化为 `TIMESTAMP` |
| `DEFAULT SYSDATE` | 自动剥离 Python 侧默认值 |
| connect_args | dmPython 不支持超时参数，连接时不传 |



---

## 七、Oracle 同步专项

> Oracle 数据库默认大写存储表名和列名，使用 `username` 作为 schema。同步引擎已做全面适配，默认使用 service_name 方式连接，也支持 SID 模式。前端传参大小写均可。

### 1. 创建 Oracle 数据源

```json
{
  "name": "生产Oracle",
  "type": "oracle",
  "host": "192.168.1.100",
  "port": 1521,
  "db_name": "ORCLPDB1",
  "username": "scott",
  "password": "tiger123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"oracle"` |
| host | string | ✅ | Oracle 服务器地址 |
| port | int | ✅ | Oracle 端口，默认 `1521` |
| db_name | string | ✅ | 服务名 (service_name)，如 `ORCLPDB1`。传了则走 service_name 模式 |
| username | string | ✅ | 用户名（同时作为 schema 名） |
| password | string | ✅ | 密码 |

> **注意：** `db_name` 会被用作 Oracle 的 `service_name` 参数。连接串格式为 `oracle+oracledb://user:pwd@host:port/?service_name=xxx`。

---

### 2. Oracle 连接模式（service_name vs SID）

Oracle 默认使用 **service_name** 模式（通过 `db_name` 指定）。如果需要使用 **SID** 模式，可通过 `config_json` 配置：

```json
{
  "name": "老版Oracle-SID模式",
  "type": "oracle",
  "host": "192.168.1.100",
  "port": 1521,
  "db_name": "",
  "username": "scott",
  "password": "tiger123",
  "config_json": {"sid": "ORCL"}
}
```

| 场景 | db_name | config_json | 连接串格式 |
|------|---------|-------------|-----------|
| service_name 模式（默认） | `"ORCLPDB1"` | 不传 | `oracle+oracledb://.../?service_name=ORCLPDB1` |
| SID 模式 | `""` | `{"sid":"ORCL"}` | `oracle+oracledb://.../ORCL` |

> **建议：** 新版本 Oracle（12c+）优先使用 service_name 模式。如果数据源保存后"测试连接"失败或"获取表列表"为空，请检查 DBA 确认应该填 service_name 还是 SID。

---

### 3. Oracle → PostgreSQL（全量同步）

最简写法，前端只需指定源表名：

```json
{
  "task_name": "Oracle全量同步",
  "source_id": "你的Oracle数据源ID",
  "sync_tables": ["EMPLOYEES", "DEPARTMENTS"],
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| sync_tables | `["EMPLOYEES","DEPARTMENTS"]` | 表名大小写均可，引擎自动匹配 Oracle 物理大写名 |
| collect_mode | `"full"` | 全量抽取 |
| target_type | 不传 | 默认 `"postgresql"` |

**目标表结构：**
- 所有列自动转小写（`EMPLOYEE_ID` → `employee_id`）
- 所有列默认 `nullable=True`（避免源库 NOT NULL 约束导致 NULL 值插入失败）
- Oracle `VARCHAR2` → PG `VARCHAR`，`NUMBER` → `NUMERIC`/`INTEGER`，`CLOB` → `TEXT`，`BLOB` → `BYTEA`
- Oracle `DATE`/`TIMESTAMP` → PG `TIMESTAMP`
- Oracle 默认值函数（`SYSDATE`、`SYS_GUID()`、`SYSTIMESTAMP` 等）自动剥离

---

### 4. Oracle 增量采集（inc_id）

基于自增列增量：

```json
{
  "task_name": "Oracle自增列增量",
  "source_id": "你的Oracle数据源ID",
  "sync_tables": ["ORDERS"],
  "collect_mode": "inc_id",
  "incremental_column": "id"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_id"` | 按自增列增量 |
| incremental_column | `"id"` | 源表中的自增列名（大小写均可，引擎自动转大写匹配 Oracle 物理列名） |
| last_watermark | 不传 | 首次全量，之后自动记录水位线 |

**原理：** 首次全量抽取，完成后水位线记录为最后一条的 `id` 值。下次执行时自动过滤 `ID > 上次水位线`。

---

### 5. Oracle 增量采集（inc_time）

基于时间字段增量：

```json
{
  "task_name": "Oracle时间增量",
  "source_id": "你的Oracle数据源ID",
  "sync_tables": ["ORDERS"],
  "collect_mode": "inc_time",
  "incremental_column": "update_time"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_time"` | 按时间字段增量 |
| incremental_column | `"update_time"` | 源表中的时间字段名（大小写均可） |
| last_watermark | 不传 | 首次全量，之后自动记录最大时间值 |

**原理：** 过滤 `UPDATE_TIME > 上次水位线`。水位线同时支持 `datetime` 对象和 `VARCHAR2` 字符串格式的自动解析。

---

### 6. Oracle 整库同步（不指定表）

不传 `sync_tables`，自动同步用户 schema 下所有表：

```json
{
  "task_name": "Oracle整库同步",
  "source_id": "你的Oracle数据源ID",
  "collect_mode": "full"
}
```

> 引擎自动用 `inspect` 获取 `username.upper()` schema 下的全部表名。

---

### 7. Oracle 表名映射

支持将 Oracle 源表名映射到 PG 目标表名：

```json
{
  "task_name": "Oracle改名同步",
  "source_id": "你的Oracle数据源ID",
  "sync_tables": ["EMPLOYEES", "DEPARTMENTS"],
  "table_mapping": {"EMPLOYEES": "t_employees", "DEPARTMENTS": "t_departments"},
  "collect_mode": "full"
}
```

| 源表名（Oracle） | 目标表名（PG） | 说明 |
|----------------|----------------|------|
| `EMPLOYEES` | `t_employees` | 映射生效 |
| `DEPARTMENTS` | `t_departments` | 映射生效 |

> 映射匹配大小写不敏感，`EMPLOYEES`、`employees`、`Employees` 都能匹配到。

---

### 8. Oracle + custom_sql 模式

用自定义 SQL 从 Oracle 抽取数据，写入 PG 指定表：

```json
{
  "task_name": "Oracle SQL抽取",
  "source_id": "你的Oracle数据源ID",
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM SCOTT.EMPLOYEES WHERE STATUS = 'ACTIVE'",
  "topic_or_table": "active_employees"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"custom_sql"` | 自定义 SQL 模式 |
| custom_sql | `"SELECT ..."` | 在 Oracle 源库执行的 SQL |
| topic_or_table | `"active_employees"` | PG 目标库中已存在的表名（必填） |

> **注意：** SQL 中的表名和列名必须使用 Oracle 的物理名（通常是大写）。如果跨 schema 查询，需要写完整限定名如 `SCOTT.EMPLOYEES`。

---

### Oracle 适配机制汇总

| 适配项 | 处理方式 |
|--------|----------|
| 连接串（service_name） | `oracle+oracledb://user:pwd@host:port/?service_name=xxx`（默认） |
| 连接串（SID） | `oracle+oracledb://user:pwd@host:port/SID`（需 `config_json.sid`） |
| schema | 反射时自动注入 `schema=username.upper()` |
| 表名大小写 | `inspect` 查物理名，前端传 `EMPLOYEES` 或 `employees` 均可 |
| 列名大小写 | 反射后自动转小写，行数据用大写/小写双匹配 |
| NOT NULL | 目标表所有列强制 `nullable=True`，避免源库 NULL 值插入失败 |
| `VARCHAR2` / `NVARCHAR2` | 归一化为 `VARCHAR` / `TEXT` |
| `NUMBER` | 精度 scale=0 → `INTEGER`；其他 → `NUMERIC(precision, scale)` |
| `CLOB` / `NCLOB` | 归一化为 `TEXT` |
| `BLOB` / `RAW` | 归一化为 `BYTEA` |
| `DATE` / `TIMESTAMP` | 归一化为 `TIMESTAMP` |
| `INTERVAL` | 归一化为 `TEXT` |
| `FLOAT` / `BINARY_FLOAT` / `BINARY_DOUBLE` | 归一化为 `NUMERIC` |
| `SYSDATE` / `SYS_GUID()` / `SYSTIMESTAMP` | 自动剥离默认值函数 |
| LOB 对象 | 自动 `.read()` 读取内容 |
| 自增列 (`autoincrement`) | 自动剥离，防止 PG 建表歧义 |



---

## 八、SQL Server 同步专项

> SQL Server 数据库保留原始列名大小写，默认端口 `1433`。同步引擎支持默认实例和命名实例两种连接方式，以及 Windows 认证和 SQL Server 认证。前端传参大小写均可（SQL Server 默认不区分大小写）。

### 1. 创建 SQL Server 数据源

```json
{
  "name": "生产SQLServer",
  "type": "sqlserver",
  "host": "192.168.1.100",
  "port": 1433,
  "db_name": "FactoryDB",
  "username": "sa",
  "password": "YourPassword123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"sqlserver"` |
| host | string | ✅ | SQL Server 服务器地址 |
| port | int | ✅ | 端口，默认实例 `1433` |
| db_name | string | ✅ | 数据库名 |
| username | string | ✅ | 登录用户名 |
| password | string | ✅ | 登录密码 |

> **注意：** 连接串格式为 `mssql+pymssql://user:pwd@host:port/db?charset=utf8`。

---

### 2. SQL Server 命名实例连接

如果 SQL Server 使用了**非默认的命名实例**（如 `HOST\MSSQLSERVER`），通过 `config_json` 指定实例名：

```json
{
  "name": "SQLServer命名实例",
  "type": "sqlserver",
  "host": "192.168.1.100",
  "port": 1433,
  "db_name": "FactoryDB",
  "username": "sa",
  "password": "YourPassword123",
  "config_json": {"instance": "MSSQLSERVER"}
}
```

| 场景 | config_json | 连接串格式 |
|------|-------------|-----------|
| 默认实例（无命名实例） | 不传 | `mssql+pymssql://...@host:1433/db` |
| 命名实例 | `{"instance":"MSSQLSERVER"}` | `mssql+pymssql://...@host\MSSQLSERVER/db` |

> **注意：** `config_json.instance` 仅在 SQL Server 使用命名实例时才需要填写，绝大多数情况下不需要。

---

### 3. SQL Server → PostgreSQL（全量同步）

最简写法：

```json
{
  "task_name": "SQLServer全量同步",
  "source_id": "你的SQLServer数据源ID",
  "sync_tables": ["Employees", "Orders"],
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| sync_tables | `["Employees","Orders"]` | 表名保持原始大小写即可 |
| collect_mode | `"full"` | 全量抽取 |
| target_type | 不传 | 默认 `"postgresql"` |

**目标表结构：**
- 列名保持原始大小写（如 `EmployeeID` 保持为 `EmployeeID`）
- 所有列默认 `nullable=True`
- SQL Server `NVARCHAR`/`VARCHAR` → PG `VARCHAR`，`VARCHAR(MAX)` → `TEXT`
- SQL Server `INT`/`BIGINT`/`SMALLINT`/`TINYINT` → PG `INTEGER`
- SQL Server `DECIMAL`/`NUMERIC`/`MONEY` → PG `NUMERIC`
- SQL Server `DATETIME`/`DATETIME2`/`SMALLDATETIME` → PG `TIMESTAMP`
- SQL Server `BIT` → PG `BOOLEAN`
- SQL Server `UNIQUEIDENTIFIER` → PG `VARCHAR(36)`
- SQL Server `IMAGE`/`VARBINARY` → PG `BYTEA`
- SQL Server `XML` → PG `TEXT`
- SQL Server 默认值函数（`GETDATE()`、`NEWID()` 等）自动剥离
- SQL Server `IDENTITY` 自增属性自动剥离

---

### 4. SQL Server 增量采集（inc_id）

基于自增列增量：

```json
{
  "task_name": "SQLServer自增列增量",
  "source_id": "你的SQLServer数据源ID",
  "sync_tables": ["Orders"],
  "collect_mode": "inc_id",
  "incremental_column": "OrderID"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_id"` | 按自增列增量 |
| incremental_column | `"OrderID"` | 源表中的自增列名（大小写需与数据库实际一致） |
| last_watermark | 不传 | 首次全量，之后自动记录水位线 |

---

### 5. SQL Server 增量采集（inc_time）

基于时间字段增量：

```json
{
  "task_name": "SQLServer时间增量",
  "source_id": "你的SQLServer数据源ID",
  "sync_tables": ["Orders"],
  "collect_mode": "inc_time",
  "incremental_column": "UpdateTime"
}
```

---

### 6. SQL Server 整库同步（不指定表）

不传 `sync_tables`，自动同步默认 schema（`dbo`）下所有表：

```json
{
  "task_name": "SQLServer整库同步",
  "source_id": "你的SQLServer数据源ID",
  "collect_mode": "full"
}
```

> 引擎自动用 `inspect` 获取数据库的全部用户表名。如果表分布在多个 schema（如 `dbo`、`sales` 等），都会一并反射。

---

### 7. SQL Server 表名映射

支持将 SQL Server 源表名映射到 PG 目标表名：

```json
{
  "task_name": "SQLServer改名同步",
  "source_id": "你的SQLServer数据源ID",
  "sync_tables": ["Employees", "Orders"],
  "table_mapping": {"Employees": "t_employees", "Orders": "t_orders"},
  "collect_mode": "full"
}
```

| 源表名（SQL Server） | 目标表名（PG） | 说明 |
|---------------------|----------------|------|
| `Employees` | `t_employees` | 映射生效 |
| `Orders` | `t_orders` | 映射生效 |

---

### 8. SQL Server + custom_sql 模式

用自定义 SQL 从 SQL Server 抽取数据：

```json
{
  "task_name": "SQLServer SQL抽取",
  "source_id": "你的SQLServer数据源ID",
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM dbo.Employees WHERE Status = 'Active'",
  "topic_or_table": "active_employees"
}
```

> **注意：** SQL 中建议写完整限定名 `dbo.Employees`，避免跨 schema 歧义。

---

### SQL Server 适配机制汇总

| 适配项 | 处理方式 |
|--------|----------|
| 连接串（默认实例） | `mssql+pymssql://user:pwd@host:port/db?charset=utf8` |
| 连接串（命名实例） | `mssql+pymssql://user:pwd@host\instance/db?charset=utf8`（需 `config_json.instance`） |
| schema | 默认使用 `dbo`，无需显式指定 |
| 表名 | 保持原始大小写 |
| 列名 | 保持原始大小写 |
| NOT NULL | 目标表所有列强制 `nullable=True` |
| `NVARCHAR` / `VARCHAR` | 有长度 → `VARCHAR(n)`；`MAX` → `TEXT` |
| `NCHAR` / `CHAR` | 归一化为 `VARCHAR` |
| `TEXT` / `NTEXT` | 归一化为 `TEXT` |
| `INT` / `BIGINT` / `SMALLINT` / `TINYINT` | 归一化为 `INTEGER` |
| `DECIMAL` / `NUMERIC` / `MONEY` / `SMALLMONEY` | 归一化为 `NUMERIC` |
| `FLOAT` / `REAL` | 归一化为 `NUMERIC` |
| `DATETIME` / `DATETIME2` / `SMALLDATETIME` | 归一化为 `TIMESTAMP` |
| `DATE` | 归一化为 `DATE` |
| `TIME` | 归一化为 `TEXT`（PG Time 有时区问题，转文本更安全） |
| `BIT` | 归一化为 `BOOLEAN` |
| `UNIQUEIDENTIFIER` (GUID) | 归一化为 `VARCHAR(36)` |
| `VARBINARY` / `BINARY` / `IMAGE` | 归一化为 `BYTEA` |
| `XML` | 归一化为 `TEXT` |
| `GETDATE()` / `NEWID()` / `SYSDATETIME()` | 自动剥离默认值函数 |
| `IDENTITY` (自增列) | 自动剥离 `autoincrement` 属性 |



---

## 九、SQLite 同步专项

> SQLite 是嵌入式文件数据库，不需要 host/port/用户名/密码。`db_name` 字段填写 `.sqlite3` / `.db` 文件的**绝对路径**。同步引擎基于 Python 内置 `sqlite3` 模块，零额外依赖。

### 1. 创建 SQLite 数据源

```json
{
  "name": "本地SQLite",
  "type": "sqlite",
  "host": "0.0.0.0",
  "port": 0,
  "db_name": "E:/data/mydb.sqlite3",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"sqlite"` |
| host | string | ✅ | 随便填（如 `"0.0.0.0"`），不参与连接 |
| port | int | ✅ | 随便填（如 `0`），不参与连接 |
| db_name | string | ✅ | **数据库文件的绝对路径**，如 `/data/mydb.sqlite3` 或 `E:/data/mydb.sqlite3` |
| username | string | ❌ | 随便填，不参与连接 |
| password | string | ❌ | 随便填，不参与连接 |

> **注意：** SQLite 连接串格式为 `sqlite:///文件绝对路径?timeout=15`。Windows 路径的反斜杠 `\` 会自动转为正斜杠 `/`，无需手动处理。

---

### 2. SQLite → PostgreSQL（全量同步）

```json
{
  "task_name": "SQLite全量同步",
  "source_id": "你的SQLite数据源ID",
  "sync_tables": ["users", "orders"],
  "collect_mode": "full"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| sync_tables | `["users","orders"]` | SQLite 表名保持原始大小写即可 |
| collect_mode | `"full"` | 全量抽取 |
| target_type | 不传 | 默认 `"postgresql"` |

**目标表结构：**
- 列名保持原始大小写
- 所有列默认 `nullable=True`
- SQLite 动态类型归一化：`INT`/`INTEGER`/`BIGINT`/`TINYINT` → PG `INTEGER`
- `TEXT`/`CLOB`/`CHAR`/`VARCHAR(n)` → PG `VARCHAR(n)` 或 `TEXT`
- `REAL`/`FLOAT`/`DOUBLE` → PG `FLOAT`
- `NUMERIC`/`DECIMAL` → PG `NUMERIC`
- `BLOB` → PG `TEXT`（十六进制字符串存储）
- `DATETIME`/`DATE` → PG `TIMESTAMP`/`DATE`
- `BOOLEAN` → PG `BOOLEAN`
- 无类型声明的列（NullType）→ PG `TEXT`
- `CURRENT_TIMESTAMP`/`CURRENT_DATE`/`CURRENT_TIME` 默认值自动剥离
- `INTEGER PRIMARY KEY`（ROWID 别名）的 `autoincrement` 属性自动剥离

---

### 3. SQLite 增量采集（inc_id）

基于自增列增量：

```json
{
  "task_name": "SQLite自增列增量",
  "source_id": "你的SQLite数据源ID",
  "sync_tables": ["orders"],
  "collect_mode": "inc_id",
  "incremental_column": "id"
}
```

| 字段 | 值 | 说明 |
|------|------|------|
| collect_mode | `"inc_id"` | 按自增列增量 |
| incremental_column | `"id"` | 源表中的自增列名 |
| last_watermark | 不传 | 首次全量，之后自动记录水位线 |

---

### 4. SQLite 增量采集（inc_time）

```json
{
  "task_name": "SQLite时间增量",
  "source_id": "你的SQLite数据源ID",
  "sync_tables": ["logs"],
  "collect_mode": "inc_time",
  "incremental_column": "created_at"
}
```

---

### 5. SQLite 整库同步（不指定表）

不传 `sync_tables`，自动同步数据库中所有表：

```json
{
  "task_name": "SQLite整库同步",
  "source_id": "你的SQLite数据源ID",
  "collect_mode": "full"
}
```

> **注意：** SQLite 不支持 `only` 参数反射，引擎采用「全量反射后手动过滤」策略——先反射全部表，再根据 `sync_tables` 移除不需要的表。

---

### 6. SQLite 表名映射

```json
{
  "task_name": "SQLite改名同步",
  "source_id": "你的SQLite数据源ID",
  "sync_tables": ["users", "orders"],
  "table_mapping": {"users": "t_users", "orders": "t_orders"},
  "collect_mode": "full"
}
```

| 源表名（SQLite） | 目标表名（PG） | 说明 |
|-----------------|----------------|------|
| `users` | `t_users` | 映射生效 |
| `orders` | `t_orders` | 映射生效 |

---

### 7. SQLite + custom_sql 模式

用自定义 SQL 从 SQLite 抽取数据：

```json
{
  "task_name": "SQLite SQL抽取",
  "source_id": "你的SQLite数据源ID",
  "collect_mode": "custom_sql",
  "custom_sql": "SELECT * FROM users WHERE status = 'active'",
  "topic_or_table": "active_users"
}
```

---

### SQLite 适配机制汇总

| 适配项 | 处理方式 |
|--------|----------|
| 连接串 | `sqlite:///绝对路径?timeout=15`（不需要 host/port/用户名/密码） |
| 路径兼容 | Windows 反斜杠 `\` 自动转正斜杠 `/` |
| 反射策略 | 全量反射后手动过滤（不支持 `only` 参数） |
| 列名 | 保持原始大小写 |
| NOT NULL | 目标表所有列强制 `nullable=True` |
| `INT` / `INTEGER` / `BIGINT` / `TINYINT` | 归一化为 `INTEGER` |
| `TEXT` / `CLOB` / `CHAR` | 有长度 → `VARCHAR(n)`，无长度 → `TEXT` |
| `VARCHAR(n)` | 保留长度 `VARCHAR(n)` |
| `REAL` / `FLOAT` / `DOUBLE` | 归一化为 `FLOAT` |
| `NUMERIC` / `DECIMAL` | 归一化为 `NUMERIC(precision, scale)` |
| `BLOB` | 归一化为 `TEXT`（hex 字符串） |
| `DATETIME` | 归一化为 `TIMESTAMP` |
| `DATE` | 归一化为 `DATE` |
| `TIME` | 归一化为 `TIMESTAMP` |
| `BOOLEAN` | 归一化为 `BOOLEAN` |
| 无类型（NullType） | 兜底归一化为 `TEXT` |
| `CURRENT_TIMESTAMP` 等 | 自动剥离默认值 |
| `AUTOINCREMENT` | 自动剥离自增属性 |



---

## 十、FTP/SFTP 文件采集专项

> 支持 FTP / FTPS / SFTP / SDTP 四种协议。自动检测 FTPS 加密、流式下载带毫秒级中断探针、MD5 去重、内容哈希幂等写入。支持 CSV / JSON / YAML / Excel / XML 结构化解析入库。

### 1. 创建文件数据源

FTP/SFTP 数据源不需要数据库连接，连接信息可在任务中通过 `ftp_url` 覆盖：

```json
{
  "name": "内网FTP服务器",
  "type": "ftp",
  "host": "192.168.1.100",
  "port": 21,
  "db_name": "/",
  "username": "admin",
  "password": "123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | `ftp`（FTP/FTPS/SFTP/SDTP 统一用此类型） |
| host | string | ✅ | 服务器地址 |
| port | int | ✅ | 端口：FTP=21，SFTP=22 |
| db_name | string | ✅ | 占位符，随便填 `"/"` |
| username | string | ❌ | 用户名 |
| password | string | ❌ | 密码 |

> `ftp_url` 中指定协议前缀（`sftp://` / `ftps://` 等），引擎自动适配，无需在数据源 `type` 中区分。

---

### 2. 创建文件采集任务

#### 方式 A：用 `ftp_url`（推荐，支持多协议）

```json
// FTP
{"ftp_url": "ftp://admin:123456@192.168.1.100:21/data/calico.yaml"}

// FTPS（自动检测加密）
{"ftp_url": "ftps://admin:123456@192.168.1.100:21/data/calico.yaml"}

// SFTP（SSH 文件传输）
{"ftp_url": "sftp://admin:123456@192.168.1.100:22/home/user/data.csv"}

// SDTP（安全网闸，预留）
{"ftp_url": "sdtp://admin:123456@192.168.1.100/data/report.csv"}
```

完整请求：

```json
{
  "task_name": "采集calico配置",
  "source_id": "你的数据源ID",
  "ftp_url": "sftp://admin:123456@192.168.1.100:22/data/calico.yaml",
  "file_parse": 1,
  "collect_mode": "full"
}
```

> `ftp_url` 的协议前缀决定使用哪种传输协议（`ftp`/`ftps`/`sftp`/`sdtp`），自动解析 host/port/username/password/path 覆盖数据源配置。

#### 方式 B：用 `ftp_path`（连接信息从数据源读取，FTP 默认）

```json
{
  "task_name": "采集calico配置",
  "source_id": "你的数据源ID",
  "ftp_path": "calico.yaml",
  "file_parse": 1,
  "collect_mode": "full"
}
```

> FTP/FTPS 路径去掉前导 `/`（如 `calico.yaml` 而非 `/calico.yaml`）。SFTP/SDTP 保留绝对路径。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | 数据源 ID |
| ftp_url | string | ❌ | 多协议 URL，支持 `ftp://` `ftps://` `sftp://` `sdtp://`，传了自动解析 |
| ftp_path | string | ❌ | 远程文件路径。FTP/FTPS 去掉前导 `/`；SFTP/SDTP 保留绝对路径。与 `ftp_url` 二选一 |
| file_parse | int | ❌ | `1`=解析文件内容入库，`0`=只下载不解析，默认 `0` |
| file_type | string | ❌ | `auto`(自动识别) / `csv` / `json` / `yaml` / `xlsx` / `xml`，默认 `auto` |
| target_table | string | ❌ | 解析后写入哪张 PG 表，不传则自动用 `ftp_文件名` |
| ftp_passive | int | ❌ | `1`=被动模式（默认），`0`=主动模式。`None` 兜底为被动 |

**核心特性：**

| 特性 | 说明 |
|------|------|
| 多协议 | FTP / FTPS(自动检测) / SFTP(paramiko) / SDTP(预留) |
| 毫秒级中断 | 下载时每 ~400KB 探测一次暂停/取消信号，大文件可瞬间中断 |
| 幂等写入 | 每行数据的 MD5 哈希作为主键，重复执行 `ON CONFLICT DO NOTHING`，不产生脏数据 |
| 断点续传 | 暂停时水位线(MD5)保存到 Redis，`/resume` 回写数据库后从断点继续 |

> **注意：** `ftp_url` 和 `ftp_path` 至少传一个。都传时 `ftp_url` 优先。密码含 `@` 等特殊字符时需 URL 编码（如 `p@ss` → `p%40ss`）。

---

### 3. FTP 批量目录采集

> 一次性采集远程目录下所有匹配的文件。支持**递归子目录**和**通配符过滤**，采用"全量扫描 → 快速去重 → 单个处理 → 异常隔离"四步策略。单个文件失败不中断批次。

**方式 C：`ftp_dir`（批量目录）**

```json
{
  "task_name": "FTP批量采集",
  "source_id": "你的FTP数据源ID",
  "ftp_dir": "/factory/logs",
  "file_pattern": "*.csv",
  "is_recursive": 1,
  "ftp_passive": 1,
  "file_parse": 1,
  "file_type": "auto",
  "target_table": "ftp_logs",
  "collect_mode": "full",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| ftp_dir | string | ✅ | — | 远程根目录，如 `/factory/logs/` |
| file_pattern | string | ❌ | `"*"` | 文件通配符（Python fnmatch 语法）：`*.csv`、`log_*.xml`、`data_????.json` |
| is_recursive | int | ❌ | `0` | `0`=仅当前目录 `1`=递归所有子目录 |

**三种模式的优先级：**

| 优先级 | 模式 | 关键字段 | 适用场景 |
|--------|------|----------|----------|
| 1 | 批量目录 | `ftp_dir` | 自动采集目录下所有匹配文件 |
| 2 | 单文件 URL | `ftp_url` | 跨协议单文件（SFTP/FTPS 可自动识别） |
| 3 | 单文件路径 | `ftp_path` | 同协议单文件（连接信息从数据源读） |

**两阶段去重：**

```
扫描阶段 → 远程 mtime + size 与历史记录比对
  ├─ 相同 → 跳过（不下载, 不消耗带宽）
  └─ 不同 → 下载到本地 → 计算 MD5 → 再与历史 MD5 比对
             ├─ 相同 → 跳过
             └─ 不同 → 解析入库 + 更新记录
```

| 去重方式 | 开销 | 精度 |
|----------|------|------|
| **快速去重**（mtime+size） | 零开销，仅 FTP `MDTM` / SFTP `stat` 命令 | 99% 准确 |
| **精确去重**（MD5） | 下载文件后流式计算 | 100% 准确 |

**批量处理流程：**

```
1. _connect_client() → FTP/FTPS/SFTP 连接
2. _scan_directory() → DFS 递归扫描目录树
   ├─ MLSD 获取 (name, type, mtime, size) — 优先
   └─ Dir() 回退 — 服务器不支持 MLSD 时
3. fnmatch 通配符过滤
4. for each file → _process_single_file():
   ├─ 快速去重 (mtime+size) → 命中跳过
   ├─ 下载 + MD5 去重 → 命中跳过
   ├─ 解析入库
   └─ 更新 ftp_file_record
   单文件异常 → logger.error → continue（不中断批次）
5. 返回统计结果
```

**批量任务请求示例（完整）：**

```json
POST /tsync/add
{
  "task_name": "FTP全目录批量采集",
  "source_id": "你的FTP数据源ID",
  "target_table": "ftp_batch_data",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1,
  "ftp_dir": "/ta",
  "file_pattern": "*",
  "is_recursive": 1,
  "ftp_passive": 1,
  "file_parse": 1,
  "file_type": "auto"
}
```

> **注意：** 和单文件模式一样，**host/port/username/password 不需要传**——Worker 自动从数据源注入凭证。

---

### 4. CSV 文件采集

CSV 文件自动探测编码（UTF-8 / GBK），流式分批写入，不会 OOM。

```json
{
  "task_name": "采集设备清单CSV",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/devices.csv",
  "file_parse": 1,
  "file_type": "csv",
  "target_table": "ftp_devices"
}
```

**CSV 文件内容示例：**

```csv
id,name,type,status
1,设备A,传感器,正常
2,设备B,控制器,异常
```

**目标表结构（自动创建）：**

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(32) | UUID 主键，自动生成 |
| raw_doc | JSON | 每行数据，如 `{"id":"1","name":"设备A","type":"传感器","status":"正常"}` |

**查询示例：**

```sql
SELECT id,
       raw_doc->>'name' AS name,
       raw_doc->>'type' AS type,
       raw_doc->>'status' AS status
FROM ftp_devices;
```

---

### 5. JSON 文件采集

支持顶层数组 `[...]` 和单个对象 `{...}`。

```json
{
  "task_name": "采集配置JSON",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/config.json",
  "file_parse": 1,
  "file_type": "json",
  "target_table": "ftp_config"
}
```

**JSON 文件内容示例（数组）：**

```json
[
  {"key": "max_connections", "value": 100},
  {"key": "timeout", "value": 30}
]
```

**JSON 文件内容示例（单对象）：**

```json
{
  "app_name": "my-app",
  "version": "1.0.0",
  "settings": {"debug": true}
}
```

**目标表结构：** 同 CSV，`id` + `raw_doc` 两列。

---

### 6. YAML 文件采集

支持单文档和多文档 YAML（`---` 分隔）。

```json
{
  "task_name": "采集K8s配置",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/calico.yaml",
  "file_parse": 1,
  "file_type": "yaml",
  "target_table": "ftp_calico"
}
```

**YAML 文件内容示例（多文档）：**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: calico-config
data:
  calico_backend: "bird"
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: calico-node
```

每个 `---` 分隔的文档存为一行 `raw_doc`。

---

### 7. Excel 文件采集

支持 `.xlsx` / `.xls` 格式，自动读取所有工作表，首行作为列名。

```json
{
  "task_name": "采集设备清单Excel",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/devices.xlsx",
  "file_parse": 1,
  "file_type": "xlsx",
  "target_table": "ftp_devices"
}
```

| Excel 内容 | 存入 raw_doc |
|------------|-------------|
| `设备A \| 传感器 \| 正常` | `{"名称":"设备A","类型":"传感器","状态":"正常"}` |
| `设备B \| 控制器 \| 异常` | `{"名称":"设备B","类型":"控制器","状态":"异常"}` |

> 多工作表时每个工作表独立解析，共享同一个目标表。空单元格转为空字符串 `""`。

---

### 8. XML 文件采集

递归解析 XML 树，整个文档存为一条 JSON 记录。

```json
{
  "task_name": "采集XML配置",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/config.xml",
  "file_parse": 1,
  "file_type": "xml",
  "target_table": "ftp_config"
}
```

**XML 内容示例：**

```xml
<project name="my-app">
  <version>1.0.0</version>
  <database>
    <host>localhost</host>
    <port>5432</port>
  </database>
</project>
```

解析后 `raw_doc` 为：

```json
{
  "_tag": "project",
  "name": "my-app",
  "version": {"_tag": "version", "_text": "1.0.0"},
  "database": {
    "_tag": "database",
    "host": {"_tag": "host", "_text": "localhost"},
    "port": {"_tag": "port", "_text": "5432"}
  }
}
```

---

### 9. 仅下载不解析（二进制文件）

`file_parse=0`（默认）时，文件只下载到本地，不解析入库。适合二进制文件（图片、PDF 等）。

```json
{
  "task_name": "备份数据库dump",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/backup/db_20260609.sql",
  "file_parse": 0
}
```

文件保存路径：`{项目根目录}/ftp_files/{task_id}/db_20260609.sql`

---

### 10. 多协议连接详解

#### FTPS 加密（自动检测）

```json
{
  "ftp_url": "ftps://admin:123456@192.168.1.100:21/data/report.csv",
  "file_parse": 1,
  "file_type": "csv"
}
```

> 引擎自动检测：先尝试明文 FTP → 服务器返回 `503 Use AUTH first` → 自动切换 FTPS → 忽略自签证书 → 下载完成。

#### SFTP（SSH 文件传输）

```json
{
  "ftp_url": "sftp://admin:123456@192.168.1.100:22/home/user/data.csv",
  "file_parse": 1,
  "file_type": "csv"
}
```

> 基于 `paramiko` SSH 协议，端口默认 `22`。**路径保留绝对路径**（如 `/home/user/data.csv`），不要去掉前导 `/`。

#### SDTP（安全网闸，预留）

```json
{
  "ftp_url": "sdtp://admin:123456@192.168.1.100/data/report.csv",
  "file_parse": 1
}
```

> 用于对接隔离网闸的私有 SDK 或命令行工具，当前为预留适配器。

#### 协议对比

| 协议 | 端口 | 路径格式 | 加密 | 依赖 |
|------|------|----------|------|------|
| FTP | 21 | 去掉前导 `/` | 明文 | `ftplib`（Python 内置） |
| FTPS | 21 | 去掉前导 `/` | TLS | `ftplib` + `ssl`（Python 内置） |
| SFTP | 22 | 保留 `/home/...` | SSH | `paramiko` |
| SDTP | — | 保留 | 网闸 | 私有 SDK |

---

### 11. MD5 去重与幂等写入

**文件级去重：** 同一文件重复执行时，如果 MD5 未变化，自动跳过下载和解析。

**行级幂等写入：** 每行数据以内容 MD5 哈希作为主键，写入时使用 `ON CONFLICT (id) DO NOTHING`。即使同一文件解析多次，也不会产生重复行。断点续传重跑时，已入库的行自动跳过。

```json
// 文件未变化
{
  "status": "skipped",
  "message": "文件 MD5 未变更, 跳过",
  "tables_synced": 0,
  "total_records": 0,
  "new_watermark": "d41d8cd98f00b204e9800998ecf8427e",
  "table_details": []
}
```

---

### 12. 文件记录表 `ftp_file_record`

每次下载都会记录元数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(32) | UUID 主键 |
| task_id | VARCHAR(32) | 关联任务 ID |
| remote_path | VARCHAR(500) | FTP 远程路径 |
| local_path | VARCHAR(500) | 本地存储路径 |
| file_name | VARCHAR(255) | 文件名 |
| file_size | INTEGER | 文件大小（字节） |
| md5 | VARCHAR(32) | 文件 MD5，用于增量去重 |
| file_type | VARCHAR(20) | 文件类型 |
| remote_mtime | VARCHAR(30) | 远程文件修改时间（批量模式快速去重凭据） |
| remote_size | BIGINT | 远程文件大小（配合 mtime 做下载前去重） |
| is_parsed | INTEGER | 0=未解析，1=已解析入库 |
| parsed_rows | INTEGER | 解析写入行数 |
| downloaded_at | TIMESTAMP | 下载时间 |

> **查询文件明细：** 任务执行后通过 `POST /tsync/record/list`（传入 `task_id`）分页查询该表，详见[同步任务管理 - 第 14 节](#14-文件同步记录查询)。

---

### 13. 深度测试(已通过)

CSV 流式解析

```json
{
  "task_name": "深度测试-CSV流式解析",
  "source_id": "f485bd9d27dc4f9f99694fb0a932e9d0",
  "ftp_url": "ftp://admin@127.0.0.1/users.csv",
  "ftp_passive": 1,
  "file_parse": 1,
  "file_type": "auto",
  "target_table": "ftp_test_csv",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

JSON 强制解析 + 主动模式避障测试

```json
{
  "task_name": "深度测试-JSON主动模式",
  "source_id": "f485bd9d27dc4f9f99694fb0a932e9d0",
  "ftp_url": "ftp://admin@127.0.0.1/orders.json",
  "ftp_passive": 0,
  "file_parse": 1,
  "file_type": "json",
  "target_table": "ftp_test_json",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

YAML 多文档拆解测试

```json
{
  "task_name": "深度测试-YAML多文档",
  "source_id": "f485bd9d27dc4f9f99694fb0a932e9d0",
  "ftp_url": "ftp://admin@127.0.0.1/calico.yaml",
  "ftp_passive": 1,
  "file_parse": 1,
  "file_type": "auto",
  "target_table": "ftp_test_yaml",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

纯二进制下载与 MD5 增量去重

```json
{
  "task_name": "深度测试-纯文件去重",
  "source_id": "f485bd9d27dc4f9f99694fb0a932e9d0",
  "ftp_url": "ftp://admin@127.0.0.1/mongo.py",
  "ftp_passive": 1,
  "file_parse": 0,
  "file_type": "auto",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

异常容错测试

```json
{
  "task_name": "深度测试-异常捕获",
  "source_id": "YOUR_SOURCE_ID",
  "ftp_url": "ftp://admin@127.0.0.1/i_do_not_exist.txt",
  "ftp_passive": 1,
  "file_parse": 0,
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



### 文件采集流程

```
1. 解析 ftp_url 获取协议类型（ftp/ftps/sftp/sdtp）
2. 查 ftp_file_record 表获取历史 MD5
3. FileClientFactory 根据协议创建适配器（FTP/FTPS 走 TLS 会话复用补丁，SFTP 走 paramiko）
4. 连接服务器 + 流式下载到本地 {项目根}/ftp_files/{task_id}/
   └── 下载过程中每 ~400KB 探测一次暂停/取消信号（毫秒级中断）
5. 验证文件大小（0字节则报错）
6. 计算 MD5 → 与历史对比 → 相同则跳过
7. 保存文件记录到 ftp_file_record
8. 如果 file_parse=1：
   - CSV → 流式解析 + 编码探测（UTF-8/GBK）
   - JSON → 支持数组/单对象
   - YAML → 支持多文档(---)
   - Excel → 多工作表，首行列名
   - XML → 递归转 dict，同名节点收集为列表
   - 每行以内容 MD5 为主键 → ON CONFLICT DO NOTHING 幂等写入
   - 目标表结构: id VARCHAR(32) PK + raw_doc JSON
9. 更新文件记录（is_parsed=1, parsed_rows=N）
```



### 14. FTP 目录树勘探（配置辅助）

> 在创建 FTP 采集任务前，可通过此接口预览服务器上的目录和文件结构，帮助用户选择正确的 `ftp_path` 或 `ftp_url`。支持懒加载（逐级展开）和有限深度的全量递归，所有网络 I/O 均在后台线程池执行，不阻塞主服务。

`POST /datasource/ftp/dir_tree`

**懒加载模式（推荐）：** 每次只返回当前路径下的直接子节点，前端树形组件逐级展开。

```json
{
  "datasource_id": "550e8400e29b41d4a716446655440000",
  "remote_path": "/",
  "recursive": false
}
```

**全量递归模式：** 一次性返回指定深度内的完整目录树（谨慎使用，深层目录可能数据量较大）。

```json
{
  "datasource_id": "550e8400e29b41d4a716446655440000",
  "remote_path": "/data",
  "recursive": true,
  "max_depth": 3
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| datasource_id | string | ✅ | — | FTP/SFTP 数据源 UUID（32位） |
| remote_path | string | ❌ | `"/"` | 勘探的远程起始路径 |
| recursive | bool | ❌ | `false` | `false`=懒加载（仅当前层级） `true`=递归向下探测 |
| max_depth | int | ❌ | `2` | 递归最大深度（1~5），仅在 `recursive=true` 时生效 |

**响应：**

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    {
      "title": "data",
      "key": "/data",
      "is_dir": true,
      "isLeaf": false,
      "children": []
    },
    {
      "title": "report.csv",
      "key": "/report.csv",
      "is_dir": false,
      "isLeaf": true,
      "children": null
    }
  ]
}
```

| 响应字段 | 类型 | 说明 |
|----------|------|------|
| title | string | 文件/目录名（用于前端树节点展示） |
| key | string | 绝对路径（前端展开时回传给 `remote_path`） |
| is_dir | bool | 是否为目录 |
| isLeaf | bool | 是否叶子节点（`true`=文件 `false`=目录，对齐 ElementPlus/AntDesign 树组件） |
| children | array/null | 子节点列表：目录为空数组可展开，文件为 null 不可展开 |

**协议自动识别：**

接口根据数据源的 `config_json.protocol` 字段选择连接方式：

| config_json.protocol | 连接方式 | 端口 |
|---------------------|----------|------|
| `"ftp"`（默认） | FTP 明文 | 21 |
| `"ftps"` | FTP + TLS 加密 | 21 |
| `"sftp"` | SFTP（SSH 文件传输） | 22 |

> 未配置 `config_json.protocol` 时默认走 FTP，且引擎会自动检测服务器是否要求 TLS（503 AUTH → 自动切换到 FTPS）。

**前端懒加载交互示例：**

```javascript
// 1. 初始加载根目录
const root = await fetch("/api/v1/datasource/ftp/dir_tree", {
  method: "POST",
  body: JSON.stringify({ datasource_id: "xxx", remote_path: "/" })
});
// → 返回 [/data, /backup, config.yaml]

// 2. 用户点击展开 /data 文件夹
const children = await fetch("/api/v1/datasource/ftp/dir_tree", {
  method: "POST",
  body: JSON.stringify({ datasource_id: "xxx", remote_path: "/data" })
});
// → 返回 [/data/reports, /data/raw, /data/schema.sql]

// 3. 继续展开 /data/reports
// ...
```

**典型使用场景：**

```
1. 前端创建 FTP 任务表单中加一个「浏览远程目录」按钮
2. 点击后弹出树形对话框，调用此接口懒加载展示远程文件结构
3. 用户选中一个文件或目录，自动填入表单的 ftp_path / ftp_url 字段
```



---

## 十一、API 接口采集专项

> API 采集引擎支持定时调用 HTTP 接口，将响应数据存入 PG，同时将监控指标写入 InfluxDB。

### 1. 创建 API 数据源

API 数据源不需要数据库连接，连接参数随便填即可：

```json
{
  "name": "雨云API监控",
  "type": "api",
  "host": "0.0.0.0",
  "port": 80,
  "db_name": "default",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"api"` |
| host | string | ✅ | 随便填，仅做标识 |
| port | int | ✅ | 随便填 |
| db_name | string | ✅ | 随便填 |

---

### 2. 创建 API 采集任务

```json
{
  "task_name": "监控雨云cdn接口",
  "source_id": "你的API数据源ID",
  "api_url": "https://api.v2.rainyun.com/user/coupons",
  "api_method": "GET",
  "api_headers": {"Authorization": "Bearer xxx", "Content-Type": "application/json"},
  "api_body": {"page": 1, "size": 10},
  "api_extract_mode": "both",
  "api_data_path": "data.items",
  "target_table": "api_rainyun_coupons",
  "schedule_type": "interval_min",
  "schedule_value": "5",
  "collect_mode": "full"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | API 数据源 ID |
| api_url | string | ✅ | 接口完整 URL |
| api_method | string | ❌ | 请求方法：`GET`/`POST`/`PUT` |
| api_headers | object | ❌ | 请求头，如 `{"Authorization":"Bearer xxx"}` |
| api_body | object | ❌ | 请求体（POST/PUT）或查询参数（GET） |
| api_extract_mode | string | ❌ | `data`(只入PG) / `monitor`(只入InfluxDB) / `both`(都要)，默认 `both` |
| api_data_path | string | ❌ | 响应体中业务数据的路径，如 `data.items`，不填取整个响应体 |
| target_table | string | ❌ | PG 目标表名，不填则自动从 URL 推导（如 `api_coupons`） |
| schedule_type | string | ❌ | 调度类型，推荐 `interval_min` 做定时监控 |
| schedule_value | string | ❌ | 配合 schedule_type 的值 |

---

### 3. API 采集三种模式

| api_extract_mode | 行为 |
|---|---|
| `both`（默认） | 业务数据入 PG + 监控指标入 InfluxDB |
| `data` | 只解析响应数据存入 PG |
| `monitor` | 只记录响应时间/状态码到 InfluxDB |

---

### 4. api_data_path 用法详解

用于从嵌套 JSON 响应中提取业务数据数组。

**示例 1：响应体就是数组**

```json
// 响应：["data1", "data2"]
// 不需要 api_data_path，直接整个响应体作为数据
```

**示例 2：数据在 `data.items` 下**

```json
// 响应：{"code": 200, "data": {"items": [{"id": 1}, {"id": 2}]}}
// api_data_path = "data.items"  或  "$.data.items"
// 提取到：[{"id": 1}, {"id": 2}]
```

**示例 3：数据在顶层 `data` 下**

```json
// 响应：{"code": 200, "data": [{"id": 1}, {"id": 2}]}
// api_data_path = "data"
```

**路径规则：** `.` 分隔的 JSON key 路径，`$` 前缀会自动去掉。中间节点必须是 dict，最终节点可以是 list（每条一个 row）或 dict（存为一条 row）。

---

### 5. 目标表名推导规则

| 用户是否传 target_table | 结果 |
|---|---|
| 传了 `"target_table": "my_data"` | 写入 `my_data` |
| 没传，`api_url = ".../coupons"` | 自动推导 `api_coupons` |
| 没传，`api_url = ".../products/list"` | 自动推导 `api_list` |
| 没传，`api_url = "https://api.com"` | 兜底 `api_data` |

**目标表结构（自动创建）：**

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(32) | UUID 主键 |
| raw_doc | JSON | 响应数据（每条为一个 JSON 对象） |
| collected_at | TEXT | 采集时间（ISO 8601 格式） |

**查询示例：**

```sql
SELECT id, raw_doc->>'name' AS name, collected_at
FROM api_rainyun_coupons
ORDER BY collected_at DESC;
```

---

### 6. 定时监控示例

每 5 分钟调用一次接口，记录监控指标到 InfluxDB，不解析业务数据：

```json
{
  "task_name": "接口健康监控",
  "source_id": "你的API数据源ID",
  "api_url": "https://api.example.com/health",
  "api_method": "GET",
  "api_extract_mode": "monitor",
  "schedule_type": "interval_min",
  "schedule_value": "5",
  "collect_mode": "full"
}
```

---

### 7.深度测试

第 0 步：创建一个外部 API 数据源

```json
{
  "name": "雨云业务API数据源",
  "type": "api",
  "host": "api.v2.rainyun.com",
  "port": 443,
  "username": "",
  "password": "",
  "db_name": "rainyun_external", 
  "description": "用于测试带复杂Cookie和Token的外部接口采集",
  "status": 1
}
```



任务 1：采集用户优惠券 (GET)

```json
{
  "task_name": "雨云-采集优惠券列表",
  "source_id": "【你的数据源ID】",
  "api_url": "https://api.v2.rainyun.com/user/coupons/",
  "api_method": "GET",
  "api_headers": {
    "cookie": "dev-code=z2JndTd5CtxwF7RE; X-CSRF-Token=6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt; cookie-exp=1781748558793; user-data={%22ID%22:800911%2C%22Name%22:%222136987894%22%2C%22LastIP%22:%22123.139.60.14%22}; rain-session=MTc4MTE0Mzc1OXxOd3dBTkZwV1JGcExTbEZSTWtrM1VFNDBUVXhHTmpZeVNsVlhTMGRPVDFFMVEwNVVSRlJYTjBoRFZVRkJXbGRUVlVvMFRWbE9TRUU9fL4max4uJsVHdZbrb7zZEYSUIFlySdbg_7iYtnBh_xXG",
    "x-csrf-token": "6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt",
    "rys": "850a225604f83c45163f4e18c1865aef1781143763.003",
    "accept": "application/json"
  },
  "api_extract_mode": "both",
  "api_data_path": "data", 
  "target_table": "api_rainyun_coupons",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



任务 2：采集云产品列表 (GET)

```json
{
  "task_name": "雨云-采集产品列表",
  "source_id": "【你的数据源ID】",
  "api_url": "https://api.v2.rainyun.com/product/",
  "api_method": "GET",
  "api_headers": {
    "cookie": "dev-code=z2JndTd5CtxwF7RE; X-CSRF-Token=6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt; cookie-exp=1781748558793; user-data={%22ID%22:800911%2C%22Name%22:%222136987894%22%2C%22LastIP%22:%22123.139.60.14%22}; rain-session=MTc4MTE0Mzc1OXxOd3dBTkZwV1JGcExTbEZSTWtrM1VFNDBUVXhHTmpZeVNsVlhTMGRPVDFFMVEwNVVSRlJYTjBoRFZVRkJXbGRUVlVvMFRWbE9TRUU9fL4max4uJsVHdZbrb7zZEYSUIFlySdbg_7iYtnBh_xXG",
    "x-csrf-token": "6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt",
    "rys": "850a225604f83c45163f4e18c1865aef1781143763.003",
    "accept": "application/json"
  },
  "api_extract_mode": "both",
  "api_data_path": "data",
  "target_table": "api_rainyun_products",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



任务 3：采集用户站内信/消息 (GET)

```json
{
  "task_name": "雨云-采集用户消息",
  "source_id": "【你的数据源ID】",
  "api_url": "https://api.v2.rainyun.com/user/msg/",
  "api_method": "GET",
  "api_headers": {
    "cookie": "dev-code=z2JndTd5CtxwF7RE; X-CSRF-Token=6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt; cookie-exp=1781748558793; user-data={%22ID%22:800911%2C%22Name%22:%222136987894%22%2C%22LastIP%22:%22123.139.60.14%22}; rain-session=MTc4MTE0Mzc2M3xOd3dBTkZwV1JGcExTbEZSTWtrM1VFNDBUVXhHTmpZeVNsVlhTMGRPVDFFMVEwNVVSRlJYTjBoRFZVRkJXbGRUVlVvMFRWbE9TRUU9fJH1XxRoIPamN4R7yDW45VwGwrYsqjaDe5dxRA-dyOoo",
    "x-csrf-token": "6rwDFBjxZnrsSpTUt1cKdOAKharCvnbt",
    "rys": "850a225604f83c45163f4e18c1865aef1781143774.148",
    "accept": "application/json"
  },
  "api_extract_mode": "both",
  "api_data_path": "data",
  "target_table": "api_rainyun_messages",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



任务 4：Umami 埋点日志模拟发送 (POST)

```json
{
  "task_name": "Umami-模拟埋点上报",
  "source_id": "【你的数据源ID】",
  "api_url": "https://umami.rainyun.cn/api/send",
  "api_method": "POST",
  "api_headers": {
    "content-type": "application/json",
    "x-umami-cache": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ3ZWJzaXRlSWQiOiJlYzM1ZjcyMy05ZjQxLTQ1MTItOGYwZS00NDVhM2JlM2ZjNWUiLCJzZXNzaW9uSWQiOiJkYjA3NjBjMi0xNjY2LTU4MjgtYmVmOS1kMjE2OWRhNGJiZDAiLCJ2aXNpdElkIjoiYjU1MGM2MjEtZGQ2OS01OTgxLTgyYzUtNjU4MjIyNzI5M2E5IiwiaWF0IjoxNzgxMTQzNzU1fQ.Z-dOgofyWMzfHorZN8O_NlMro2bGdMCf8eWKENXhW7Y",
    "origin": "https://app.rainyun.com",
    "referer": "https://app.rainyun.com/"
  },
  "api_body": {
    "type": "event",
    "payload": {
      "website": "ec35f723-9f41-4512-8f0e-445a3be3fc5e",
      "screen": "1536x864",
      "language": "zh-CN",
      "title": "应用商店 | 雨云",
      "hostname": "app.rainyun.com",
      "url": "https://app.rainyun.com/apps/rca/store",
      "referrer": "https://app.rainyun.com/dashboard"
    }
  },
  "api_extract_mode": "monitor", 
  "target_table": "api_umami_log",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



## 十二、InfluxDB 监控查询接口 `/monitor`

> 查询 API 采集引擎写入 InfluxDB 的监控指标数据，用于可视化大盘。

### 1. 24小时监控统计卡片

`POST /monitor/stats`

```json
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "total_requests": 1234,
    "avg_time_ms": 45.2,
    "success_rate": 98.5
  }
}
```

| 字段 | 说明 |
|------|------|
| total_requests | 过去 24h 总调用次数 |
| avg_time_ms | 平均响应时间（毫秒） |
| success_rate | 成功率（百分比） |

---

### 2. 耗时与并发趋势图

`POST /monitor/trend`

```json
{"task_id": "e480c7cb0ff245a7bbb6685d23615182", "interval": "1 hour"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 ID |
| interval | string | ❌ | 聚合粒度：`1 hour`（默认）/ `5 minutes` |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    {"_time": "2026-06-10T10:00:00Z", "request_count": 50, "avg_time_ms": 42.1},
    {"_time": "2026-06-10T11:00:00Z", "request_count": 45, "avg_time_ms": 38.7}
  ]
}
```

> 可用 Echarts 折线图：X 轴 `_time`，左 Y 轴 `request_count`（柱状），右 Y 轴 `avg_time_ms`（折线）。

---

### 3. 最新调用明细日志

`POST /monitor/logs`

```json
{"task_id": "e480c7cb0ff245a7bbb6685d23615182", "limit": 50}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 ID |
| limit | int | ❌ | 返回条数 1-500，默认 50 |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    {
      "api_url": "https://api.v2.rainyun.com/user/coupons",
      "method": "GET",
      "status_code": 200,
      "response_time": 45.2,
      "error_msg": "",
      "time": "2026-06-10T12:00:00Z"
    },
    {
      "api_url": "https://api.v2.rainyun.com/user/coupons",
      "method": "GET",
      "status_code": 500,
      "response_time": 1230.5,
      "error_msg": "Internal Server Error",
      "time": "2026-06-10T11:55:00Z"
    }
  ]
}
```

> 前端建议：非 2xx 状态码行高亮标红。

---

### 4. 高级时序查询（动态降采样）

`POST /monitor/series/query`

```json
{
  "task_id": "e480c7cb0ff245a7bbb6685d23615182",
  "start_time": "2026-06-10T00:00:00Z",
  "end_time": "2026-06-11T00:00:00Z",
  "window": "5m"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 ID |
| start_time | string | ✅ | 开始时间（ISO 8601） |
| end_time | string | ✅ | 结束时间（ISO 8601） |
| window | string | ❌ | 聚合粒度：`1m` / `5m`(默认) / `15m` / `1h` / `1d` |

响应：

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": {
    "series": [
      {"time_bucket": "2026-06-10T10:00:00Z", "request_count": 20, "avg_latency_ms": 38.5, "max_latency_ms": 120.0, "success_rate": 95.0},
      {"time_bucket": "2026-06-10T10:05:00Z", "request_count": 25, "avg_latency_ms": 42.1, "max_latency_ms": 89.0, "success_rate": 100.0}
    ],
    "meta": {"window_used": "5m", "data_points": 288}
  }
}
```

> `window` 越小，数据点越多，图表越精细。推荐根据时间跨度自动选择：24h → `5m`，7d → `1h`，30d → `1d`。

---

### InfluxDB 数据模型

`api_monitor` measurement 结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | tag | 任务 ID |
| method | tag | HTTP 方法 |
| status_code | tag | HTTP 状态码 |
| url | tag | 接口 URL |
| response_time | field | 响应时间（毫秒） |
| is_success | field | 1=成功 0=失败 |
| response_size | field | 响应体大小（字节） |
| error_msg | field | 错误信息 |
| time | timestamp | InfluxDB 自动生成 |



---

## 十三、SNMP 采集专项

> 基于 pysnmp 7.x 异步 API，支持 v1/v2c/v3 三种版本。性能指标入 InfluxDB，设备表格信息入 PG。

### 1. 创建 SNMP 数据源

连接凭证（v3 密钥等）存入数据源的 `config_json`，不在任务中暴露：

```json
{
  "name": "核心交换机",
  "type": "snmp",
  "host": "192.168.1.1",
  "port": 161,
  "db_name": "default",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"snmp"` |
| host | string | ✅ | 设备 IP 地址 |
| port | int | ✅ | SNMP 端口，默认 `161` |
| db_name | string | ✅ | 随便填 |
| username | string | ❌ | 配置界面用，SNMP 实际参数在任务中 |

---

### 2. SNMP v2c 采集（最常用）

```json
{
  "task_name": "交换机端口流量监控",
  "source_id": "你的SNMP数据源ID",
  "snmp_version": "v2c",
  "snmp_community": "public",
  "snmp_extract_mode": "both",
  "snmp_metric_oids": {
    "cpu_usage": "1.3.6.1.4.1.2021.11.11.0",
    "mem_total": "1.3.6.1.4.1.2021.4.5.0",
    "mem_free": "1.3.6.1.4.1.2021.4.11.0"
  },
  "snmp_table_oids": {
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16"
  },
  "target_table": "snmp_interfaces",
  "schedule_type": "interval_min",
  "schedule_value": "5",
  "collect_mode": "full"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | SNMP 数据源 ID |
| snmp_version | string | ❌ | `v1` / `v2c`（默认）/ `v3` |
| snmp_community | string | ❌ | v1/v2c 团体字，默认 `"public"` |
| snmp_extract_mode | string | ❌ | `metric`(指标→InfluxDB) / `info`(表格→PG) / `both`(都要)，默认 `both` |
| snmp_metric_oids | object | ❌ | 性能指标 OID 映射，格式 `{"字段名":"OID"}` |
| snmp_table_oids | object | ❌ | 表格列 OID 映射，格式 `{"列名":"基础OID"}` |
| target_table | string | ❌ | PG 目标表名，不传默认 `snmp_info` |
| schedule_type | string | ❌ | 推荐 `interval_min` 做定时采集 |
| schedule_value | string | ❌ | 配合 schedule_type |

**snmp_metric_oids 说明：** 对每个 OID 执行 `GET`，取一个标量值。适合 CPU、内存、温度等。值自动转为 float，失败时为 `None`。

**snmp_table_oids 说明：** 对每个基础 OID 执行 `WALK`，按索引后缀聚合成行。适合接口流量表、ARP 表等。OID 后缀相同的值归入同一行。

**响应示例：**

```
WALK ifDescr  → {"1": "eth0", "2": "eth1"}
WALK ifInOctets → {"1": 1234567, "2": 8901234}

聚合成行：
  {"_index": "1", "ifDescr": "eth0", "ifInOctets": 1234567}
  {"_index": "2", "ifDescr": "eth1", "ifInOctets": 8901234}
→ 每行以内容 MD5 为主键，ON CONFLICT DO NOTHING 幂等写入 PG
```

---

### 3. SNMP v3 采集（加密认证）

```json
{
  "task_name": "核心路由器v3监控",
  "source_id": "你的SNMP数据源ID",
  "snmp_version": "v3",
  "snmp_user": "admin",
  "snmp_auth_key": "auth_password123",
  "snmp_priv_key": "priv_password456",
  "snmp_auth_protocol": "SHA",
  "snmp_priv_protocol": "AES",
  "snmp_extract_mode": "metric",
  "snmp_metric_oids": {
    "sys_uptime": "1.3.6.1.2.1.1.3.0",
    "cpu_5s": "1.3.6.1.4.1.2021.10.1.3.1"
  },
  "schedule_type": "interval_min",
  "schedule_value": "1"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| snmp_version | string | ✅ | 固定 `"v3"` |
| snmp_user | string | ✅ | v3 用户名 |
| snmp_auth_key | string | ❌ | 认证密码（不传 = 无认证） |
| snmp_priv_key | string | ❌ | 加密密码（不传 = 无加密） |
| snmp_auth_protocol | string | ❌ | 认证协议：`MD5` / `SHA`（默认） |
| snmp_priv_protocol | string | ❌ | 加密协议：`DES` / `AES`（默认） |

> v3 凭证字段仅存在于 `DBSyncReq` 内部流转，不出现在 `TaskOut` 返回值中。

---

### 4. 仅采集表格（info 模式）

```json
{
  "task_name": "ARP表快照",
  "source_id": "你的SNMP数据源ID",
  "snmp_version": "v2c",
  "snmp_community": "public",
  "snmp_extract_mode": "info",
  "snmp_table_oids": {
    "ipNetToMediaIfIndex": "1.3.6.1.2.1.4.22.1.1",
    "ipNetToMediaPhysAddress": "1.3.6.1.2.1.4.22.1.2",
    "ipNetToMediaNetAddress": "1.3.6.1.2.1.4.22.1.3",
    "ipNetToMediaType": "1.3.6.1.2.1.4.22.1.4"
  },
  "target_table": "snmp_arp_table",
  "collect_mode": "full"
}
```

> `info` 模式只做 WALK → 聚合 → 写入 PG，不写 InfluxDB。适合定期快照。

---

### 5. 仅采集指标（metric 模式）

```json
{
  "task_name": "设备健康心跳",
  "source_id": "你的SNMP数据源ID",
  "snmp_extract_mode": "metric",
  "snmp_metric_oids": {
    "cpu": "1.3.6.1.4.1.2021.11.11.0",
    "mem_used": "1.3.6.1.4.1.2021.4.6.0",
    "temp": "1.3.6.1.4.1.2021.13.16.2.1.3.1"
  },
  "schedule_type": "interval_min",
  "schedule_value": "1"
}
```

> `metric` 模式只做 GET → 写入 InfluxDB，不入 PG。适合高频监控（每秒/每分钟）。

---

### 6. 深度测试

创建一个 SNMP 数据源

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

创建并测试 SNMP 双写采集任务

```json
{
  "task_name": "深度测试-SNMP双引擎采集",
  "source_id": "【数据源 ID】",
  "snmp_version": "v2c",
  "snmp_community": "public",
  "snmp_extract_mode": "both",
  
  "snmp_metric_oids": {
    "sys_name": "1.3.6.1.2.1.1.5.0",
    "sys_uptime": "1.3.6.1.2.1.1.3.0",
    "if_in_octets": "1.3.6.1.2.1.2.2.1.10.1"
  },
  
  "snmp_table_oids": {
    "sys_info_tree": "1.3.6.1.2.1.1"
  },
  
  "target_table": "snmp_test_info",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



## 十四、Socket 采集专项

> 原生 TCP/UDP Socket 主动请求-响应模式。支持文本指令和十六进制二进制协议。监控入 InfluxDB，数据入 PG。

### 1. 创建 Socket 数据源

```json
{
  "name": "工控设备TCP",
  "type": "socket",
  "host": "192.168.1.50",
  "port": 502,
  "db_name": "default",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"socket"` |
| host | string | ✅ | 目标主机 IP |
| port | int | ✅ | 目标端口 |
| db_name | string | ✅ | 随便填 |

---

### 2. TCP 文本协议（JSON 响应）

```json
{
  "task_name": "TCP设备状态查询",
  "source_id": "你的Socket数据源ID",
  "socket_protocol": "tcp",
  "socket_command": "{\"cmd\":\"get_status\"}\n",
  "socket_command_encoding": "utf-8",
  "socket_timeout": 5,
  "socket_recv_size": 4096,
  "socket_terminator": "\n",
  "socket_response_format": "json",
  "target_table": "socket_status",
  "schedule_type": "interval_min",
  "schedule_value": "1",
  "collect_mode": "full"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | Socket 数据源 ID |
| socket_protocol | string | ❌ | `tcp`（默认）/ `udp` |
| socket_command | string | ❌ | 发送的指令内容 |
| socket_command_encoding | string | ❌ | 指令编码：`utf-8`（默认）/ `hex` |
| socket_timeout | int | ❌ | 超时秒数，默认 `10` |
| socket_recv_size | int | ❌ | 接收缓冲区大小，默认 `4096` |
| socket_terminator | string | ❌ | 响应结束符，如 `\n`。不填则读到一次数据即完成 |
| socket_response_format | string | ❌ | 响应解析格式：`json`（默认）/ `text` / `hex` |
| target_table | string | ❌ | PG 目标表名，不传默认 `socket_data` |

**TCP 接收逻辑：**
- 配置了 `socket_terminator` → 持续接收直到读到终止符或超时
- 未配置 `socket_terminator` → 收到一次数据即完成

---

### 3. 二进制协议（十六进制指令）

工控设备常用 Modbus 等二进制协议：

```json
{
  "task_name": "Modbus读取",
  "source_id": "你的Socket数据源ID",
  "socket_protocol": "tcp",
  "socket_command": "00 01 00 00 00 06 01 03 00 00 00 0A",
  "socket_command_encoding": "hex",
  "socket_timeout": 3,
  "socket_response_format": "hex",
  "target_table": "modbus_data",
  "schedule_type": "interval_min",
  "schedule_value": "10"
}
```

| socket_command_encoding | socket_command | 发送内容 |
|------------------------|---------------|----------|
| `utf-8`（默认） | `"hello\n"` | 4 字节 `hello\n` |
| `hex` | `"00 01 02 0A"` 或 `"0001020A"` | 4 字节 `\x00\x01\x02\x0A` |

**`socket_response_format` 三种模式：**

| 值 | 解析行为 | 存入 raw_doc |
|----|---------|-------------|
| `json`（默认） | `json.loads(text)` | 解析后的 dict/list |
| `text` | 直接存为字符串 | `{"raw_text":"响应内容..."}` |
| `hex` | 十六进制显示 | `{"raw_hex":"00ffa1b2..."}` |

---

### 4. UDP 请求

```json
{
  "task_name": "UDP设备探测",
  "source_id": "你的Socket数据源ID",
  "socket_protocol": "udp",
  "socket_command": "ping",
  "socket_command_encoding": "utf-8",
  "socket_timeout": 3,
  "socket_response_format": "text",
  "schedule_type": "interval_min",
  "schedule_value": "1"
}
```

> UDP 模式下 `sendto` + `recvfrom`，一次性接收，不支持终止符。

---

### 5. socket_response_format 示例

| 设备响应内容 | socket_response_format | 存入 raw_doc |
|-------------|----------------------|-------------|
| `{"temp":25.5,"status":"ok"}` | `json` | `{"temp":25.5,"status":"ok"}` |
| `OK\r\n` | `text` | `{"raw_text":"OK\r\n"}` |
| `\x00\x01\xA0\xFF` | `hex` | `{"raw_hex":"0001a0ff"}` |
| `not valid json` | `json` → 降级 | `{"raw_text":"not valid json"}` |

---

### 6. 深度测试

创建一个 Socket 数据源

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

创建并测试 Socket 采集任务

```json
{
  "task_name": "深度测试-Socket模拟接收",
  "source_id": "【数据源 ID】",
  "socket_protocol": "tcp",
  "socket_timeout": 5,
  "socket_recv_size": 1024,
  "socket_terminator": "\n",
  "socket_response_format": "json",
  "api_extract_mode": "both",
  
  "target_table": "socket_test_data",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```



### 7. SNMP/Socket 通用说明

| 特性 | SNMP | Socket |
|------|------|--------|
| 默认端口 | 161 | 无默认，必须配置 |
| 监控写入 | InfluxDB `snmp_monitor` | InfluxDB `socket_monitor` |
| 数据写入 | PG（`id` + `raw_doc` + `collected_at`） | PG（`id` + `raw_doc` + `collected_at`） |
| 幂等 | 内容哈希 + ON CONFLICT DO NOTHING | 内容哈希 + ON CONFLICT DO NOTHING |
| 暂停/取消 | 支持 | 支持 |
| 定时调度 | 推荐 `interval_min` | 推荐 `interval_min` |



---

## 十五、Kafka 流式采集专项

> 常驻 Consumer 模式，启动后持续消费。攒批写入 PG，offset 写入成功后才 commit。消费速率写入 InfluxDB。

```
FastAPI 启动时 (lifespan)
  ↓
KafkaConsumerManager
  ├── 读取所有 db_type="kafka" 且启用的任务
  └── 为每个任务启动一个 asyncio.Task（长期运行的消费循环）

消费循环 (KafkaSyncEngine.run)
  ↓
poll消息 → 攒批 → 写入PG（数据）+ InfluxDB（消费速率/Lag监控）
  ↓
写入成功后才 commit offset（Kafka自身的offset机制，天然持久化）
```



### 1. 创建 Kafka 数据源

Kafka 的连接信息（bootstrap servers 等）直接在任务中配置，数据源仅做标识：

```json
{
  "name": "工业传感器Kafka",
  "type": "kafka",
  "host": "0.0.0.0",
  "port": 9092,
  "db_name": "default",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"kafka"` |
| host | string | ✅ | 随便填，做标识用 |
| port | int | ✅ | 随便填 |
| db_name | string | ✅ | 随便填 |

---

### 2. 创建 Kafka 消费任务

```json
{
  "task_name": "传感器数据流消费",
  "source_id": "69fa04c0d1bb48f7ae594bd75efb04f4",
  "kafka_bootstrap_servers": "127.0.0.1:9092",
  "kafka_topic": "test_sensor_topic",
  "kafka_group_id": "test_group_01",
  "kafka_auto_offset_reset": "latest",
  "kafka_batch_size": 100,
  "kafka_batch_timeout_ms": 5000,
  "kafka_value_format": "json",
  "target_table": "kafka_test_data",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_name | string | ✅ | 任务名称 |
| source_id | string | ✅ | Kafka 数据源 ID |
| kafka_bootstrap_servers | string | ✅ | Kafka 集群地址，如 `127.0.0.1:9092` |
| kafka_topic | string | ✅ | 订阅的 Topic |
| kafka_group_id | string | ❌ | 消费组 ID，不填自动用 `dataflux_{task_id}` |
| kafka_auto_offset_reset | string | ❌ | `latest`（默认，只消费新消息）/ `earliest`（从最早的 offset 开始） |
| kafka_batch_size | int | ❌ | 攒批大小，满批或超时即写入一次，默认 `500` |
| kafka_batch_timeout_ms | int | ❌ | 攒批超时毫秒数，默认 `5000`（5秒） |
| kafka_value_format | string | ❌ | 消息体解析格式：`json`（默认）/ `text` |
| target_table | string | ❌ | PG 目标表名，不传默认 `kafka_{topic名}` |
| collect_mode | string | ❌ | 固定 `"full"` |
| status | int | ❌ | `1`=启用，`0`=停用 |

---

### 3. Kafka 专属接口

Kafka 不通过 `/tsync/run` 触发（那是 ARQ 一次性任务），而是通过常驻消费者管理：

| 接口 | 说明 |
|------|------|
| `POST /tsync/kafka/start` | 启动指定任务的 Kafka Consumer |
| `POST /tsync/kafka/stop` | 停止指定任务的 Kafka Consumer |
| `POST /tsync/kafka/status` | 查询指定任务的 Consumer 状态 |

**启动 Consumer：**

```json
POST /tsync/kafka/start
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "Consumer已启动", "data": null}
```

> 系统启动时（FastAPI lifespan）会自动拉起所有启用状态的 Kafka 任务，无需手动逐个启动。

**停止 Consumer：**

```json
POST /tsync/kafka/stop
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "Consumer已停止", "data": null}
```

**查询状态：**

```json
POST /tsync/kafka/status
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "获取成功", "data": {"status": "running"}}
```

> `status` 取值：`"running"`（运行中）/ `"stopped"`（已停止）

---

### Kafka Consumer 生命周期（核心规则）

| 操作 | DB `status` 变化 | Consumer 行为 | 说明 |
|------|-----------------|---------------|------|
| 新建任务 | `status=1` | **不启动** | 仅存入数据库，需手动点 `/kafka/start` |
| 点击「启用」 | `0→1` | **不启动** | 只改数据库，把启动权交给前端按钮 |
| 点击「停用」 | `1→0` | **强制停止** | 数据库改为 0 + 立即调用 `kafka_manager.stop()` |
| 点击「删除」 | 记录删除 | **先停后删** | 先调用 `kafka_manager.stop()`，再删除数据库记录 |
| `/kafka/start` | 不变 | **启动** | 手动控制按钮，仅当 status=1 时生效 |
| `/kafka/stop` | 不变 | **停止** | 手动控制按钮 |
| 系统重启 | 不变 | **自动拉起** | 启动时自动启动所有 `status=1` 的 Kafka 任务 |

**设计原则：**

```
新建 → 不自动跑，等用户确认
启用 → 只开权限，不自动跑
停用 → 立刻停，切断资源
删除 → 先停后删，不留孤儿进程
重启 → 全部恢复，无需手动
```

---

### 4. Kafka 消费流程图

```
FastAPI 启动 (lifespan)
  ↓
start_all_kafka_tasks()
  ├── 查所有 DataSource.type="kafka" 且 CollectTask.status=1 的任务
  └── 为每个任务调用 kafka_manager.start()
       ↓
  KafkaConsumerManager 为每个 task_id 创建 asyncio.Task
       ↓
  KafkaSyncEngine.run(stop_event)
       ↓
  ┌─ while not stop_event.is_set(): ──┐
  │  consumer.getmany(最多N条, 最长T毫秒)│
  │  ↓                                │
  │  攒批 → PG批量写入                │
  │  ↓                                │
  │  写入成功 → consumer.commit()     │
  │  ↓                                │
  │  写 InfluxDB (消费速率/Lag)       │
  └───────────────────────────────────┘
       ↓
  stop_event.set() → consumer.stop() → 退出
```

---

### 5. 消息体解析

| kafka_value_format | 消息示例 | 存入 raw_doc |
|-------------------|---------|-------------|
| `json`（默认） | `{"temp":25.5,"humidity":60}` | `{"temp":25.5,"humidity":60}` |
| `text` | `sensor_A,25.5,60` | `{"raw_text":"sensor_A,25.5,60"}` |
| `json`（非 JSON 消息） | `invalid` | `{"raw_text":"invalid"}` — 自动降级 |

---

### 6. 幂等去重

每条消息以 `topic + partition + offset` 的 MD5 哈希作为主键：

```
id = md5("test_sensor_topic-0-12345")
```

写入时 `ON CONFLICT (id) DO NOTHING`，重复消费（如 rebalance 导致的重复读取）不会产生脏数据。

---

### 7. 目标表结构

```sql
CREATE TABLE kafka_test_data (
    id           VARCHAR(32) PRIMARY KEY,   -- topic+partition+offset 的 MD5
    raw_doc      JSON NOT NULL,              -- 消息内容
    collected_at VARCHAR(64)                 -- 采集时间 ISO 格式
);
```

查询示例：

```sql
SELECT id,
       raw_doc->>'temp' AS temperature,
       raw_doc->>'humidity' AS humidity,
       collected_at
FROM kafka_test_data
ORDER BY collected_at DESC
LIMIT 50;
```

---

### 8. Kafka 特有说明

| 特性 | 说明 |
|------|------|
| 生命周期 | 常驻后台 `asyncio.Task`，不同于 ARQ Worker 一次性任务 |
| offset 管理 | `enable_auto_commit=False`，手动 commit，确保写库成功的消息不会被重复消费 |
| 并发控制 | 每个 task_id 唯一一个 Consumer，`/kafka/start` 检测到已运行则跳过 |
| 停止 | `stop_event.set()` → `consumer.stop()`，最多等待 30 秒超时强制取消 |
| 自动拉起 | 系统启动时自动启动所有启用的 Kafka 任务 |
| 监控 | InfluxDB `kafka_monitor` measurement，包含 consumed/Lag/elapsed_ms |
| 暂停/取消 | 调用 `/kafka/stop` 停止消费，调用 `/kafka/start` 重新启动 |

---

### 9. Kafka 消费监控时序数据

`POST /tsync/monitor/trend`

从 InfluxDB 查询 Kafka 任务的消费速率和耗时趋势，用于 Echarts 可视化。

```json
{"task_id": "e480c7cb0ff245a7bbb6685d23615182", "minutes": 30}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 UUID（32位） |
| minutes | int | ❌ | 查询过去多少分钟的数据，默认 `30`，最小 `1` |

响应：

```json
{
  "code": 1,
  "msg": "获取监控数据成功",
  "data": {
    "xAxis": ["15:22:00", "15:22:10", "15:22:20"],
    "series": {
      "consumed": [100, 200, 150],
      "elapsed_ms": [3200, 2800, 4500]
    }
  }
}
```

| 返回字段 | 说明 |
|----------|------|
| `xAxis` | 时间点数组（HH:MM:SS 格式），直接用于 Echarts X 轴 |
| `series.consumed` | 每个批次消费的消息条数 |
| `series.elapsed_ms` | 每个批次耗时（毫秒） |

> 数据来源：Kafka 引擎每完成一次攒批写入，向 InfluxDB `kafka_monitor` measurement 写入 consumed（条数）和 elapsed_ms（耗时）。

**Echarts 前端示例：**

```javascript
// 左 Y 轴：消费条数（柱状图）
const consumedSeries = {
  name: '消费条数', type: 'bar', yAxisIndex: 0,
  data: data.series.consumed
};
// 右 Y 轴：耗时（折线图）
const elapsedSeries = {
  name: '耗时(ms)', type: 'line', yAxisIndex: 1,
  data: data.series.elapsed_ms
};
```

---

### 10. 注意事项

系统现在是一个“批处理（ARQ 调度）+ 流处理（Kafka 常驻）”双引擎并存的混合架构，同时兼容了 7 种以上的异构协议

**1. 两种任务的 UI 交互必须彻底分离**

在渲染任务列表时，必须根据 `db_type` 彻底切分按钮逻辑：

- **常规任务（SQL/API/FTP/SNMP/Socket）：**
  - 接口映射： 走 `/api/v1/tsync/run`、`/pause`、`/resume`。
  - UI 交互： 点击“执行”后，前端需要立刻通过 Axios 开启一个轮询（例如 `setInterval` 每 3 秒拉取一次 `/tasklog/detail`），并在页面上展示状态扭转。
- **流式任务（Kafka）：**
  - 接口映射： 必须专门走 `/api/v1/tsync/kafka/start` 和 `/kafka/stop`。
  - UI 交互： 绝对不要轮询进度条！ Kafka 任务没有进度。只需要一个类似开关的 UI（Start/Stop），点击启动后，按钮变成“停止”即可。

 **2. 表单按需渲染与 Payload 瘦身**

在后端的 `TaskCreateReq` 里堆了将近 50 个字段，不是全发过来的。

- 表单： 需要利用 Vue 的条件渲染（如 `v-if="formData.db_type === 'snmp'"`）来动态切换表单项。如果用户选了 FTP，就绝对不要在页面上展示 Socket 或 Kafka 的配置项。
- 发送前的清洗： 在调用 Axios POST 之前，最好做一次 Payload 瘦身。比如当前是 Socket 任务，就把 `snmp_xxx`、`kafka_xxx` 的字段全部 `delete` 掉或置为 `null`，保持请求体干净。

 **3. 统一的 Axios 响应拦截与纯粹的字典解析**

因为我们的 FastAPI 后端为了保持灵活性，去掉了复杂的返回 Pydantic 模型强校验，所有的接口都会直接抛出纯粹且统一的字典格式：`{"code": 1, "msg": "...", "data": ...}`。

- 全局拦截： 强烈建议前端在 `axios.interceptors.response` 中做全局拦截。如果 `res.data.code === 0`，直接拦截并弹出一个 Tailwind 风格的红色 Error Toast 显示 `res.data.msg`，千万不要让业务组件再去写冗长的 `if...else` 错误处理逻辑。
- 防抖处理： 像“执行”、“启动”这种核心按钮，前端在发起 Axios 请求后，必须立刻进入 `loading` 状态，禁用按钮，直到后端返回响应，防止手抖重复触发导致后台排他锁冲突或并发异常。

 **4. InfluxDB 监控数据与 Echarts 渲染对齐**

当对接 `/monitor/trend` 等图表接口时，后端返回的是时序数组，例如 `[{"_time": "...", "request_count": 50, "avg_time_ms": 42.1}]`。

- 时间轴处理： 在将这些数据喂给 Echarts 之前，注意处理 ISO 8601 时间格式（`_time`）。将 UTC 时间统一格式化为本地时间（如 `YYYY-MM-DD HH:mm`）再作为 X 轴。
- 双 Y 轴设计： 像 Socket/API/Kafka 的监控，通常有”调用量/消费量”和”延迟（ms）”两个维度，建议图表采用左侧柱状图（量）、右侧折线图（延迟）的双 Y 轴设计，这样大盘展示最具视觉冲击力。



---

## 十六、MQTT 流式采集专项

> MQTT 是物联网标准消息协议，采用**常驻订阅**模式（类似 Kafka），不走 ARQ 批处理 Worker。基于 `aiomqtt`（封装 `paho-mqtt`），支持 QoS 0/1/2、TLS 加密、持久会话（Clean Session）、自动重连和指数退避。

### MQTT vs Kafka 对比

| 特性 | MQTT | Kafka |
|------|------|-------|
| 运行模式 | 常驻 `asyncio.Task` | 常驻 `asyncio.Task` |
| 触发方式 | `/tsync/mqtt/start` | `/tsync/kafka/start` |
| 停止方式 | `/tsync/mqtt/stop` | `/tsync/kafka/stop` |
| 状态查询 | `/tsync/mqtt/status` | `/tsync/kafka/status` |
| 自动拉起 | 启动时自动启动所有启用任务 | 同 |
| 任务列表 run_status | `running` / `stopped` | 同 |
| 监控写入 | InfluxDB `mqtt_monitor` | InfluxDB `kafka_monitor` |
| 幂等策略 | topic + payload MD5 主键 | topic + partition + offset MD5 主键 |
| 断线重连 | 自动重连 + 指数退避 (5s→60s) | 不适用（Kafka Consumer 自身管理） |

---

### 1. 创建 MQTT 数据源

MQTT 数据源不需要数据库连接，连接信息（Broker 地址、Topic 等）在任务中配置：

```json
{
  “name”: “工厂传感器MQTT”,
  “type”: “mqtt”,
  “host”: “0.0.0.0”,
  “port”: 1883,
  “db_name”: “default”,
  “username”: “”,
  “password”: “”
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `”mqtt”` |
| host | string | ✅ | 随便填（如 `”0.0.0.0”`），不参与连接 |
| port | int | ✅ | 随便填（如 `0`），不参与连接 |
| db_name | string | ✅ | 随便填 |
| username | string | ❌ | 随便填，MQTT 认证在任务中配置 |
| password | string | ❌ | 随便填 |

> **注意：** MQTT 数据源仅做标识用途，实际 Broker 连接信息全部在任务请求体中配置。

---

### 2. 创建 MQTT 订阅任务

```json
{
  “task_name”: “工厂传感器数据订阅”,
  “source_id”: “你的MQTT数据源ID”,
  “mqtt_broker”: “127.0.0.1”,
  “mqtt_port”: 1883,
  “mqtt_topic”: “factory/#”,
  “mqtt_client_id”: “dataflux_sensor_01”,
  “mqtt_qos”: 1,
  “mqtt_clean_session”: 0,
  “mqtt_use_tls”: 0,
  “mqtt_keepalive”: 60,
  “mqtt_batch_size”: 100,
  “mqtt_batch_timeout_ms”: 3000,
  “mqtt_value_format”: “json”,
  “target_table”: “mqtt_sensor_data”,
  “collect_mode”: “full”,
  “sync_mode”: “insert”,
  “status”: 1
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| task_name | string | ✅ | — | 任务名称 |
| source_id | string | ✅ | — | MQTT 数据源 ID |
| mqtt_broker | string | ✅ | — | MQTT Broker 地址，如 `127.0.0.1` 或 `mqtt.example.com` |
| mqtt_port | int | ❌ | `1883` | Broker 端口，TLS 通常用 `8883` |
| mqtt_topic | string | ✅ | — | 订阅的 Topic，支持通配符 `+`（单级）和 `#`（多级） |
| mqtt_client_id | string | ❌ | `dataflux_{task_id}` | 客户端 ID，固定 ID + Clean Session=False 才能保证离线消息补发 |
| mqtt_qos | int | ❌ | `1` | 服务质量：`0`=最多一次 `1`=至少一次 `2`=恰好一次 |
| mqtt_clean_session | int | ❌ | `0` | `0`=持久会话（断线重连补发离线消息） `1`=全新会话 |
| mqtt_use_tls | int | ❌ | `0` | `0`=明文连接 `1`=TLS 加密（端口通常用 8883） |
| mqtt_keepalive | int | ❌ | `60` | 心跳间隔（秒），Broker 在 1.5 倍此时间内收不到 PINGREQ 会断开 |
| mqtt_batch_size | int | ❌ | `100` | 攒批大小，满批或超时即写 PG |
| mqtt_batch_timeout_ms | int | ❌ | `3000` | 攒批超时（毫秒），即使未满 `batch_size` 也会写入 |
| mqtt_value_format | string | ❌ | `json` | 消息体解析格式：`json` / `text` / `hex` |
| target_table | string | ❌ | 自动推导 | PG 目标表名，不传则根据 Topic 自动生成 |
| collect_mode | string | ❌ | `full` | 固定 `”full”` |
| sync_mode | string | ❌ | `insert` | 推荐 `”insert”`（幂等去重由内容 MD5 主键保证） |
| status | int | ❌ | `1` | `1`=启用 `0`=停用 |

**Topic 通配符示例：**

| Topic | 匹配 |
|-------|------|
| `factory/sensor/temp` | 精确匹配单个主题 |
| `factory/+/temp` | 匹配 `factory/sensor1/temp`、`factory/sensor2/temp` 等 |
| `factory/#` | 匹配 `factory` 下所有子级，如 `factory/sensor/temp`、`factory/device/status` |

---

### 3. MQTT 消息体解析

| mqtt_value_format | 消息示例 | 存入 raw_doc |
|-------------------|---------|-------------|
| `json`（默认） | `{“temp”: 25.5, “humidity”: 60}` | `{“temp”: 25.5, “humidity”: 60}` |
| `text` | `sensor_A,25.5,60` | `{“raw_text”: “sensor_A,25.5,60”}` |
| `hex` | `0x00 0xFF 0xA1` | `{“raw_hex”: “00ffa1”}` |
| `json`（非法 JSON） | `not valid` | `{“raw_text”: “not valid”}` — 自动降级 |

---

### 4. MQTT 专属接口

MQTT 不通过 `/tsync/run` 触发（那是 ARQ 一次性批处理任务），而是通过常驻订阅管理：

| 接口 | 说明 |
|------|------|
| `POST /tsync/mqtt/start` | 启动指定任务的 MQTT Consumer |
| `POST /tsync/mqtt/stop` | 停止指定任务的 MQTT Consumer |
| `POST /tsync/mqtt/status` | 查询指定任务的 Consumer 状态 |

**启动 Consumer：**

```json
POST /tsync/mqtt/start
{“task_id”: “e480c7cb0ff245a7bbb6685d23615182”}
```

响应：

```json
{“code”: 1, “msg”: “订阅已启动”, “data”: null}
```

> 系统启动时（FastAPI lifespan）会自动拉起所有 `status=1` 的 MQTT 任务，无需手动逐个启动。

**停止 Consumer：**

```json
POST /tsync/mqtt/stop
{“task_id”: “e480c7cb0ff245a7bbb6685d23615182”}
```

响应：

```json
{“code”: 1, “msg”: “订阅已停止”, “data”: null}
```

**查询状态：**

```json
POST /tsync/mqtt/status
{“task_id”: “e480c7cb0ff245a7bbb6685d23615182”}
```

响应：

```json
{“code”: 1, “msg”: “获取成功”, “data”: {“status”: “running”}}
```

> `status` 取值：`”running”`（运行中）/ `”stopped”`（已停止）

---

### 5. MQTT Consumer 生命周期

| 操作 | DB `status` 变化 | Consumer 行为 | 说明 |
|------|-----------------|---------------|------|
| 新建任务 | `status=1` | **不启动** | 仅存入数据库 |
| 点击「启用」 | `0→1` | **不启动** | 把启动权交给 `/mqtt/start` |
| 点击「停用」 | `1→0` | **强制停止** | DB 改为 0 + 立即调用 `mqtt_manager.stop()` |
| 点击「删除」 | 记录删除 | **先停后删** | 先 `mqtt_manager.stop()` 再删 DB |
| `/mqtt/start` | 不变 | **启动** | 仅当 `status=1` 时生效 |
| `/mqtt/stop` | 不变 | **停止** | 立即停止，不阻塞 |
| 系统重启 | 不变 | **自动拉起** | 启动时自动启动所有 `status=1` 的 MQTT 任务 |

---

### 6. MQTT 消费流程图

```
FastAPI 启动 (lifespan)
  ↓
start_all_mqtt_tasks()
  ├── JOIN sys_data_source WHERE type=”mqtt” AND CollectTask.status=1
  └── 为每个任务调用 mqtt_manager.start()
       ↓
  MqttConsumerManager 为每个 task_id 创建 asyncio.Task
       ↓
  MqttSyncEngine.run(stop_event)
       ↓
  ┌─ while not stop_event.is_set(): ────────┐
  │  async with aiomqtt.Client(...) as client│
  │    await client.subscribe(topic, qos)    │
  │    async for message in client.messages: │
  │      batch.append(message)               │
  │      满批/超时 → to_thread(PG写入)      │
  │      to_thread(InfluxDB监控)             │
  │  ── 异常断连 ──                          │
  │  抢救性 flush batch → 指数退避 → 重连   │
  └──────────────────────────────────────────┘
       ↓
  stop_event.set() → client.disconnect() → 退出
```

---

### 7. 幂等去重策略

每条消息以 **Topic + Payload 内容的 MD5 哈希** 作为主键：

```
id = md5(“factory/sensor/temp:{payload_hex}”)
```

写入时使用 `ON CONFLICT (id) DO NOTHING`，即使 QoS 1/2 重传导致同一条消息被重复消费，也不会产生脏数据。

> **与 Kafka 的区别：** Kafka 用 `topic + partition + offset` 生成 ID（天然唯一），MQTT 没有 offset 概念，用 Payload 内容哈希替代。两个完全相同的 Payload 发到同一个 Topic 会被视为同一条（合理——MQTT 场景下一般不会有意发两条完全相同的消息）。

---

### 8. 目标表结构

```sql
CREATE TABLE mqtt_sensor_data (
    id            VARCHAR(32) PRIMARY KEY,  -- topic + payload 的 MD5
    topic         VARCHAR(255),             -- 消息来源 Topic
    raw_doc       JSON NOT NULL,            -- 消息内容
    collected_at  VARCHAR(64)               -- 采集时间 ISO 格式
);
```

查询示例：

```sql
SELECT id,
       topic,
       raw_doc->>'temp' AS temperature,
       raw_doc->>'humidity' AS humidity,
       collected_at
FROM mqtt_sensor_data
ORDER BY collected_at DESC
LIMIT 50;
```

---

### 9. MQTT 监控时序数据

`POST /tsync/monitor/trend`

从 InfluxDB 查询 MQTT 任务的消费速率和耗时趋势（与 Kafka 共用同一接口，自动识别 `mqtt_monitor` measurement）。

```json
{“task_id”: “e480c7cb0ff245a7bbb6685d23615182”, “minutes”: 30}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 任务 UUID（32位） |
| minutes | int | ❌ | 查询过去多少分钟，默认 `30` |

响应：

```json
{
  “code”: 1,
  “msg”: “获取监控数据成功”,
  “data”: {
    “xAxis”: [“16:30:00”, “16:30:03”, “16:30:06”],
    “series”: {
      “consumed”: [100, 200, 150],
      “elapsed_ms”: [3200, 2800, 4500]
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `xAxis` | 时间点（HH:MM:SS），用于 Echarts X 轴 |
| `series.consumed` | 每个批次消费的消息条数 |
| `series.elapsed_ms` | 每个批次写入耗时（毫秒） |

> 数据来源：MQTT 引擎每完成一次攒批写入，向 InfluxDB `mqtt_monitor` measurement 写入 consumed（条数）和 elapsed_ms（耗时）。

---

### 10. MQTT 特有说明

| 特性 | 说明 |
|------|------|
| 生命周期 | 常驻后台 `asyncio.Task`，不同于 ARQ Worker 一次性任务 |
| 自动重连 | 断线后指数退避重连（5s → 10s → 20s → 40s → 60s），连接成功后重置 |
| 数据安全 | 断连前抢救性 flush 攒批缓冲区中的消息，最小化数据丢失 |
| 并发控制 | 每个 task_id 唯一一个 Consumer，`/mqtt/start` 检测到已运行则跳过 |
| 自动拉起 | 系统启动时自动启动所有启用状态的 MQTT 任务 |
| 监控 | InfluxDB `mqtt_monitor` measurement，记录 consumed + elapsed_ms |
| 持久会话 | `mqtt_clean_session=0` + 固定 `client_id` = Broker 缓存离线消息，重连后补发 |
| 停止 | `stop_event.set()` → `client.disconnect()` 3s 超时 → tail flush → 退出 |
| Windows 兼容 | 顶层设置 `WindowsSelectorEventLoopPolicy`，`aiomqtt` 清理噪音自动消音 |

---

### 11. 注意事项

1. **MQTT 和 Kafka 一样是常驻任务**，任务列表中”执行”按钮对它们无效——应使用专属的 Start/Stop 按钮。
2. **`/tsync/run` 会拒绝 MQTT 任务**，返回提示”请使用 /tsync/mqtt/start 启动”。
3. **停用 MQTT 任务会立即停止底层 Consumer**，`run_status` 变为 `stopped`。
4. **`mqtt_clean_session=0` + 固定 `client_id`** 是保证断线不丢消息的关键组合——不要随便改 `client_id`。
5. **Topic 通配符 `#` 会匹配所有子级**，如果 Broker 上消息量巨大，注意调整 `batch_size` 和 `batch_timeout_ms` 避免攒批缓冲区 OOM。



---

## 十七、RabbitMQ 流式采集专项

> RabbitMQ 基于 AMQP 0-9-1 协议，采用**常驻消费**模式（类似 Kafka/MQTT），不走 ARQ 批处理 Worker。基于 `aio_pika`（asyncio 原生），支持交换机绑定、队列声明、QoS 预取、手动 ACK/NACK，**写库成功后才 ACK，失败则整批 NACK 重新入队——保证零丢失**。

### 三大流式引擎对比

| 特性 | RabbitMQ | Kafka | MQTT |
|------|----------|-------|------|
| 运行模式 | 常驻 `asyncio.Task` | 同 | 同 |
| 触发方式 | `/rabbitmq/start` | `/kafka/start` | `/mqtt/start` |
| 停止方式 | `/rabbitmq/stop` | `/kafka/stop` | `/mqtt/stop` |
| 状态查询 | `/rabbitmq/status` | `/kafka/status` | `/mqtt/status` |
| 自动拉起 | ✅ 启动时自动拉起所有启用任务 | ✅ | ✅ |
| 消息可靠性 | **写库成功 → ACK / 写库失败 → NACK 重新入队** | offset commit | QoS 重传 |
| 幂等策略 | routing_key + body MD5 | topic+partition+offset MD5 | topic+payload MD5 |
| 监控写入 | InfluxDB `rabbitmq_monitor` | `kafka_monitor` | `mqtt_monitor` |
| 并发控制 | `prefetch_count` 预取 | `max_records` 攒批 | `batch_size` 攒批 |

---

### 1. 创建 RabbitMQ 数据源

```json
{
  "name": "业务队列RabbitMQ",
  "type": "rabbitmq",
  "host": "0.0.0.0",
  "port": 5672,
  "db_name": "default",
  "username": "",
  "password": ""
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"rabbitmq"` |
| host | string | ✅ | 随便填（如 `"0.0.0.0"`），不参与连接 |
| port | int | ✅ | 随便填（如 `0`），不参与连接 |
| db_name | string | ✅ | 随便填 |
| username | string | ❌ | 随便填，RabbitMQ 认证在任务中配置 |
| password | string | ❌ | 随便填 |

---

### 2. 创建 RabbitMQ 消费任务

**基础模式（直连队列）：**

```json
{
  "task_name": "业务日志队列消费",
  "source_id": "你的RabbitMQ数据源ID",
  "mq_host": "127.0.0.1",
  "mq_port": 5672,
  "mq_vhost": "/",
  "mq_queue": "business_logs",
  "mq_prefetch_count": 50,
  "mq_durable": 1,
  "mq_batch_size": 100,
  "mq_batch_timeout_ms": 3000,
  "mq_value_format": "json",
  "target_table": "mq_business_logs",
  "collect_mode": "full",
  "sync_mode": "insert",
  "status": 1
}
```

**交换机绑定模式：**

```json
{
  "task_name": "订单事件消费",
  "source_id": "你的RabbitMQ数据源ID",
  "mq_host": "127.0.0.1",
  "mq_port": 5672,
  "mq_vhost": "/",
  "mq_queue": "order_events",
  "mq_exchange": "order_topic",
  "mq_exchange_type": "topic",
  "mq_routing_key": "order.#",
  "mq_prefetch_count": 30,
  "mq_batch_size": 200,
  "mq_batch_timeout_ms": 5000,
  "mq_value_format": "json",
  "target_table": "mq_order_events",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| task_name | string | ✅ | — | 任务名称 |
| source_id | string | ✅ | — | RabbitMQ 数据源 ID |
| mq_host | string | ✅ | — | RabbitMQ Broker 地址 |
| mq_port | int | ❌ | `5672` | Broker 端口 |
| mq_vhost | string | ❌ | `"/"` | 虚拟主机（vhost），多租户隔离 |
| mq_queue | string | ✅ | — | 队列名称 |
| mq_exchange | string | ❌ | — | 交换机名称，不传则直连队列消费 |
| mq_exchange_type | string | ❌ | `"direct"` | 交换机类型：`direct` / `topic` / `fanout` / `headers` |
| mq_routing_key | string | ❌ | — | 路由键，topic 模式支持通配符 `*`（单词）和 `#`（多词） |
| mq_durable | int | ❌ | `1` | `1`=持久化队列（Broker 重启不丢定义） `0`=非持久 |
| mq_prefetch_count | int | ❌ | `50` | 预取消息数量，控制消费者内存占用 |
| mq_batch_size | int | ❌ | `100` | 攒批大小，满批或超时即写 PG + 批量 ACK |
| mq_batch_timeout_ms | int | ❌ | `3000` | 攒批超时（毫秒） |
| mq_value_format | string | ❌ | `json` | 消息体解析格式：`json` / `text` / `hex` |
| target_table | string | ❌ | `mq_{队列名}` | PG 目标表名 |
| collect_mode | string | ❌ | `full` | 固定 `"full"` |
| sync_mode | string | ❌ | `insert` | 推荐 `"insert"`（幂等去重由 MD5 主键保证） |
| status | int | ❌ | `1` | `1`=启用 `0`=停用 |

---

### 3. 消息体解析

| mq_value_format | 消息示例 | 存入 raw_doc |
|-----------------|---------|-------------|
| `json`（默认） | `{"order_id":123,"amount":99.9}` | `{"order_id": 123, "amount": 99.9}` |
| `text` | `order_123,completed,99.9` | `{"raw_text": "order_123,completed,99.9"}` |
| `hex` | `0x00 0xFF 0xA1` | `{"raw_hex": "00ffa1"}` |
| `json`（非法 JSON） | `not valid` | `{"raw_text": "not valid"}` — 自动降级 |

---

### 4. RabbitMQ 专属接口

| 接口 | 说明 |
|------|------|
| `POST /tsync/rabbitmq/start` | 启动指定任务的 RabbitMQ Consumer |
| `POST /tsync/rabbitmq/stop` | 停止指定任务的 RabbitMQ Consumer |
| `POST /tsync/rabbitmq/status` | 查询指定任务的 Consumer 状态 |

**启动 Consumer：**

```json
POST /tsync/rabbitmq/start
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "消费已启动", "data": null}
```

> 系统启动时（FastAPI lifespan）会自动拉起所有 `status=1` 的 RabbitMQ 任务。

**停止 Consumer：**

```json
POST /tsync/rabbitmq/stop
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "消费已停止", "data": null}
```

**查询状态：**

```json
POST /tsync/rabbitmq/status
{"task_id": "e480c7cb0ff245a7bbb6685d23615182"}
```

响应：

```json
{"code": 1, "msg": "获取成功", "data": {"status": "running"}}
```

---

### 5. 消息可靠性保证（核心机制）

RabbitMQ 引擎的设计目标是**金融级零丢失 + 毒药消息自动隔离**：

```
while 消费中:
  1. async for message in queue:          ← 从队列拉取消息
  2. batch.append(message)                ← 进入内存攒批缓冲区
  3. pending_messages.append(message)      ← 保存原始引用（用于 ACK/NACK）

  4. 满批 或 超时 → 写 PG:
     ├─ 写库成功 → 批量 ACK 
     ├─ DB 宕机 (OperationalError) → 整批 NACK + 等 5s 重试 ⏳
     └─ 其他异常 →  降级「单条排雷」:
           ├─ 单条成功 → ACK 
           └─ 单条失败（毒药消息）
               → 写 PG mq_dead_letter 表（隔离备查）
               → ACK（从队列移除，阻断死循环）🗑️
```

**三层异常处理逻辑：**

| 异常类型 | 判定 | 行为 |
|----------|------|------|
| `OperationalError` | 数据库宕机/连接断开 | 整批 NACK 重新入队，等 5 秒后重试。网络恢复后继续消费 |
| 批次写入失败（非 DB） | 某条消息数据格式有问题 | **不整批退回**——逐条单写排雷，精确定位毒药 |
| 单条写入失败 | 该条消息与 PG 表结构不兼容 | **写 PG 死信表 → ACK 移出队列**，阻断 NACK 死循环 |

**死信隔离机制（`mq_dead_letter` 表）：**

| 场景 | 行为 |
|------|------|
| 正常消费 | 攒批写入 PG → 成功 → 批量 ACK |
| DB 宕机 | 整批 NACK + 5s 延迟重试，DB 恢复后自动继续 |
| 毒药消息（类型不兼容/字段超长） | 单条降级失败 → 原始消息 + 错误原因写入 `mq_dead_letter` → ACK 移除 |
| 极端情况（死信表写不进） | `msg.nack(requeue=True)` 退回队列保底（极少发生） |
| 进程崩溃 | 消息仍在 Broker 队列中（未 ACK），重启后重新投递 |
| Broker 重启 | `durable=1` 队列定义持久化，重启后队列和消息仍存在 |

> **前端可基于 `mq_dead_letter` 表开发「死信管理」页面**——查看失败的原始消息、错误原因，修改数据后一键重发到目标队列。

---

### 6. 交换机和队列拓扑

```
[Producer] → Exchange (topic/direct/fanout) → routing_key → Queue → [Consumer]
                                                              ↑
                                                     mq_prefetch_count
                                                     控制每次预取量
```

**配置场景：**

| 场景 | mq_exchange | mq_exchange_type | mq_routing_key |
|------|-------------|-----------------|----------------|
| 直连队列（最简单） | 不传 | — | 不传 |
| 精确路由 | `"order_ex"` | `"direct"` | `"order.created"` |
| 模式匹配 | `"order_ex"` | `"topic"` | `"order.*"` |
| 广播 | `"logs_ex"` | `"fanout"` | 不传（广播忽略 routing_key） |

---

### 7. 幂等去重策略

每条消息以 **routing_key + body 内容的 MD5 哈希** 作为主键：

```
id = md5("order.created:{body_hex}")
```

写入时 `ON CONFLICT (id) DO NOTHING`。重新投递（NACK 后重入队）的同一条消息会产生相同的 ID，不会插入重复行。

---

### 8. 目标表结构

```sql
CREATE TABLE mq_business_logs (
    id            VARCHAR(32) PRIMARY KEY,  -- routing_key + body 的 MD5
    routing_key   VARCHAR(255),             -- 消息的路由键
    raw_doc       JSON NOT NULL,            -- 消息内容
    collected_at  VARCHAR(64)               -- 采集时间 ISO 格式
);
```

**死信表（毒药消息隔离）：**

```sql
CREATE TABLE mq_dead_letter (
    id            VARCHAR(64) PRIMARY KEY,  -- UUID 主键
    task_id       VARCHAR(64),              -- 关联的任务 ID
    queue_name    VARCHAR(255),             -- 来源队列名
    routing_key   VARCHAR(255),             -- 消息路由键
    raw_payload   TEXT NOT NULL,            -- 原始消息体（String 最高容错）
    error_reason  TEXT,                     -- PG 写入失败的错误原因
    created_at    VARCHAR(64)               -- 隔离时间 ISO 格式
);
```

查询死信示例：

```sql
SELECT id, queue_name, routing_key,
       raw_payload,
       error_reason,
       created_at
FROM mq_dead_letter
WHERE task_id = 'your-task-id'
ORDER BY created_at DESC
LIMIT 50;
```

> 死信表是**全系统共享**的——所有 RabbitMQ 任务的毒药消息都写入同一张表，通过 `task_id` 和 `queue_name` 区分来源。

---

### 9. 监控时序数据

与 Kafka/MQTT 共用 `/tsync/monitor/trend` 接口，后端根据任务类型自动选择 `rabbitmq_monitor` measurement。

```json
POST /tsync/monitor/trend
{"task_id": "e480c7cb0ff245a7bbb6685d23615182", "minutes": 30}
```

响应格式与 Kafka/MQTT 一致，`consumed` + `elapsed_ms` 时序数组。

---

### 10. RabbitMQ Consumer 生命周期

| 操作 | DB `status` | Consumer 行为 |
|------|------------|---------------|
| 新建任务 | `1` | **不启动** |
| 点击「启用」 | `0→1` | **不启动**（把启动权交给 `/rabbitmq/start`） |
| 点击「停用」 | `1→0` | **强制停止** Consumer |
| 点击「删除」 | 记录删除 | **先停 Consumer 后删记录** |
| `/rabbitmq/start` | 不变 | **启动**（仅当 `status=1`） |
| `/rabbitmq/stop` | 不变 | **停止**（非阻塞） |
| 系统重启 | 不变 | **自动拉起**所有 `status=1` 的任务 |

---

### 11. 注意事项

1. **RabbitMQ 是常驻任务**，任务列表中「执行」按钮对它无效——应使用专属的 Start/Stop 按钮。`/tsync/run` 会拦截并提示使用 `/rabbitmq/start`。
2. **毒药消息自动隔离至 `mq_dead_letter` 表**——数据格式与 PG 表不兼容的消息不会被反复 NACK 形成死循环，而是自动写入死信表并从队列移除。可通过数据探索接口或自定义页面查看隔离的消息，修复数据后重新发送到队列。
3. **`mq_durable=1` 仅持久化队列定义（元数据）**——消息持久化需要在 Producer 端设置 `delivery_mode=2`。
4. **`prefetch_count` 不是批次大小**——它控制 RabbitMQ 推送给消费者的未确认消息数上限。`batch_size` 是应用层攒批写入 PG 的大小。二者配合使用。
5. **认证凭据**：当前版本 RabbitMQ 认证使用默认的 `guest`/`guest`，如需自定义认证，可通过 `config_json` 或后续新增 `mq_username`/`mq_password` 字段配置。



---

## 十八、OSS（S3 兼容）对象存储采集专项

> 基于 `boto3` S3 协议，支持阿里云 OSS / AWS S3 / MinIO 等所有 S3 兼容存储。**批处理模式**（走 ARQ Worker），支持单文件下载和批量前缀采集，MD5 增量去重，结构化文件解析入库。AK/SK 凭证存储在数据源中，任务侧无需重复填写。

### vs FTP 对比

| 特性 | OSS / S3 | FTP / SFTP |
|------|----------|------------|
| 运行模式 | ARQ Worker 一次性批处理 | 同 |
| 协议 | S3（boto3） | FTP / FTPS / SFTP |
| 凭证管理 | 数据源 `username`/`password` 存 AK/SK | 数据源 + ftp_url |
| 单文件 | `oss_object_key` 指定完整对象 Key | `ftp_path` 指定远程路径 |
| 批量模式 | `oss_prefix` 前缀列举 + 自动翻页 | 不支持（需逐个指定文件） |
| MD5 去重 | ✅ 通过 oss_file_record 表 | ✅ 通过 ftp_file_record 表 |
| 文件解析 | CSV / JSON / YAML / Excel / XML | 同 |
| 端点风格 | `virtual`（Bucket 在域名） / `path`（Bucket 在路径） | — |

---

### 1. 创建 OSS 数据源

> **关键设计：** 敏感凭证（AccessKey / SecretKey）存储在数据源中，任务创建时无需重复填写。`username` 存 AK，`password` 存 SK，`host` 存 Endpoint 域名，`db_name` 存默认 Bucket。

```json
{
  "name": "阿里云OSS生产",
  "type": "oss",
  "host": "oss-cn-hangzhou.aliyuncs.com",
  "port": 443,
  "db_name": "my-bucket",
  "username": "LTAI5txxxxxxxxxxxxx",
  "password": "xxxxxxxxxxxxxxxxxxxx",
  "config_json": {"region": "cn-hangzhou", "addressing_style": "virtual"}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 数据源别名 |
| type | string | ✅ | 固定 `"oss"` |
| host | string | ✅ | Endpoint 域名（如 `oss-cn-hangzhou.aliyuncs.com`），不含 `https://` |
| port | int | ✅ | 端口，HTTPS 用 `443`，HTTP 用 `80` |
| db_name | string | ✅ | 默认 Bucket 名称，任务可覆盖 |
| username | string | ✅ | **AccessKeyId** |
| password | string | ✅ | **AccessKeySecret** |
| config_json | object | ❌ | 扩展配置，见下方 |

**config_json 可选项：**

| 键 | 默认值 | 说明 |
|----|--------|------|
| region | `"us-east-1"` | 区域标识（阿里云必须填正确区域） |
| addressing_style | `"virtual"` | Bucket 寻址风格：`virtual`（Bucket 在域名中） / `path`（Bucket 在路径中） |

---

### 2. 凭证自动注入机制

**Worker 组装执行参数时的兜底链：**

```
oss_access_key  = 任务显式传的值 || 数据源 username
oss_secret_key  = 任务显式传的值 || 数据源 password
oss_endpoint    = 任务显式传的值 || https://{数据源 host}
oss_bucket      = 任务显式传的值 || 数据源 db_name
```

> **前端只需让用户选数据源**，AK/SK 输入框可以删掉。只有在极少数需要针对某个任务使用不同凭证时，才在任务中显式覆盖。

**匿名免密模式：** 当数据源的 `username`（AK）和 `password`（SK）都为空时，引擎自动切入 **UNSIGNED 匿名模式**——不进行签名验证，直接访问公开 Bucket 或 MinIO 免密实例。无需额外配置。

---

### 3. 单文件模式

下载指定对象 Key，支持 MD5 去重和结构化解析。重复执行时文件未变化则自动跳过。

```json
{
  "task_name": "采集月度报表",
  "source_id": "你的OSS数据源ID",
  "oss_object_key": "reports/2026/06/summary.json",
  "oss_bucket": "my-bucket",
  "file_parse": 1,
  "file_type": "json",
  "target_table": "oss_monthly_summary",
  "collect_mode": "full",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| task_name | string | ✅ | — | 任务名称 |
| source_id | string | ✅ | — | OSS 数据源 ID |
| oss_object_key | string | ✅ | — | 对象的完整 Key（路径），如 `data/report.csv` |
| oss_bucket | string | ❌ | 数据源的 db_name | Bucket 名称 |
| oss_endpoint | string | ❌ | 数据源拼接 | Endpoint 完整 URL |
| oss_region | string | ❌ | `"us-east-1"` | 区域 |
| oss_addressing_style | string | ❌ | `"virtual"` | `virtual` / `path` |
| oss_use_ssl | int | ❌ | `1` | `0`=HTTP `1`=HTTPS |
| file_parse | int | ❌ | `0` | `1`=解析文件内容入库 `0`=只下载不解析 |
| file_type | string | ❌ | `"auto"` | `auto` / `csv` / `json` / `yaml` / `xlsx` / `xml` |
| target_table | string | ❌ | `oss_{bucket名}` | PG 目标表名 |
| sync_mode | string | ❌ | `insert` | 推荐 `"insert"`（幂等由内容 MD5 主键保证） |
| schedule_type | string | ❌ | `"none"` | 可配置定时调度（如 `daily / 02:00` 每天凌晨采集） |

---

### 4. 批量前缀模式

列举指定前缀下的**所有**对象，逐个下载处理。自动处理分页（超过 1000 个对象时翻页）。单个对象失败不中断批次，继续处理下一个。

```json
{
  "task_name": "采集6月所有日志",
  "source_id": "你的OSS数据源ID",
  "oss_prefix": "logs/2026/06/",
  "oss_bucket": "my-bucket",
  "oss_max_keys": 500,
  "file_parse": 1,
  "file_type": "csv",
  "target_table": "oss_june_logs",
  "schedule_type": "daily",
  "schedule_value": "03:00",
  "collect_mode": "full",
  "status": 1
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| oss_prefix | string | ✅ | — | 对象 Key 前缀，如 `logs/2026/`，匹配该前缀下所有对象 |
| oss_max_keys | int | ❌ | `1000` | 单次 API 调用列举的最大对象数（翻页自动处理，这只是分页大小） |

> **注意：** `oss_object_key`（单文件）和 `oss_prefix`（批量）二选一。都传则 `oss_object_key` 优先。

---

### 5. 消息体 / 文件解析

复用与 FTP 相同的解析引擎，支持 5 种结构化格式：

| file_type | 行为 | 目标表结构 |
|-----------|------|-----------|
| `csv` | 首行作为列名，自动探测 UTF-8/GBK 编码 | `id` UUID + `source_key` + `raw_doc` JSON |
| `json` | 顶层数组 → 逐条入行；单对象 → 存为一行 | 同上 |
| `yaml` | 支持多文档（`---` 分隔），每个文档存一行 | 同上 |
| `xlsx` | 读取所有工作表，首行为列名 | 同上 |
| `xml` | 递归解析为嵌套 dict，存为一行 | 同上 |
| `binary` / 不解析 | 仅下载到本地，不入库 | — |

**目标表结构：**

```sql
CREATE TABLE oss_monthly_summary (
    id          VARCHAR(32) PRIMARY KEY,   -- 内容 MD5 主键（幂等去重）
    source_key  VARCHAR(500),              -- OSS 对象 Key（溯源）
    raw_doc     JSON NOT NULL              -- 文件解析后的结构化数据
);
```

---

### 6. OSS 文件记录表 `oss_file_record`

每次采集都会记录元数据，用于增量去重（MD5 未变化则跳过）：

| 字段 | 说明 |
|------|------|
| task_id | 关联任务 ID |
| object_key | OSS 对象 Key（完整路径） |
| local_path | 本地下载存储路径 |
| file_name | 文件名 |
| file_size | 文件大小（字节） |
| md5 | 文件 MD5 哈希，增量去重判断依据 |
| file_type | 文件类型 |
| is_parsed | `0`=未解析 `1`=已解析入库 |
| parsed_rows | 解析写入的行数 |
| downloaded_at | 首次下载时间 |

---

### 7. 采集流程图

```
1. 解析任务参数：单文件模式 vs 批量前缀模式
2. 连接 S3 客户端（boto3，支持 virtual / path 寻址）
3. 确定待处理对象列表：
   ├─ 单文件: [oss_object_key]
   └─ 批量: list_objects_v2(Prefix) → 自动翻页 → 过滤目录占位对象
         ↓
4. 逐个处理对象 (每对象前后探测暂停/取消信号):
   ├─ 查 oss_file_record 历史 MD5
   ├─ download_file 下载到本地
   ├─ 计算 MD5 → 与历史对比 → 相同则跳过
   ├─ 保存记录到 oss_file_record
   └─ file_parse=1 且非 binary → 解析入库:
        CSV → 流式解析
        JSON → 数组/单对象
        YAML → 多文档
        Excel → 多工作表
        XML → 递归转 dict
        每行以内容 MD5 为主键 → ON CONFLICT DO NOTHING 幂等写入
5. 单个对象失败不中断批次，记录日志后继续处理下一个
6. 返回统计结果
```

---

### 8. 幂等去重策略

**文件级去重：** 同一对象 Key 重复执行时，如果 MD5 未变化，自动跳过下载和解析。

**行级幂等：** 每行数据以内容 MD5 哈希作为主键，`ON CONFLICT (id) DO NOTHING`。即使同一文件重复解析多次，也不会产生重复行。

```
// 文件未变化
{
  "status": "skipped",
  "object_key": "reports/2026/06/summary.json",
  "records": 0
}
```

---

### 9. OSS 目录树勘探（配置辅助）

> 类似 FTP 的目录树勘探，用于在创建 OSS 采集任务前预览 Bucket 内的目录结构和文件列表。采用 S3 `Delimiter='/'` 机制按目录折叠，支持懒加载（逐级展开）。自动适配匿名免密和 signed 认证，自动推断 virtual/path 寻址风格。

`POST /datasource/oss/tree`

**请求：**

```json
{
  "source_id": "550e8400e29b41d4a716446655440000",
  "prefix": "cjcy_files/"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | OSS 数据源 UUID（32位） |
| prefix | string | ❌ | 当前目录前缀。查 Bucket 根目录传空字符串 `""`；查子目录传如 `"data/2026/"` |

**响应：**

```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    {
      "type": "folder",
      "name": "reports",
      "full_path": "cjcy_files/reports/",
      "is_leaf": false
    },
    {
      "type": "file",
      "name": "summary.json",
      "full_path": "cjcy_files/summary.json",
      "size": 204800,
      "last_modified": "2026-06-17T10:30:00",
      "is_leaf": true
    }
  ]
}
```

| 响应字段 | 类型 | 说明 |
|----------|------|------|
| type | string | `"folder"`（目录）或 `"file"`（文件） |
| name | string | 文件/目录名（用于前端树节点展示） |
| full_path | string | 完整 Key（前端展开时回传给 `prefix`） |
| size | int | 文件大小（字节），仅文件有 |
| last_modified | string | 最后修改时间 ISO 格式，仅文件有 |
| is_leaf | bool | 是否叶子节点：`true`=文件 `false`=目录（对齐 ElementPlus/AntDesign 树组件） |

**前端懒加载交互示例：**

```javascript
// 1. 初始加载 Bucket 根目录
const root = await fetch("/api/v1/datasource/oss/tree", {
  method: "POST",
  body: JSON.stringify({ source_id: "xxx", prefix: "" })
});
// → 返回根目录下的文件夹和文件列表

// 2. 用户点击展开 cjcy_files/ 文件夹
const children = await fetch("/api/v1/datasource/oss/tree", {
  method: "POST",
  body: JSON.stringify({ source_id: "xxx", prefix: "cjcy_files/" })
});
// → 返回 cjcy_files/ 下的子目录和文件

// 3. 继续展开更深层级...
```

**认证自动适配：**

| 数据源配置 | 引擎行为 |
|-----------|----------|
| `username`/`password` 有值 | s3v4 签名认证 |
| `username`/`password` 都为空 | UNSIGNED 匿名免密模式 |

**寻址风格自动推断：**

| host 特征 | addressing_style |
|-----------|-----------------|
| 包含 `127.0.0.1` 或 `:9000` | `path`（适合 MinIO） |
| 其他（如 `oss-cn-hangzhou.aliyuncs.com`） | `virtual`（适合阿里云/AWS） |

---

### 10. 区别

| 引擎 | 适用场景 | 运行模式 | 凭证管理 |
|------|----------|----------|----------|
| **OSS** | S3 兼容对象存储（阿里云/AWS/MinIO） | ARQ Worker 批处理 | 数据源 username/password |
| FTP | 传统 FTP/SFTP 文件服务器 | ARQ Worker 批处理 | 数据源 + ftp_url |
| API | HTTP 接口 JSON 数据 | ARQ Worker 批处理 | 数据源或任务请求头 |
| Kafka | 流式消息队列 | 常驻 Consumer | 任务 bootstrap_servers |
| MQTT | 物联网消息 | 常驻 Consumer | 任务 broker |
| RabbitMQ | AMQP 消息队列 | 常驻 Consumer | 任务 mq_host |

---

### 10. 注意事项

1. **OSS 是批处理任务**，通过 `/tsync/run` 触发执行或配置定时调度。
2. **凭证自动从数据源注入**——创建 OSS 任务时不需要填 AK/SK。如果需要针对特定任务使用不同凭证，才在任务中显式填写覆盖。
3. **单个对象失败不中断批次**——如果批量模式中某个文件下载/解析失败，引擎记录错误日志后继续处理下一个对象，不会整个任务报错退出。
4. **批量模式注意对象数量**——`oss_max_keys` 只是单次 API 调用的分页大小，引擎会自动翻页拉取全部匹配对象。如果前缀下有几百万个对象，建议切分成更细的前缀分批执行。
5. **MinIO 兼容配置**——使用 MinIO 时，`oss_endpoint` 填 `http://192.168.1.100:9000`，`oss_addressing_style` 设为 `"path"`，`oss_use_ssl` 设为 `0`。
6. **阿里云 OSS 注意 Region**——`config_json.region` 必须和 Bucket 所在地域一致（如 `cn-hangzhou`），否则签名校验失败。
7. **匿名免密访问**——公开 Bucket 或 MinIO 免密实例：数据源 `username`/`password` 留空即可，引擎自动走 UNSIGNED 模式。
8. **文件同步明细**——任务执行后可通过 `/tsync/record/list` 查询每个文件的下载状态、MD5、解析行数，前端可直接渲染为文件明细表格。



---

## 十九、数据探索 `/explorer`

> 通用数据查询模块，用于探索采集落地库中所有表的表结构、字段信息和数据内容。查询目标库为采集结果库（`dataflux_collected`），而非系统元数据库。

### 1. 获取所有表列表

`POST /explorer/tables/list`

支持关键字模糊搜索表名。

```json
// 查全部
{}

// 按关键字过滤
{“keyword”: “kafka”}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | ❌ | 表名模糊搜索关键字，不传则返回全部表名 |

响应：

```json
{
  “code”: 1,
  “msg”: “获取表列表成功”,
  “data”: [
    “api_rainyun_coupons”,
    “ftp_test_csv”,
    “kafka_test_data”,
    “kafka_test_sensor_topic”,
    “snmp_interfaces”,
    “socket_test_data”,
    “sys_collect_record”,
    “sys_collect_task”,
    “sys_data_source”,
    “sys_task_log”
  ]
}
```

---

### 2. 获取表结构详情

`POST /explorer/tables/columns`

获取指定表的所有字段名、类型、是否可空、默认值、注释等元数据。

```json
{“table_name”: “kafka_test_data”}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| table_name | string | ✅ | 目标表名（采集落地库中的表） |

响应：

```json
{
  “code”: 1,
  “msg”: “获取表结构成功”,
  “data”: [
    {
      “name”: “id”,
      “type”: “VARCHAR(32)”,
      “nullable”: false,
      “default”: null,
      “comment”: null
    },
    {
      “name”: “raw_doc”,
      “type”: “JSON”,
      “nullable”: false,
      “default”: null,
      “comment”: null
    },
    {
      “name”: “collected_at”,
      “type”: “VARCHAR(64)”,
      “nullable”: true,
      “default”: null,
      “comment”: null
    }
  ]
}
```

---

### 3. 通用表数据分页查询

`POST /explorer/tables/data`

基于动态条件进行分页、排序、精确匹配、模糊匹配查询。适用于前端通用表格组件。

```json
{
  “table_name”: “sys_task_log”,
  “page”: 1,
  “size”: 15,
  “filters”: {“status”: “success”},
  “like_filters”: {“task_name”: “同步”},
  “sort_by”: “start_time”,
  “sort_order”: “desc”
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| table_name | string | ✅ | 目标表名 |
| page | int | ❌ | 页码，默认 `1` |
| size | int | ❌ | 每页条数，默认 `15` |
| filters | object | ❌ | 精确匹配条件：`{“列名”: 值}`，多组 AND 叠加 |
| like_filters | object | ❌ | 模糊匹配条件：`{“列名”: “关键字”}` → `WHERE 列名 LIKE '%关键字%'` |
| sort_by | string | ❌ | 排序字段名，不填则自动用主键降序 |
| sort_order | string | ❌ | `desc`（默认）/ `asc` |

**过滤规则：**
- `filters` 中的字段名必须在表中存在，取值为 `None` 或列不存在的条目会被静默跳过
- `like_filters` 同理，空字符串也会被跳过
- 多个 filter 之间是 **AND** 关系

**排序规则：**
- 传了 `sort_by` 且字段存在 → 按该字段排序
- 没传或字段不存在 → 自动取主键第一列降序排列

响应：

```json
{
  “code”: 1,
  “msg”: “查询成功”,
  “data”: {
    “total”: 128,
    “items”: [
      {
        “id”: “a1b2c3d4...”,
        “task_id”: “550e8400...”,
        “task_name”: “每日同步用户表”,
        “status”: “success”,
        “start_time”: “2026-06-15 02:00:00”,
        “end_time”: “2026-06-15 02:03:25”,
        “tables_synced”: 2,
        “total_records”: 15000,
        “error_msg”: null
      }
    ]
  }
}
```

---

### 典型使用场景

| 场景 | 接口组合 |
|------|----------|
| 浏览采集结果 | `/tables/list` → 选表 → `/tables/columns` 看结构 → `/tables/data` 查数据 |
| 前端通用数据表格 | `/tables/data` + `filters` + `like_filters` + `sort_by` 动态组合 |
| 调试采集任务 | 查 `sys_task_log` 或 `kafka_test_data` 等目标表确认数据已入库 |
| 快速搜索 | `/tables/list` 传 `keyword` 快速定位包含特定关键词的表 |



---

## 二十、音视频解析 `/media`

> ⚠️ **状态：代码已完成，尚未测试。** 依赖系统安装 `ffmpeg` 命令行工具 + Whisper 模型文件（`faster-whisper`）。

本模块提供独立的音视频转写能力，与 FTP 采集引擎中的自动转写共用同一套底层（`media_converter` + `WhisperASR`），但触发方式和输出不同：

| 维度 | API 手动转写 | FTP 自动转写 |
|------|-------------|-------------|
| **触发方式** | 前端手动上传文件 → `POST /media/transcribe` | FTP 采集任务 → `file_type=video/audio` → 引擎自动调用 `_transcribe_and_ingest` |
| **生效阶段** | 用户主动操作，即时 | 任务执行时，批量 |
| **输入** | `multipart/form-data` 文件上传 | FTP 下载到本地的媒体文件 |
| **输出** | 直接返回 JSON 文本 | 文本存入 PG 采集表（`raw_doc` JSON 列） |
| **清理** | 临时上传文件 + 临时 WAV 均删除 | 原始文件保留，仅删除临时 WAV |

### 1. 上传文件并获取转写文本

`POST /media/transcribe`

**请求：** `multipart/form-data`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| file | file(binary) | ✅ | — | 音视频文件，支持 mp4/mkv/avi/mov/flv/wmv/mp3/wav/m4a/aac/flac |
| language | string | ❌ | `"zh"` | 语言代码：`zh`(中文) / `en`(英文) / `ja`(日文) 等 |

**cURL 示例：**

```bash
curl -X POST http://localhost:8028/api/v1/media/transcribe \
  -F "file=@recording.mp3" \
  -F "language=zh"
```

**响应：**

```json
{
  "code": 1,
  "msg": "转写成功",
  "data": {
    "file_name": "recording.mp3",
    "file_type": "audio",
    "text": "今天下午三点召开项目评审会议请各部门负责人准时参加",
    "text_length": 25
  }
}
```

**错误响应（不支持的文件类型）：**

```json
{
  "code": 0,
  "msg": "不支持的文件类型 (.pdf)，支持: mp4/mkv/avi/mov/mp3/wav/m4a/aac/flac"
}
```

---

### 2. 内部处理流程

```
POST /media/transcribe
  │
  ├─ 1. 保存上传文件到临时目录 (NamedTemporaryFile)
  ├─ 2. 检测文件类型:
  │     ├─ is_video() → file_type = "video"
  │     ├─ is_audio() → file_type = "audio"
  │     └─ 其他       → 拒绝，删除临时文件
  │
  └─ 3. asyncio.to_thread(_sync_transcribe):    ← 不阻塞主事件循环
        ├─ ffmpeg 转 WAV (16kHz, mono, pcm_s16le)
        │   └─ 已 WAV 直接跳过转换
        ├─ Whisper 模型转写 (VAD 过滤 + 繁转简)
        ├─ 清理临时 WAV
        └─ 清理上传文件
        ↓
     返回 {file_name, file_type, text, text_length}
```

---

### 3. 环境依赖

| 依赖 | 用途 | 安装 |
|------|------|------|
| `ffmpeg` | 视频提取音轨 / 音频格式统一转 WAV | `apt install ffmpeg` 或下载二进制加入 PATH |
| `faster-whisper` | Whisper 语音识别模型 | `uv sync`（已在 pyproject.toml） |
| Whisper 模型文件 | 转写核心（large-v3 约 3GB） | 首次调用自动下载，或手动放到 `WHISPER_MODEL_PATH` |
| `opencc` | 繁体中文→简体中文 | `uv sync`（已在 pyproject.toml） |

**`.env` 可选配置：**

```env
WHISPER_MODEL_PATH=./large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

---

### 4. 与 FTP 采集的联动说明

FTP 采集任务配置了 `file_parse=1` 且采集到视频/音频文件时，引擎会在**后台自动**走同一套转写流程，结果存入 PG 目标表而非直接返回：

```json
// FTP 目标表 raw_doc 列的内容:
{
  "file_name": "meeting.mp4",
  "file_type": "video",
  "transcribed_text": "今天下午三点...",
  "text_length": 25,
  "transcribed_at": "2026-06-22T15:30:00"
}
```

> API 接口用于**即时预览测试**，FTP 引擎用于**批量自动采集**——两套触发方式，共享同一底层。

