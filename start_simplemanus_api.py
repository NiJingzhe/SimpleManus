#!/usr/bin/env python3
"""
CADDesigner API 服务器启动脚本
重构版本 - 后端启动器
"""
import sys
import os
import argparse
import signal
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def validate_directory(path_str: str) -> Path:
    """验证并返回有效的目录路径"""
    path = Path(path_str).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"📁 创建工作目录: {path}")
        except Exception as e:
            raise argparse.ArgumentTypeError(f"无法创建目录 {path}: {e}")
    elif not path.is_dir():
        raise argparse.ArgumentTypeError(f"路径 {path} 不是一个目录")
    return path


def check_config():
    from SimpleLLMFunc.logger import app_log
    """检查配置文件"""
    config_file = project_root / "config" / "provider.json"
    template_file = project_root / "config" / "provider_template.json"
    
    if not config_file.exists():
        print("⚠️ 配置文件不存在")
        if template_file.exists():
            try:
                import shutil
                shutil.copy2(template_file, config_file)
                app_log("✅ 已从模板创建配置文件")
                print(f"📝 请编辑配置文件: {config_file}")
                print("💡 您可以稍后修改配置，现在继续启动服务...")
            except Exception as e:
                print(f"❌ 复制配置模板失败: {e}")
                return False
        else:
            print("❌ 配置模板文件不存在，请检查项目结构")
            return False
    else:
        app_log("✅ 配置文件检查通过")
    return True


def signal_handler(signum, frame):
    """信号处理器，优雅关闭"""
    print(f"\n🔄 收到信号 {signum}，正在关闭API服务器...")
    sys.exit(0)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="CADDesigner API 服务器启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认配置启动
  %(prog)s
  
  # 自定义主机和端口
  %(prog)s --host 0.0.0.0 --port 8001
  
  # 启用开发模式 (自动重载)
  %(prog)s --reload
  
  # 调整工作进程数量
  %(prog)s --workers 4
  
  # 在特定工作目录启动
  %(prog)s --working-dir /path/to/workspace
  
  # 生产环境配置示例
  %(prog)s --host 0.0.0.0 --port 8000 \\
           --workers 4 --log-level info \\
           --working-dir /var/lib/caddesigner

API端点:
  GET  /                           # 服务器信息
  GET  /health                     # 健康检查
  GET  /v1/models                  # 列出可用模型
  POST /v1/chat/completions        # 聊天完成 (OpenAI兼容)
  GET  /v1/conversations           # 会话管理
  GET  /docs                       # Swagger API文档
  GET  /redoc                      # ReDoc API文档
        """
    )
    
    # 服务器基本参数
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API服务器主机地址 (默认: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API服务器端口 (默认: 8000)"
    )
    
    parser.add_argument(
        "--working-dir",
        type=validate_directory,
        default=project_root,
        help="工作目录路径 (默认: 项目根目录)"
    )
    
    # 开发和调试参数
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用开发模式 (文件修改后自动重载)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="日志级别 (默认: info)"
    )
    
    parser.add_argument(
        "--access-log",
        action="store_true",
        default=True,
        help="启用访问日志 (默认: 启用)"
    )
    
    # 性能参数
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数量 (默认: 1, reload模式下强制为1)"
    )
    
    parser.add_argument(
        "--loop",
        choices=["auto", "asyncio", "uvloop"],
        default="auto",
        help="事件循环类型 (默认: auto)"
    )
    
    # 安全和限制参数
    parser.add_argument(
        "--limit-concurrency",
        type=int,
        help="最大并发连接数限制"
    )
    
    parser.add_argument(
        "--limit-max-requests",
        type=int,
        help="每个进程最大处理请求数"
    )
    
    # 调试参数
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    
    args = parser.parse_args()
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 切换到工作目录
    original_dir = os.getcwd()
    os.chdir(args.working_dir)
    
    try:
        import uvicorn
        from web_interface.server import app
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保已安装所有依赖: uv sync 或 pip install -r requirements.txt")
        sys.exit(1)


    try:
        print("🚀 启动CADDesigner API 服务器...")
        print("=" * 60)
        print(f"🌐 服务器地址: http://{args.host}:{args.port}")
        print(f"📖 API文档: http://{args.host}:{args.port}/docs")
        print(f"🔄 ReDoc文档: http://{args.host}:{args.port}/redoc")
        print(f"🏥 健康检查: http://{args.host}:{args.port}/health")
        print(f"📁 工作目录: {args.working_dir}")
        
        if args.reload:
            print("🔄 开发模式: 启用 (自动重载)")
        if args.workers > 1 and not args.reload:
            print(f"⚡ 工作进程: {args.workers}")
        if args.debug:
            print("🐛 调试模式: 启用")
        
        print("💡 按 Ctrl+C 停止服务")
        print("=" * 60)
        
        # 检查配置
        if not check_config():
            print("❌ 配置检查失败，请检查配置文件")
            sys.exit(1)
        
        # 准备uvicorn配置
        uvicorn_config = {
            "app": "web_interface.server:app",
            "host": args.host,
            "port": args.port,
            "reload": args.reload,
            "log_level": args.log_level,
            "access_log": args.access_log,
            "workers": 1 if args.reload else args.workers,  # reload模式下只能使用1个worker
            "loop": args.loop,
        }
        
        # 添加可选参数
        if args.limit_concurrency:
            uvicorn_config["limit_concurrency"] = args.limit_concurrency
        if args.limit_max_requests:
            uvicorn_config["limit_max_requests"] = args.limit_max_requests
        
        # 启动服务器
        uvicorn.run(**uvicorn_config)
        
    except KeyboardInterrupt:
        print("\n👋 API服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        # 恢复原始工作目录
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
