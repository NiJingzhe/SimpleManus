"""
全局Agent单例管理器
确保在服务器和CLI中使用同一个Agent实例
"""

import asyncio
import threading
from typing import Optional
from agent.BaseAgent import BaseAgent
from config.config import get_config
from context.context import initialize_global_context
from tools import (
    execute_command,
    file_operations,
)


class GlobalAgentManager:
    """全局Agent单例管理器"""
    
    _instance: Optional['GlobalAgentManager'] = None
    _lock = threading.Lock()
    _agent: Optional[BaseAgent] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize_agent(
        self, 
        name: str = "SimpleAgent",
        description: str = "Professional CAD modeling assistant",
        context_file: str = "history/conversation_history.json",
        max_history_length: int = 20
    ) -> BaseAgent:
        """初始化全局Agent实例"""
        if self._initialized and self._agent is not None:
            return self._agent
            
        with self._lock:
            if self._initialized and self._agent is not None:
                return self._agent
                
            try:
                # 获取配置
                config = get_config()
                
                # 初始化全局context
                initialize_global_context(
                    llm_interface=config.BASIC_INTERFACE,
                    max_history_length=max_history_length,
                    save_to_file=True,
                    context_file=context_file
                )
                
                # 创建工具集
                toolkit = [
                    execute_command,
                    file_operations,
                ]
                
                # 创建Agent实例
                self._agent = BaseAgent(
                    name=name,
                    description=description,
                    toolkit=toolkit,
                    llm_interface=config.BASIC_INTERFACE,
                )
                
                self._initialized = True
                return self._agent
                
            except Exception as e:
                self._initialized = False
                self._agent = None
                raise RuntimeError(f"Failed to initialize global agent: {e}")
    
    def get_agent(self) -> Optional[BaseAgent]:
        """获取已初始化的Agent实例"""
        return self._agent
    
    def is_initialized(self) -> bool:
        """检查Agent是否已初始化"""
        return self._initialized and self._agent is not None
    
    def reset(self):
        """重置Agent实例（用于测试或重新初始化）"""
        with self._lock:
            self._agent = None
            self._initialized = False


# 全局管理器实例
_global_agent_manager = GlobalAgentManager()


def initialize_global_agent(
    name: str = "SimpleAgent",
    description: str = "Professional CAD modeling assistant", 
    context_file: str = "history/conversation_history.json",
    max_history_length: int = 20
) -> BaseAgent:
    """初始化全局Agent单例"""
    return _global_agent_manager.initialize_agent(
        name=name,
        description=description,
        context_file=context_file,
        max_history_length=max_history_length
    )


def get_global_agent() -> Optional[BaseAgent]:
    """获取全局Agent实例"""
    return _global_agent_manager.get_agent()


def is_agent_initialized() -> bool:
    """检查全局Agent是否已初始化"""
    return _global_agent_manager.is_initialized()


def reset_global_agent():
    """重置全局Agent实例"""
    _global_agent_manager.reset()
