# 使用 Debian-slim 避免 C 库冲突，并极速构建依赖

FROM python:3.13-slim AS builder

# 注入官方 uv 工具 (Astral 官方推荐)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 安装编译所需的系统依赖 (针对 psycopg2 等 C 扩展)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 配置 uv 环境变量
# UV_COMPILE_BYTECODE: 预编译 .pyc 字节码，提升容器启动速度
# UV_LINK_MODE: Docker 构建中禁用硬链接，避免跨层复制出错
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 利用 Docker 缓存层，先安装依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim

WORKDIR /app

# 设置时区并安装运行时必需的动态库
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段无损复制编译好的虚拟环境
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 复制应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 创建持久化目录 (赋予足够权限防写报 Error)
RUN mkdir -p /app/ftp_files /app/data/oss_files \
    && chmod 777 /app/ftp_files /app/data/oss_files

EXPOSE 8028

# 启动服务 (推荐加上 Python 缓冲关闭,让日志即时输出)
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]