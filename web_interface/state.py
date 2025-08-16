"""
服务器状态管理模块
"""
from typing import Optional, Any
from context.conversation_manager import ConversationManager, get_conversation_manager
from agent import get_agent_registry
from tools import (
    execute_command,
    read_or_search_file,
    write_file,
    sketch_pad_operations,
)


class ServerState:
    """服务器状态管理类，替代全局变量"""
    
    def __init__(self):
        self.agent_registry: Optional[Any] = None
        self.conversation_manager: Optional[ConversationManager] = None
    
    def initialize(self) -> None:
        """初始化服务器状态"""
        self.agent_registry = get_agent_registry()
        self.conversation_manager = get_conversation_manager()
        
        # 创建默认工具集
        toolkit = [
            execute_command,
            read_or_search_file,
            write_file,
            sketch_pad_operations,
        ]

        # 创建默认Agent实例
        self.agent_registry.get_or_create_agent(
            "simplemanus",
            name="SimpleManus Web Service",
            description="SimpleManus Web Service",
            toolkit=toolkit,
            max_history_length=4,  # DEFAULT_MAX_HISTORY_LENGTH
        )


# 全局服务器状态
server_state = ServerState()


def get_server_state() -> ServerState:
    """获取服务器状态依赖"""
    return server_state
