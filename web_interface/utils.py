"""
工具函数模块
"""
import time
import uuid
from typing import Tuple, Optional, Any, Union, Dict
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from .models import (
    ChatCompletionRequest,
    Usage,
    ChatCompletionResponse,
    ChatMessage,
    ChatChoice,
)
from context.conversation_manager import ConversationManager, Conversation
from tools import (
    execute_command,
    read_or_search_file,
    write_file,
    sketch_pad_operations,
)
from SimpleLLMFunc.logger import app_log, push_warning, push_error, get_current_context_attribute
from SimpleLLMFunc.llm_decorator.utils import extract_content_from_stream_response


def get_agent_for_model(model_name: str, agent_registry) -> Any:
    """
    根据模型名称获取Agent实例
    
    Args:
        model_name: 模型名称
        agent_registry: Agent注册器实例

    Returns:
        Agent实例

    Raises:
        HTTPException: 如果模型不存在或创建失败
    """
    if not agent_registry:
        raise HTTPException(status_code=500, detail="Agent registry not initialized")

    # 首先尝试获取已存在的Agent实例
    agent = agent_registry.get_agent(model_name)
    if agent:
        return agent

    # 如果不存在，尝试创建新的Agent实例
    try:
        agent = agent_registry.get_or_create_agent(
            model_name,
            name=f"Agent for {model_name}",
            description=f"Agent instance for model {model_name}",
            toolkit=[
                execute_command,
                read_or_search_file,
                write_file,
                sketch_pad_operations,
            ],
        )
        return agent
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error: {e} was caught. Maybe due to: [Unknown model: {model_name}]",
        )


# 移除create_error_response函数，因为它已经移到了error_handlers.py中


def validate_chat_request(request: ChatCompletionRequest) -> Tuple[str, str]:
    """
    验证聊天请求并提取用户消息
    
    Returns:
        (query, request_id)
    """
    if not request.messages:
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter: messages"
        )

    # 获取用户最后一条消息
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=400,
            detail="No user message found in conversation"
        )

    last_user_message = user_messages[-1]
    
    # 处理多模态消息内容
    query = ""
    if isinstance(last_user_message.content, str):
        # 纯文本消息
        query = last_user_message.content or ""
    elif isinstance(last_user_message.content, list):
        # 多模态消息 - 提取文本部分
        text_parts = []
        for item in last_user_message.content:
            # 处理字典格式或 Pydantic 模型格式
            if hasattr(item, 'type') and hasattr(item, 'text'):
                # Pydantic 模型格式
                if item.type == "text":
                    text_parts.append(item.text or "")
            elif isinstance(item, dict) and item.get("type") == "text":
                # 字典格式
                text_parts.append(item.get("text", ""))
        query = " ".join(text_parts)
    else:
        query = ""
    
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="User message content cannot be empty"
        )

    request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
    return query, request_id


def get_or_create_conversation(
    conversation_id: Optional[str],
    conversation_manager: ConversationManager
) -> Tuple[Conversation, str]:
    """
    获取或创建conversation

    如果conversation_id为None，则创建新的conversation
    如果conversation_id存在但对应的conversation不存在，则创建新的conversation
    否则返回现有的conversation

    Args:
        conversation_id: 可选的conversation ID
        conversation_manager: ConversationManager实例
    
    Returns:
        (conversation, conversation_id)
    """
    if not conversation_id:
        conversation = conversation_manager.create_conversation()
        conversation_id = conversation.uuid
    else:
        conversation = conversation_manager.get_conversation(conversation_id)   # type: ignore
        if conversation is None:
            # 如果conversation不存在，创建一个新的
            conversation = conversation_manager.create_conversation(conversation_id=conversation_id)
    
    return conversation, conversation_id


def _extract_tokens_from_chunk(chunk: Any) -> Tuple[Optional[int], Optional[int]]:
    """从多种可能的 chunk 结构中提取 token 统计。

    返回 (prompt_tokens, completion_tokens)。任意一个不存在则为 None。
    """
    # 1) Pydantic 模型：chunk.usage.prompt_tokens
    try:
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            pt = getattr(usage, "prompt_tokens", None)
            ct = getattr(usage, "completion_tokens", None)
            if isinstance(pt, int) or isinstance(ct, int):
                return (int(pt) if isinstance(pt, int) else None, int(ct) if isinstance(ct, int) else None)
    except Exception:
        pass

    # 2) 字典：{"usage": {"prompt_tokens": x, "completion_tokens": y}}
    try:
        if isinstance(chunk, dict):
            u = chunk.get("usage")
            if isinstance(u, dict):
                pt = u.get("prompt_tokens")
                ct = u.get("completion_tokens")
                pt_v = int(pt) if isinstance(pt, (int, float)) else None
                ct_v = int(ct) if isinstance(ct, (int, float)) else None
                if pt_v is not None or ct_v is not None:
                    return (pt_v, ct_v)
    except Exception:
        pass

    # 3) 扁平字典：{"prompt_tokens": x, "completion_tokens": y}
    try:
        if isinstance(chunk, dict):
            pt = chunk.get("prompt_tokens")
            ct = chunk.get("completion_tokens")
            pt_v = int(pt) if isinstance(pt, (int, float)) else None
            ct_v = int(ct) if isinstance(ct, (int, float)) else None
            if pt_v is not None or ct_v is not None:
                return (pt_v, ct_v)
    except Exception:
        pass

    return (None, None)


async def process_agent_response(
    query: str,
    conversation: Conversation,
    agent: Any
) -> Tuple[str, Optional[int], Optional[int]]:
    """处理Agent响应并返回 (完整文本, prompt_tokens, completion_tokens)。"""
    full_response: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    try:
        with conversation:
            async for chunk in agent.run(query):
                # 兼容 CADAgent.run 返回 raw 包的场景
                try:
                    delta: str = extract_content_from_stream_response(chunk, "agent_non_stream") or ""
                except Exception:
                    delta = ""
                if delta:
                    full_response += delta
                # 尝试从 chunk 中提取 token 统计（如果上游已提供）
                if prompt_tokens is None or completion_tokens is None:
                    pt, ct = _extract_tokens_from_chunk(chunk)
                    if pt is not None:
                        prompt_tokens = pt
                    if ct is not None:
                        completion_tokens = ct

            # 对话完成后立即持久化conversation
            try:
                await conversation.context.persist()
                # 直接调用sketch_pad的persist方法
                conversation.sketch_pad.persist()
                app_log(f"✅ Auto-saved conversation {conversation.uuid} after agent response")
            except Exception as save_error:
                # 保存失败不应该影响响应，但要记录日志
                push_warning(f"⚠️ Warning: Failed to save conversation {conversation.uuid}: {save_error}")

        return full_response.strip(), prompt_tokens, completion_tokens
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing error: {str(e)}"
        )


def create_chat_response(
    request_id: str,
    model: str,
    full_response: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
) -> ChatCompletionResponse:
    """创建聊天响应"""
    created_time = int(time.time())
    
    response_message = ChatMessage(
        role="assistant",
        content=full_response,
        name=None,
        tool_calls=None,
        tool_call_id=None,
    )

    choice = ChatChoice(index=0, message=response_message, finish_reason="stop")

    # 优先使用上游透传的 token 统计；否则回退上下文统计；最后置 0
    if prompt_tokens is None:
        _in = get_current_context_attribute("input_tokens")
        try:
            prompt_tokens = int(_in) if _in is not None else 0
        except Exception:
            prompt_tokens = 0
    if completion_tokens is None:
        _out = get_current_context_attribute("output_tokens")
        try:
            completion_tokens = int(_out) if _out is not None else 0
        except Exception:
            completion_tokens = 0

    usage = Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=(prompt_tokens or 0) + (completion_tokens or 0),
    )

    return ChatCompletionResponse(
        id=request_id,
        object="chat.completion",
        created=created_time,
        model=model,
        choices=[choice],
        usage=usage,
        system_fingerprint=None,
    )
