# 使用Python 3.12作为基础镜像（满足 requires-python >=3.12）
# 说明：强制使用 amd64 架构以获得 `cadquery-ocp` 可用 wheel（Linux aarch64 无可用官方 wheel）
FROM --platform=linux/amd64 python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ARG APP_DEFAULT_MODE=api
ENV APP_DEFAULT_MODE=${APP_DEFAULT_MODE}

RUN set -e; . /etc/os-release; \
  codename="${VERSION_CODENAME}"; \
  printf 'deb https://mirrors.ustc.edu.cn/debian/ %s main contrib non-free non-free-firmware\n' "$codename" > /etc/apt/sources.list; \
  printf 'deb https://mirrors.ustc.edu.cn/debian/ %s-updates main contrib non-free non-free-firmware\n' "$codename" >> /etc/apt/sources.list; \
  printf 'deb https://mirrors.ustc.edu.cn/debian-security %s-security main contrib non-free non-free-firmware\n' "$codename" >> /etc/apt/sources.list; \
  printf 'deb https://mirrors.ustc.edu.cn/debian/ %s-backports main contrib non-free non-free-firmware\n' "$codename" >> /etc/apt/sources.list

# 安装系统依赖（包含 OpenGL 运行时以修复 libGL.so.1）
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    # OpenGL/GLX/EGL 运行时（VTK/Qt/pyvista 常见依赖）
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglu1-mesa \
    libglx-mesa0 \
    libegl1 \
    # 头less渲染（Xvfb）
    xvfb \
    xauth \
    libx11-6 \
    libxkbcommon0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（通过 PyPI 安装二进制发行包）
RUN export PIP_INDEX_URL="https://mirrors.ustc.edu.cn/pypi/web/simple"
RUN pip install --no-cache-dir uv

# 仅复制锁文件与项目描述以最大化缓存
COPY pyproject.toml uv.lock ./

# 使用 uv 基于锁文件同步依赖（生成 /app/.venv）
RUN export UV_INDEX_URL="https://mirrors.ustc.edu.cn/pypi/web/simple"
RUN uv sync --frozen --no-dev

# 确保使用项目虚拟环境中的 Python/可执行文件
ENV PATH="/app/.venv/bin:${PATH}"
ENV DISPLAY=:99
ENV PYVISTA_OFF_SCREEN=true
ENV PYVISTA_USE_PANEL=false
ENV QT_QPA_PLATFORM=offscreen
ENV MPLBACKEND=Agg
ENV LIBGL_ALWAYS_SOFTWARE=1

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/workspace /app/workspace/sandbox

# 设置权限
RUN chmod +x /app/start_simplemanus_api.py

# 复制并设置入口脚本
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 暴露端口
EXPOSE 8000 

# 入口脚本
ENTRYPOINT ["/app/entrypoint.sh"]