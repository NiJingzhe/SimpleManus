#!/bin/bash

# 等待MinIO服务启动
echo "等待MinIO服务启动..."
until curl -f http://localhost:9000/minio/health/live; do
    echo "MinIO还未就绪，等待5秒..."
    sleep 5
done

echo "MinIO服务已启动，开始初始化..."

# 安装MinIO客户端
if ! command -v mc &> /dev/null; then
    echo "安装MinIO客户端..."
    # 为macOS下载对应的客户端
    curl https://dl.min.io/client/mc/release/darwin-amd64/mc \
      --create-dirs \
      -o ./mc
    chmod +x ./mc
    MC_CMD="./mc"
else
    MC_CMD="mc"
fi

# 配置MinIO客户端
echo "配置MinIO客户端..."
$MC_CMD alias set local http://localhost:9000 ${MINIO_ACCESS_KEY:-simplemanus} ${MINIO_SECRET_KEY:-simplemanus_secure_minio_key_2024}

# 创建默认bucket
echo "创建默认bucket..."
$MC_CMD mb local/simplemanus-files --ignore-existing

# 设置bucket策略为public read
echo "设置bucket访问策略..."
$MC_CMD anonymous set public local/simplemanus-files

echo "MinIO初始化完成！"
echo "MinIO控制台访问地址: http://localhost:9001"
echo "用户名: ${MINIO_ACCESS_KEY:-simplemanus}"
echo "密码: ${MINIO_SECRET_KEY:-simplemanus_secure_minio_key_2024}"
