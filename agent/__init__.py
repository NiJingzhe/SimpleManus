from .BaseAgent import BaseAgent
from .AgentRegister import (
    AgentRegistry,
    get_agent_registry,
    register_agent,
    get_agent,
    list_available_models
)

from .SampleAgent import SampleAgent

__all__ = [
    'BaseAgent',
    'SampleAgent',
    'AgentRegistry',
    'get_agent_registry',
    'register_agent',
    'get_agent',
    'list_available_models',
]


# 注册Agent
register_agent("sampleagent", SampleAgent)
register_agent("simplemanus", SampleAgent)  # 为 Web 服务提供默认的 simplemanus 模型