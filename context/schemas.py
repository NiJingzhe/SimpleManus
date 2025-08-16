from typing import Literal, List, Optional, Union, Any, Dict, Set
from pydantic import BaseModel, Field, model_validator, field_validator, RootModel
from datetime import datetime
import hashlib


class TextContent(BaseModel):
    type: Literal["text"] = Field(..., description="内容块类型：纯文本")
    text: str = Field(..., description="消息的文本内容")


class ImageURL(BaseModel):
    url: str = Field(..., description="图片的公开访问URL")
    detail: Optional[Literal["auto", "low", "high"]] = Field(
        None,
        description="图片的可选细节级别"
    )


class ImageContent(BaseModel):
    type: Literal["image_url"] = Field(..., description="内容块类型：图片URL")
    image_url: ImageURL = Field(..., description="图片内容的详细信息")


MessageContent = Union[
    str,
    None,
    List[Union[TextContent, ImageContent]]
]


class FunctionCall(BaseModel):
    name: str = Field(..., description="要调用的函数名称")
    arguments: str = Field(..., description="要传递的参数的JSON格式字符串")


class ToolCall(BaseModel):
    id: str = Field(..., description="此工具调用的唯一ID")
    type: Literal["function"] = Field(..., description="被调用工具的类型（函数）")
    function: FunctionCall = Field(..., description="函数调用规范")


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ...,
        description="消息发送者的角色"
    )
    content: MessageContent = Field(
        ...,
        description=(
            "消息内容。"
            "可以是字符串、null（调用工具时）或结构化多模态块的列表。"
        )
    )
    name: Optional[str] = Field(
        default=None,
        description="可选的发送者名称，当角色为'user'或'tool'时必需",
        max_length=64,
        pattern=r"^[a-zA-Z0-9_]*$"
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None,
        description="助手想要调用的工具调用列表"
    )
    tool_call_id: Optional[str] = Field(
        default=None,
        description="此工具消息响应的工具调用ID"
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="消息时间戳（ISO格式）"
    )

    @model_validator(mode="after")
    def validate_tool_message_consistency(cls, values):
        role = values.role
        content = values.content
        tool_calls = values.tool_calls
        tool_call_id = values.tool_call_id

        if role == "assistant" and tool_calls and content is not None:
            raise ValueError("When role is 'assistant' and tool_calls exist, content must be None.")
        if role == "tool" and not tool_call_id:
            raise ValueError("When role is 'tool', tool_call_id must be provided.")
        return values


class ChatMessages(RootModel[List[Message]]):
    """按时间顺序排列的聊天消息列表"""


class SketchPadItem(BaseModel):
    """SketchPad 存储项的数据结构"""
    
    value: Any = Field(..., description="存储的值")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间")
    summary: Optional[str] = Field(default=None, description="内容摘要")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")
    access_count: int = Field(default=0, description="访问次数")
    last_accessed: Optional[datetime] = Field(default=None, description="最后访问时间")
    tags: Set[str] = Field(default_factory=set, description="标签集合")
    content_type: str = Field(default="text", description="内容类型")
    content_hash: Optional[str] = Field(default=None, description="内容哈希值")

    @field_validator('last_accessed', mode='before')
    @classmethod
    def set_last_accessed(cls, v):
        """如果 last_accessed 为 None，则设置为当前时间"""
        if v is None:
            return datetime.now()
        return v

    @field_validator('content_hash', mode='before')
    @classmethod
    def set_content_hash(cls, v, info):
        """如果 content_hash 为 None，则计算哈希值"""
        if v is None:
            value = info.data.get('value')
            if value is not None:
                content_str = str(value)
                return hashlib.md5(content_str.encode()).hexdigest()[:8]
        return v

    def is_expired(self) -> bool:
        """检查是否过期"""
        return self.expires_at is not None and datetime.now() > self.expires_at

    def update_access(self):
        """更新访问信息（用于LRU缓存）"""
        self.access_count += 1
        self.last_accessed = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "tags": list(self.tags),
            "content_type": self.content_type,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SketchPadItem":
        """从字典创建实例"""
        # 处理时间字段
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("expires_at") and isinstance(data["expires_at"], str):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if data.get("last_accessed") and isinstance(data["last_accessed"], str):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])

        # 处理tags
        if data.get("tags") and isinstance(data["tags"], list):
            data["tags"] = set(data["tags"])

        return cls(**data)


class SketchPadStatistics(BaseModel):
    """SketchPad 统计信息"""
    
    total_items: int = Field(..., description="总项目数")
    max_items: int = Field(..., description="最大项目数")
    items_with_summary: int = Field(..., description="有摘要的项目数")
    total_accesses: int = Field(..., description="总访问次数")
    popular_tags: Dict[str, int] = Field(..., description="热门标签统计")
    content_types: Dict[str, int] = Field(..., description="内容类型统计")
    avg_access_per_item: float = Field(..., description="平均每项访问次数")
    memory_usage_percent: float = Field(..., description="内存使用百分比")


class SketchPadSearchResult(BaseModel):
    """SketchPad 搜索结果"""
    
    key: str = Field(..., description="项目键名")
    value: Any = Field(..., description="项目值")
    summary: Optional[str] = Field(default=None, description="项目摘要")
    timestamp: str = Field(..., description="创建时间（ISO格式）")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    content_type: str = Field(..., description="内容类型")
    access_count: int = Field(..., description="访问次数")


class SketchPadListItem(BaseModel):
    """SketchPad 列表项"""
    
    key: str = Field(..., description="项目键名")
    summary: Optional[str] = Field(default=None, description="项目摘要")
    timestamp: str = Field(..., description="创建时间（ISO格式）")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    content_type: str = Field(..., description="内容类型")
    access_count: int = Field(..., description="访问次数")
    content_hash: Optional[str] = Field(default=None, description="内容哈希值")
    value: Optional[Any] = Field(default=None, description="项目值（仅在包含内容时）")
