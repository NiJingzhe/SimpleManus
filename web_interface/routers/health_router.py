"""
健康检查路由模块
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from typing import Dict, Any

from ..models import HealthResponse, ServerInfoResponse
from ..state import get_server_state, ServerState

router = APIRouter()


@router.get("/", response_model=ServerInfoResponse)
async def root():
    """服务器根路径信息"""
    return ServerInfoResponse(
        name="SimpleAgent API Server",
        version="1.0.0",
        description="OpenAI-compatible API for SimpleAgent universal framework",
        api_version="v1",
        supported_models=["simple-agent-v1"],
        capabilities=[
            "chat.completions",
            "streaming",
            "tool_calling",
            "conversation_history",
            "sketch_pad_storage",
        ],
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(state: ServerState = Depends(get_server_state)):
    """健康检查端点"""
    default_agent = (
        state.agent_registry.get_agent("simple-agent-v1") if state.agent_registry else None
    )

    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        agent_name=default_agent.name if default_agent else "Not initialized",
    )
