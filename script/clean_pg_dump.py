# -*- coding: utf-8 -*-
r"""pg_dump SQL 清洗脚本 —— 适配 Vastbase 导入

处理内容:
  1. 去掉 \restrict / \unrestrict 加密壳
  2. 去掉 PG 专有 SET 参数 (lock_timeout, row_security 等)
  3. 去掉 SELECT pg_catalog.set_config
  4. 去掉混合大小写列名的双引号 (适配 Vastbase 全小写列名)

用法:
  python script/clean_pg_dump.py <输入文件> [输出文件]
  python script/clean_pg_dump.py dataflux_vb.sql                       # 同名覆盖
  python script/clean_pg_dump.py dataflux_vb.sql dataflux_cleaned.sql   # 输出到新文件
"""

import re
import sys
from pathlib import Path

# 需要去掉双引号的混合大小写列名（Dataflux 无此问题，保留给其他项目使用）
QUOTED_COLUMNS = ["locationLR", "locationFB", "locationUD"]


def clean(sql: str) -> str:
    sql = re.sub(r'(?m)^\\restrict.*\r?\n', '', sql)
    sql = re.sub(r'(?m)^\\unrestrict.*\r?\n', '', sql)
    sql = re.sub(r'(?m)^SET .*\r?\n', '', sql)
    sql = re.sub(r'(?m)^SELECT pg_catalog\.set_config.*\r?\n', '', sql)
    for col in QUOTED_COLUMNS:
        sql = sql.replace(f'"{col}"', col)
    return sql


# ---- 命令行参数 ----
if len(sys.argv) < 2:
    print("用法: python script/clean_pg_dump.py <输入文件> [输出文件]")
    print("示例: python script/clean_pg_dump.py dataflux_vb.sql")
    sys.exit(1)

src_file = sys.argv[1]
dst_file = sys.argv[2] if len(sys.argv) > 2 else src_file

src = Path(src_file)
if not src.exists():
    print(f"文件不存在: {src}")
    sys.exit(1)

print(f"读取: {src}  ({src.stat().st_size:,} 字节)")
raw = src.read_text(encoding="utf-8")
cleaned = clean(raw)

# 统计残留
restrict = len(re.findall(r'\\restrict', cleaned))
set_lines = len(re.findall(r'(?m)^SET ', cleaned))
quoted = sum(1 for col in QUOTED_COLUMNS for _ in re.finditer(f'"{col}"', cleaned))

Path(dst_file).write_text(cleaned, encoding="utf-8")
print(f"写入: {dst_file}  ({len(cleaned):,} 字符)")
print(f"\\restrict: {restrict}  |  SET: {set_lines}  |  带引号列: {quoted}")
print("完成" if restrict == 0 and set_lines == 0 and quoted == 0 else "⚠️ 仍有残留")
