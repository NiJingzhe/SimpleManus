#!/usr/bin/env python3
"""
SimpleAgent Web Server Launcher
启动符合OpenAI API规范的Web服务器
"""

import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from web_interface.server import start_server
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保已安装所有依赖: uv sync 或 pip install -r requirements.txt")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="SimpleAgent Web API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s                          # 使用默认设置启动 (127.0.0.1:8000)
  %(prog)s --host 0.0.0.0 --port 8080  # 在所有网卡的8080端口启动
  %(prog)s --reload                 # 开发模式，文件修改后自动重载

API端点:
  GET  /                           # 服务器信息
  GET  /health                     # 健康检查
  GET  /v1/models                  # 列出可用模型
  POST /v1/chat/completions        # 聊天完成 (OpenAI兼容)
  GET  /docs                       # Swagger文档
  GET  /redoc                      # ReDoc文档

OpenAI客户端使用示例:
  curl -X POST "http://localhost:8000/v1/chat/completions" \\
    -H "Content-Type: application/json" \\
    -d '{
      "model": "simple-agent-v1",
      "messages": [{"role": "user", "content": "设计一个齿轮"}],
      "stream": false
    }'
        """
    )
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1",
        help="服务器主机地址 (默认: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="服务器端口号 (默认: 8000)"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true",
        help="启用开发模式 (文件修改后自动重载)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数量 (默认: 1)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Starting SimpleAgent Web API Server...")
    print(f"📍 Server: http://{args.host}:{args.port}")
    print(f"📖 Docs: http://{args.host}:{args.port}/docs")
    print(f"🔄 Reload: {'Enabled' if args.reload else 'Disabled'}")
    print("="*50)
    
    try:
        start_server(
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    except KeyboardInterrupt:
        print("\n👋 Server shutdown requested by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
