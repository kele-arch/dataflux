# 前端接口对接文档

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
| type | string | ✅ | 类型：`mysql` / `postgresql` |
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
| db_type | string | ✅ | `mysql` / `postgresql` |
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

响应：

```json
{
  "code": 1,
  "msg": "任务执行完毕",
  "data": {
    "status": "success",
    "tables_synced": 2,
    "total_records": 15000,
    "new_watermark": "2026-06-05 12:00:00"
  }
}
```

---

### 7. 任务列表

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
        "sync_mode": "overwrite",
        "collect_mode": "inc_time",
        "incremental_column": "update_time",
        "last_watermark": "2026-06-05 12:00:00",
        "remark": "每天凌晨2点",
        "sync_tables": ["users", "orders"],
        "create_time": "2026-06-05T10:00:00",
        "update_time": "2026-06-05T10:00:00"
      }
    ]
  }
}
```

---

### 8. 任务详情

`POST /tsync/detail`

```json
{"task_id": "550e8400e29b41d4a716446655440000"}
```

响应同列表中单条 item 结构。

---

### 9. 仪表盘统计

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
| status | string | ❌ | 过滤：`running` / `success` / `failed` |
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

## 七、FTP 文件采集专项

> FTP 采集引擎支持文件下载、MD5 去重、结构化文件解析入库（CSV/JSON/YAML）。自动兼容明文 FTP 和加密 FTPS。

### 1. 创建 FTP 数据源

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
| type | string | ✅ | 固定 `"ftp"` |
| host | string | ✅ | FTP 服务器地址 |
| port | int | ✅ | FTP 端口，默认 `21` |
| db_name | string | ✅ | FTP 无数据库概念，随便填 `"/"` |
| username | string | ❌ | 用户名，不传则匿名登录 |
| password | string | ❌ | 密码 |

> 测试连接时自动兼容 FTPS（服务器要求加密时自动切换）。

---

### 2. 创建 FTP 采集任务

#### 方式 A：用 `ftp_url`（推荐，最简洁）

```json
{
  "task_name": "采集calico配置",
  "source_id": "你的FTP数据源ID",
  "ftp_url": "ftp://admin:123456@192.168.1.100:21/data/calico.yaml",
  "file_parse": 1,
  "collect_mode": "full"
}
```

#### 方式 B：用 `ftp_path`（连接信息从数据源读取）

```json
{
  "task_name": "采集calico配置",
  "source_id": "你的FTP数据源ID",
  "ftp_path": "/data/calico.yaml",
  "file_parse": 1,
  "collect_mode": "full"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_id | string | ✅ | FTP 数据源 ID |
| ftp_url | string | ❌ | 完整 FTP URL，传了自动解析 host/port/username/password/ftp_path |
| ftp_path | string | ❌ | 远程文件路径，如 `/data/calico.yaml`。与 `ftp_url` 二选一 |
| file_parse | int | ❌ | `1`=解析文件内容入库，`0`=只下载不解析，默认 `0` |
| file_type | string | ❌ | `auto`(自动识别) / `csv` / `json` / `yaml`，默认 `auto` |
| target_table | string | ❌ | 解析后写入哪张 PG 表，不传则自动用 `ftp_文件名` |
| ftp_passive | int | ❌ | `1`=被动模式（默认），`0`=主动模式 |
| collect_mode | string | ❌ | 固定 `"full"` |

> **注意：** `ftp_url` 和 `ftp_path` 至少传一个。都传时 `ftp_url` 优先。密码含 `@` 等特殊字符时需 URL 编码（如 `p@ss` → `p%40ss`）。

---

### 3. CSV 文件采集

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

### 4. JSON 文件采集

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

### 5. YAML 文件采集

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

### 6. 仅下载不解析

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

### 7. FTPS 加密连接

服务器要求加密时自动切换，无需额外配置。前端传参和普通 FTP 完全一样：

```json
{
  "task_name": "加密FTP采集",
  "source_id": "你的FTPS数据源ID",
  "ftp_url": "ftps://admin:123456@192.168.1.100:21/data/report.csv",
  "file_parse": 1,
  "file_type": "csv"
}
```

> 引擎自动检测：先尝试明文 FTP → 服务器返回 `503 Use AUTH first` → 自动切换 FTPS → 忽略自签证书 → 下载完成。

---

### 8. MD5 去重

同一文件重复执行任务时，如果 MD5 未变化，自动跳过：

```json
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

### 9. 文件记录表 `ftp_file_record`

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
| is_parsed | INTEGER | 0=未解析，1=已解析入库 |
| parsed_rows | INTEGER | 解析写入行数 |
| downloaded_at | TIMESTAMP | 下载时间 |

---

### 10.深度测试(已通过)

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



### FTP 采集流程

```
1. 查 ftp_file_record 表获取历史记录
2. 连接 FTP（自动检测 FTP/FTPS）
3. 下载文件到本地 {项目根}/ftp_files/{task_id}/
4. 计算 MD5
5. MD5 去重判断 → 相同则跳过
6. 保存文件记录到 ftp_file_record
7. 如果 file_parse=1：
   - CSV → 流式解析，每行存为 JSON
   - JSON → 解析数组/对象，每条存为 JSON
   - YAML → 解析多文档，每条存为 JSON
   - 写入目标表 (id UUID + raw_doc JSON)
8. 更新文件记录（is_parsed=1, parsed_rows=N）
```



---

## 八、API 接口采集专项

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



## 九、InfluxDB 监控查询接口 `/monitor`

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

