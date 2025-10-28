# SimpleAgent Docker 服务配置

本项目提供完整的后端服务栈，包括API服务、数据库、对象存储和日志系统。

## 服务概览

### 核心服务
- **simplemanus_api**: 主API服务 (外部端口: 8000)
- **simplemanus_redis**: Redis缓存服务 (内部端口: 9736, 不对外暴露)

### 数据库服务
- **simplemanus_postgres**: PostgreSQL关系型数据库 (内部端口: 5432, 调试端口: 5433)
  - 提供完整的CRUD操作支持
  - 用户认证和授权
  - 自动生成API端点

### 存储服务
- **simplemanus_minio**: MinIO对象存储 (内部端口: 9000, 控制台: 9001)
  - 高性能文件存储
  - 支持用户文件上传
  - S3兼容API
  - **注意**: API端口9000仅在内部网络可访问，控制台9001对外开放

### 日志服务
- **simplemanus_mongodb**: MongoDB文档数据库 (内部端口: 27017, 调试端口: 27018)
  - 结构化日志存储
  - 透明化后端操作
  - 便于检索和分析

## 快速启动

### 1. 环境配置
```bash
# 复制环境变量模板
cp env.example .env

# 重要：修改密码配置（必须设置以下密码）
vim .env
```

**必须配置的密码变量：**
- `POSTGRES_PASSWORD` - PostgreSQL数据库密码
- `MINIO_SECRET_KEY` - MinIO对象存储密钥
- `MONGODB_PASSWORD` - MongoDB数据库密码

**示例.env文件：**
```bash
# PostgreSQL数据库配置
POSTGRES_PASSWORD=your_secure_postgres_password

# MinIO对象存储配置  
MINIO_SECRET_KEY=your_secure_minio_secret_key

# MongoDB日志存储配置
MONGODB_PASSWORD=your_secure_mongodb_password
```

### 2. 启动所有服务
```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f
```

### 3. 初始化MinIO (可选)
```bash
# 运行MinIO初始化脚本
./init-minio.sh
```

## 服务访问信息

### 外部可访问服务

#### API服务
- **地址**: http://localhost:8000
- **健康检查**: http://localhost:8000/health

#### MinIO控制台 (管理界面)
- **控制台**: http://localhost:9001
- **用户名**: simplemanus (可通过 `MINIO_ACCESS_KEY` 配置)
- **密码**: 通过环境变量 `MINIO_SECRET_KEY` 配置

### 调试端口 (仅开发/调试使用)

#### PostgreSQL数据库
- **主机**: localhost
- **端口**: 5433 (映射到容器内部5432)
- **数据库**: simplemanus
- **用户名**: simplemanus
- **密码**: 通过环境变量 `POSTGRES_PASSWORD` 配置

#### MongoDB日志系统
- **主机**: localhost
- **端口**: 27018 (映射到容器内部27017)
- **数据库**: simplemanus_logs
- **用户名**: simplemanus (可通过 `MONGODB_USERNAME` 配置)
- **密码**: 通过环境变量 `MONGODB_PASSWORD` 配置

### 内部服务 (仅容器间访问)

#### Redis缓存
- **内部主机**: simplemanus_redis
- **内部端口**: 9736
- **数据库**: 0

#### MinIO API
- **内部地址**: http://simplemanus_minio:9000
- **默认bucket**: simplemanus-files

## 数据持久化

所有服务数据都通过Docker卷进行持久化存储：

- `simplemanus_postgres_data`: PostgreSQL数据
- `simplemanus_minio_data`: MinIO对象存储数据
- `simplemanus_mongodb_data`: MongoDB数据
- `simplemanus_mongodb_config`: MongoDB配置
- `simplemanus_redis_data`: Redis数据
- `app_data`: 应用数据
- `app_logs`: 应用日志
- `app_workspace`: 工作空间

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker-compose exec [service_name] sh

# 清理所有数据 (谨慎使用)
docker-compose down -v
```

## 开发建议

1. **数据库迁移**: 使用PostgreSQL进行结构化数据存储
2. **文件上传**: 通过MinIO API处理文件上传和存储
3. **日志记录**: 将操作日志写入MongoDB便于查询分析
4. **缓存策略**: 利用Redis提高数据访问性能

## 故障排除

### 服务启动失败
1. 检查端口是否被占用
2. 确认Docker和docker-compose版本
3. 查看服务日志定位问题

### 连接问题
1. 确认服务健康检查通过
2. 检查网络配置
3. 验证环境变量配置

### 数据问题
1. 检查数据卷挂载
2. 确认权限设置
3. 查看服务特定日志
