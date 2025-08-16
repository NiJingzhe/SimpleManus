"""
Conversation相关路由模块
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends

# 移除未使用的导入
from ..state import get_server_state, ServerState
from ..error_handlers import create_error_response
from config.config import get_config

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.get(
    "",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="列出所有可用的conversations",
)
async def list_conversations(state: ServerState = Depends(get_server_state)):
    """列出所有可用的conversations"""
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        conversations = state.conversation_manager.list_conversations()
        return {"conversations": conversations, "total_count": len(conversations)}
    except Exception as e:
        return create_error_response(
            message=f"Failed to list conversations: {str(e)}",
            error_type="server_error",
            status_code=500,
        )


@router.post(
    "",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="创建新的conversation",
)
async def create_conversation(
    state: ServerState = Depends(get_server_state),
):
    """创建新的conversation

    Args:
        llm_interface: LLM接口名称，如果为None则使用默认接口
        max_history_length: Context最大历史长度
    """
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        llm_obj = get_config().CONTEXT_SUMMARY_INTERFACE
        max_history_length = get_config().CONTEXT_MAX_HISTORY_LENGTH
        conversation = state.conversation_manager.create_conversation(
            llm_interface=llm_obj, max_history_length=max_history_length
        )

        return {
            "conversation_id": conversation.uuid,
            "created_at": conversation.created_at.isoformat(),
            "last_accessed": conversation.last_accessed.isoformat(),
        }
    except Exception as e:
        return create_error_response(
            message=f"Failed to create conversation: {str(e)}",
            error_type="server_error",
            status_code=500,
        )


@router.get(
    "/{conversation_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="获取指定conversation的信息",
)
async def get_conversation(
    conversation_id: str, state: ServerState = Depends(get_server_state)
):
    """获取指定conversation的信息"""
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        conversation = state.conversation_manager.get_conversation(conversation_id)
        if conversation is None:
            return create_error_response(
                message=f"Conversation {conversation_id} not found",
                error_type="not_found",
                status_code=404,
            )

        # 获取conversation统计信息
        with conversation:
            try:
                history_count = conversation.context.get_message_count()
                sketch_stats = conversation.sketch_pad.get_statistics()
                # 将SketchPadStatistics对象转换为字典
                sketch_stats_dict = sketch_stats.model_dump()
            except Exception as e:
                history_count = 0
                sketch_stats_dict = {}

        return {
            "conversation_id": conversation.uuid,
            "created_at": conversation.created_at.isoformat(),
            "last_accessed": conversation.last_accessed.isoformat(),
            "message_count": history_count,
            "sketch_stats": sketch_stats_dict,
        }
    except Exception as e:
        return create_error_response(
            message=f"Failed to get conversation: {str(e)}",
            error_type="server_error",
            status_code=500,
        )


@router.delete(
    "/{conversation_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="删除指定conversation",
)
async def delete_conversation(
    conversation_id: str, state: ServerState = Depends(get_server_state)
):
    """删除指定conversation"""
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        success = state.conversation_manager.delete_conversation(conversation_id)
        if not success:
            return create_error_response(
                message=f"Conversation {conversation_id} not found",
                error_type="not_found",
                status_code=404,
            )

        return {"deleted": True, "conversation_id": conversation_id}
    except Exception as e:
        return create_error_response(
            message=f"Failed to delete conversation: {str(e)}",
            error_type="server_error",
            status_code=500,
        )


@router.get(
    "/{conversation_id}/history",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="获取指定conversation的对话历史",
)
async def get_conversation_history(
    conversation_id: str,
    limit: Optional[int] = None,
    state: ServerState = Depends(get_server_state),
):
    """获取指定conversation的对话历史"""
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        conversation = state.conversation_manager.get_conversation(conversation_id)
        if conversation is None:
            return create_error_response(
                message=f"Conversation {conversation_id} not found",
                error_type="not_found",
                status_code=404,
            )

        # 获取对话历史
        with conversation:
            try:
                # 获取完整的对话历史
                history = [
                    message_item.model_dump()
                    for message_item in conversation.context.retrieve_messages()
                ]

                # 如果指定了限制，只返回最近的消息
                if limit and limit > 0:
                    history = history[-limit:]

                return {
                    "conversation_id": conversation_id,
                    "messages": history,
                    "total_messages": len(history),
                    "has_more": len(history) > len(history) if limit else False,
                }
            except Exception as e:
                return create_error_response(
                    message=f"Failed to access conversation history: {str(e)}",
                    error_type="server_error",
                    status_code=500,
                )
    except Exception as e:
        return create_error_response(
            message=f"Failed to get conversation history: {str(e)}",
            error_type="server_error",
            status_code=500,
        )


@router.get(
    "/{conversation_id}/sketchpad",
    response_model=Dict[str, Any],
    dependencies=[Depends(get_server_state)],
    description="获取指定conversation的SketchPad内容",
)
async def get_conversation_sketchpad(
    conversation_id: str, state: ServerState = Depends(get_server_state)
):
    """获取指定conversation的SketchPad内容"""
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized",
            error_type="server_error",
            status_code=500,
        )

    try:
        conversation = state.conversation_manager.get_conversation(conversation_id)
        if conversation is None:
            return create_error_response(
                message=f"Conversation {conversation_id} not found",
                error_type="not_found",
                status_code=404,
            )

        # 获取SketchPad内容
        with conversation:
            try:
                # 获取包含具体内容的sketch项目
                sketch_items = conversation.sketch_pad.list_items(include_value=True)
                sketch_stats = conversation.sketch_pad.get_statistics()

                return {
                    "conversation_id": conversation_id,
                    "sketch_items": sketch_items,
                    "statistics": sketch_stats,
                    "total_items": len(sketch_items),
                }
            except Exception as e:
                return create_error_response(
                    message=f"Failed to access SketchPad: {str(e)}",
                    error_type="server_error",
                    status_code=500,
                )
    except Exception as e:
        return create_error_response(
            message=f"Failed to get SketchPad: {str(e)}",
            error_type="server_error",
            status_code=500,
        )
