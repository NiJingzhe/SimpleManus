"""
通用工具函数和配置
"""

from config.config import get_config
import asyncio
import concurrent.futures

config = get_config()


def print_tool_output(title: str, content: str, style: str = "cyan"):
    """简化版工具输出函数，使用朴素print和分割线"""
    print("\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(f"{title}")
    print(content)
    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")


def safe_asyncio_run(coro_func, *args, **kwargs):
    """安全地运行异步函数的辅助函数，支持传入参数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro_func(*args, **kwargs))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro_func(*args, **kwargs))
    except RuntimeError:
        return asyncio.run(coro_func(*args, **kwargs))
