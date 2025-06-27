#!/bin/bash
# SimpleAgent Web Server 启动脚本
# Usage: ./start_server.sh [options]

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 显示帮助信息
show_help() {
    cat << EOF
SimpleAgent Web Server 启动脚本

用法:
    ./start_server.sh [选项]

选项:
    -h, --help          显示此帮助信息
    -p, --port PORT     指定端口号 (默认: 8000)
    -H, --host HOST     指定主机地址 (默认: 127.0.0.1)
    -r, --reload        启用开发模式 (文件修改后自动重载)
    -d, --debug         启用调试模式
    --public            在所有网卡上启动 (相当于 --host 0.0.0.0)

示例:
    ./start_server.sh                    # 默认启动
    ./start_server.sh -p 8080            # 在8080端口启动
    ./start_server.sh --public           # 在所有网卡启动
    ./start_server.sh -r                 # 开发模式启动

EOF
}

# 默认参数
HOST="127.0.0.1"
PORT="8000"
RELOAD=""
DEBUG=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        -r|--reload)
            RELOAD="--reload"
            shift
            ;;
        -d|--debug)
            DEBUG="--debug"
            shift
            ;;
        --public)
            HOST="0.0.0.0"
            shift
            ;;
        *)
            print_error "未知选项: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

echo "🚀 SimpleAgent Web Server 启动脚本"
echo "=================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    print_error "未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

print_success "Python 环境检查通过"

# 检查配置文件
if [ ! -f "config/provider.json" ]; then
    print_warning "配置文件不存在"
    print_info "正在复制配置模板..."
    
    if [ -f "config/provider_template.json" ]; then
        cp config/provider_template.json config/provider.json
        print_success "配置模板已复制"
        print_warning "请编辑 config/provider.json 填入您的API密钥"
        print_info "示例: nano config/provider.json"
        echo ""
        print_info "继续启动服务器 (您可以稍后修改配置)..."
    else
        print_error "配置模板文件不存在，请检查项目结构"
        exit 1
    fi
else
    print_success "配置文件检查通过"
fi

# 检查依赖
print_info "检查依赖包..."
if command -v uv &> /dev/null; then
    print_info "检测到 uv，使用 uv 管理依赖"
    # uv 会自动处理虚拟环境
elif [ -f "requirements.txt" ]; then
    print_info "使用 pip 检查依赖"
    # 这里可以添加 pip 依赖检查逻辑
fi

# 启动服务器
print_success "正在启动 SimpleAgent Web Server..."
echo "📍 地址: http://${HOST}:${PORT}"
echo "📖 API文档: http://${HOST}:${PORT}/docs"
echo "🔗 健康检查: http://${HOST}:${PORT}/health"
echo "💡 按 Ctrl+C 停止服务器"
echo "=================================="

# 构建启动命令
CMD="python3 start_web_server.py --host $HOST --port $PORT $RELOAD $DEBUG"

# 启动服务器
exec $CMD
