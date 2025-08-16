"""
Agent相关路由模块
"""

import time
from typing import Dict, Any
from fastapi import APIRouter, Depends

from ..models import ModelListResponse, ModelInfo
from ..state import get_server_state, ServerState
from agent import list_available_models

router = APIRouter(prefix="/v1", tags=["agents"])


@router.get(
    "/agents",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="列出所有活跃的Agent实例（用于调试和监控）",
)
async def list_agents(state: ServerState = Depends(get_server_state)):
    """列出所有活跃的Agent实例（用于调试和监控）"""
    if not state.agent_registry:
        return {"error": "Agent registry not initialized"}

    agents_info = {}
    for model_name in state.agent_registry.list_agents():
        agent_info = state.agent_registry.get_agent_info(model_name)
        if agent_info:
            # 添加实例ID用于验证单例
            agent = state.agent_registry.get_agent(model_name)
            agent_info["instance_id"] = id(agent) if agent else None
            agents_info[model_name] = agent_info

    return {
        "registry_stats": state.agent_registry.get_agent_stats(),
        "agents": agents_info,
    }


@router.get(
    "/models",
    response_model=ModelListResponse,
    dependencies=[Depends(get_server_state)],
    description="列出所有可用的模型（用于选择模型）",
)
async def list_models():
    """列出可用模型"""
    available_models = list_available_models()

    models = []
    for model_name in available_models:
        model_info = ModelInfo(
            id=model_name,
            object="model",
            created=int(time.time()),
            owned_by="simpleagent",
            permission=None,
            root=None,
            parent=None,
        )
        models.append(model_info)

    return ModelListResponse(object="list", data=models)
