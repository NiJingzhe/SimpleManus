"""
OpenAI API compatible data models
符合OpenAI API规范的数据模型定义
"""

from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class ChatMessage(BaseModel):
    """对话消息模型"""
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="消息角色")
    content: Optional[str] = Field(None, description="消息内容")
    name: Optional[str] = Field(None, description="发送者名称")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用")
    tool_call_id: Optional[str] = Field(None, description="工具调用ID")


class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""
    model: str = Field(..., description="模型名称")
    messages: List[ChatMessage] = Field(..., description="对话消息列表")
    temperature: Optional[float] = Field(1.0, ge=0, le=2, description="生成温度")
    top_p: Optional[float] = Field(1.0, ge=0, le=1, description="核采样参数")
    n: Optional[int] = Field(1, ge=1, le=128, description="生成数量")
    stream: Optional[bool] = Field(False, description="是否流式输出")
    stop: Optional[Union[str, List[str]]] = Field(None, description="停止词")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大Token数")
    presence_penalty: Optional[float] = Field(0, ge=-2, le=2, description="存在惩罚")
    frequency_penalty: Optional[float] = Field(0, ge=-2, le=2, description="频率惩罚")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="logit偏置")
    user: Optional[str] = Field(None, description="用户标识")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="可用工具")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="工具选择策略")


class Usage(BaseModel):
    """Token使用统计"""
    prompt_tokens: int = Field(..., description="提示词Token数")
    completion_tokens: int = Field(..., description="完成Token数")
    total_tokens: int = Field(..., description="总Token数")


class ChatChoice(BaseModel):
    """聊天选择结果"""
    index: int = Field(..., description="选择索引")
    message: ChatMessage = Field(..., description="生成的消息")
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = Field(
        None, description="结束原因"
    )


class ChatCompletionResponse(BaseModel):
    """聊天完成响应模型"""
    id: str = Field(..., description="请求ID")
    object: Literal["chat.completion"] = Field("chat.completion", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[ChatChoice] = Field(..., description="生成选择列表")
    usage: Usage = Field(..., description="Token使用统计")
    system_fingerprint: Optional[str] = Field(None, description="系统指纹")


class DeltaMessage(BaseModel):
    """流式输出的增量消息"""
    role: Optional[Literal["system", "user", "assistant", "tool"]] = Field(None, description="消息角色")
    content: Optional[str] = Field(None, description="消息内容")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用")


class ChatCompletionChunkChoice(BaseModel):
    """流式输出的选择块"""
    index: int = Field(..., description="选择索引")
    delta: DeltaMessage = Field(..., description="增量消息")
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = Field(
        None, description="结束原因"
    )


class ChatCompletionChunk(BaseModel):
    """流式输出的响应块"""
    id: str = Field(..., description="请求ID")
    object: Literal["chat.completion.chunk"] = Field("chat.completion.chunk", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[ChatCompletionChunkChoice] = Field(..., description="选择块列表")
    usage: Optional[Usage] = Field(None, description="Token使用统计")
    system_fingerprint: Optional[str] = Field(None, description="系统指纹")


class ModelInfo(BaseModel):
    """模型信息"""
    id: str = Field(..., description="模型ID")
    object: Literal["model"] = Field("model", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    owned_by: str = Field(..., description="拥有者")
    permission: Optional[List[Dict[str, Any]]] = Field(None, description="权限信息")
    root: Optional[str] = Field(None, description="根模型")
    parent: Optional[str] = Field(None, description="父模型")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    object: Literal["list"] = Field("list", description="对象类型")
    data: List[ModelInfo] = Field(..., description="模型列表")


class ErrorDetail(BaseModel):
    """错误详情"""
    message: str = Field(..., description="错误消息")
    type: str = Field(..., description="错误类型")
    param: Optional[str] = Field(None, description="错误参数")
    code: Optional[str] = Field(None, description="错误代码")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: ErrorDetail = Field(..., description="错误详情")


# 健康检查响应
class HealthResponse(BaseModel):
    """健康检查响应"""
    status: Literal["ok"] = Field("ok", description="服务状态")
    timestamp: str = Field(..., description="时间戳")
    version: str = Field(..., description="版本信息")
    agent_name: str = Field(..., description="智能体名称")


# 服务器信息响应
class ServerInfoResponse(BaseModel):
    """服务器信息响应"""
    name: str = Field(..., description="服务名称")
    version: str = Field(..., description="版本信息")
    description: str = Field(..., description="服务描述")
    api_version: str = Field(..., description="API版本")
    supported_models: List[str] = Field(..., description="支持的模型列表")
    capabilities: List[str] = Field(..., description="服务能力列表")
