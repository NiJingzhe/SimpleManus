"""
Web Interface Routers Package
包含所有API路由模块
"""

from .conversation_router import router as conversation_router
from .agent_router import router as agent_router
from .chat_router import router as chat_router
from .health_router import router as health_router

__all__ = [
    "conversation_router",
    "agent_router", 
    "chat_router",
    "health_router"
]
