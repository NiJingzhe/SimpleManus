"""
通用工具函数和配置
"""
from SimpleLLMFunc import llm_function, tool
from typing import List, Optional
from config.config import get_config
import os
import subprocess
import time
import json
import asyncio
import concurrent.futures
from rich.table import Table
from context.context import ensure_global_context, get_global_context
from context.sketch_pad import get_global_sketch_pad

config = get_config()

global_context = ensure_global_context(
        llm_interface=config.BASIC_INTERFACE,
        max_history_length=20,
        save_to_file=True,
        context_file="context/conversation_history.json"
)

def print_tool_output(title: str, content: str, style: str = "cyan"):
    """简化版工具输出函数，使用朴素print和分割线"""
    print("\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(f"{title}")
    print(content)
    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")


def safe_asyncio_run(coro_func):
    """安全地运行异步函数的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro_func())
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro_func())
    except RuntimeError:
        return asyncio.run(coro_func())
