"""
聊天路由模块
"""
import time
import json
from typing import AsyncGenerator, Any
from SimpleLLMFunc import push_error
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from ..models import (
    ChatCompletionRequest,
    Usage,
)
from context.conversation_manager import Conversation
from ..state import get_server_state, ServerState
from ..utils import (
    validate_chat_request,
    get_or_create_conversation,
    get_agent_for_model,
    process_agent_response,
    create_chat_response,
)
from ..error_handlers import create_error_response
from SimpleLLMFunc.logger import app_log, push_warning, log_context, get_current_context_attribute, get_location
from SimpleLLMFunc.base.post_process import extract_content_from_stream_response
from agent import BaseAgent

router = APIRouter(prefix="/v1/chat", tags=["chat"])


async def stream_chat_completion(
    request: ChatCompletionRequest,
    request_id: str,
    conversation: Conversation,
    agent: BaseAgent 
) -> AsyncGenerator[str, None]:
    """流式聊天完成生成器"""
    query, _ = validate_chat_request(request)

    app_log(f"🔍 Starting stream chat completion for conversation {conversation.uuid}, the query is {query}, agent is {agent.name}")

    created_time = int(time.time())

    # 流式处理智能体响应
    content_buffer = ""
    try:
        with conversation:
            async for chunk in agent.run(query):
                # 将 raw 包转发给客户端
                try:
                    if hasattr(chunk, "model_dump_json"):
                        json_str = chunk.model_dump_json()
                    elif hasattr(chunk, "model_dump"):
                        json_str = json.dumps(chunk.model_dump(), ensure_ascii=False)
                    elif hasattr(chunk, "dict"):
                        json_str = json.dumps(chunk.dict(), ensure_ascii=False)
                    else:
                        json_str = json.dumps(chunk, default=str, ensure_ascii=False)
                except Exception as encode_err:
                    push_warning(f"Failed to encode raw chunk: {encode_err}")
                    json_str = json.dumps({"error": str(encode_err)}, ensure_ascii=False)

                # 从 raw 包中提取文本，用于最终非流式汇总和持久化
                try:
                    content_delta = extract_content_from_stream_response(chunk, "agent_stream") or ""
                    if content_delta:
                        content_buffer += content_delta
                except Exception:
                    pass

                app_log(f"🔍 Forwarding raw chunk: {json_str}")
                yield f"data: {json_str}\n\n"
            
            # 流式对话完成后立即持久化conversation
            try:
                await conversation.context.persist()
                # 直接调用sketch_pad的persist方法
                conversation.sketch_pad.persist()
                app_log(f"✅ Auto-saved conversation {conversation.uuid} after stream completion")
            except Exception as save_error:
                # 保存失败不应该影响响应，但要记录日志
                push_warning(f"⚠️ Warning: Failed to save conversation {conversation.uuid}: {save_error}")

    except Exception as e:
        err_obj: dict[str, Any] = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": f"Error: {str(e)}"},
                    "finish_reason": "stop",
                }
            ],
        }
        err_json = json.dumps(err_obj, ensure_ascii=False)
        push_error(f"🔍 Sending error chunk: {err_json}", location=get_location())
        yield f"data: {err_json}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 结束信号
    yield "data: [DONE]\n\n"


@router.post(
    "/completions",
    dependencies=[Depends(get_server_state)],
    description="聊天完成端点（符合OpenAI规范）",
)
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
    state: ServerState = Depends(get_server_state),
):
    """聊天完成端点（符合OpenAI规范）"""
    if not state.agent_registry:
        return create_error_response(
            message="Agent registry not initialized",
            error_type="server_error",
            status_code=500,
        )
    
    if not state.conversation_manager:
        return create_error_response(
            message="Conversation manager not initialized", 
            error_type="server_error",
            status_code=500,
        )

    # 从自定义Header获取conversation ID
    conversation_id = http_request.headers.get("X-Conversation-ID")


    with log_context(conversation_id=conversation_id):
    
        try:
            # 获取或创建conversation
            conversation, conversation_id = get_or_create_conversation(
                conversation_id, state.conversation_manager
            )
            
            # 获取Agent
            agent = get_agent_for_model(request.model, state.agent_registry)
            
            # 验证请求并获取必要信息
            query, request_id = validate_chat_request(request)

            app_log(f"🔍 {request_id} request chat completion for conversation {conversation_id}")

            # 流式响应
            if request.stream:
                return StreamingResponse(
                    stream_chat_completion(request, request_id, conversation, agent),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                        "X-Conversation-ID": conversation_id,
                    },
                )

            # 非流式响应：返回文本 + token 统计
            full_response, prompt_tokens, completion_tokens = await process_agent_response(query, conversation, agent)
            response = create_chat_response(request_id, request.model, full_response, prompt_tokens, completion_tokens)
            
            return JSONResponse(
                content=response.model_dump(),
                headers={"X-Conversation-ID": conversation_id}
            )

        except HTTPException:
            # 重新抛出HTTPException，让FastAPI处理
            raise
        except Exception as e:
            return create_error_response(
                message=f"Internal server error: {str(e)}",
                error_type="server_error",
                status_code=500,
            )
