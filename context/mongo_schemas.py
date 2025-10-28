"""
MongoDB文档模型定义
基于MongoEngine实现的数据持久化模型，对应现有的Pydantic模型结构
"""

from mongoengine import (  # type: ignore
    Document, EmbeddedDocument, 
    StringField, DateTimeField, IntField, FloatField, 
    ListField, DictField, BooleanField, EmbeddedDocumentField,
    ObjectIdField, ReferenceField
)
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


class MessageDocument(EmbeddedDocument):
    """消息文档 - 对应schemas.Message"""
    
    role = StringField(required=True, choices=["system", "user", "assistant", "tool"])
    content = DictField()  # 存储序列化后的消息内容，支持字符串、列表、字典等所有类型
    name = StringField(max_length=64)
    tool_calls = ListField(DictField())  # 工具调用列表
    tool_call_id = StringField()
    timestamp = DateTimeField(default=datetime.now)
    
    meta = {
        'indexes': [
            'role',
            'timestamp',
            'tool_call_id'
        ]
    }


class ContextDocument(Document):
    """上下文文档 - 对应Context数据结构"""
    
    # 基础信息
    context_id = StringField(required=True, unique=True, primary_key=True)
    session_id = StringField()
    
    # 时间信息
    start_time = DateTimeField(default=datetime.now)
    last_activity = DateTimeField(default=datetime.now)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    # 消息历史
    messages = ListField(EmbeddedDocumentField(MessageDocument))
    
    # 摘要信息
    summary = StringField()
    
    # 元数据
    metadata = DictField(default=dict)
    total_messages = IntField(default=0)
    max_history_length = IntField(default=5)
    
    # 配置信息
    llm_interface_config = DictField()  # 存储LLM接口配置
    
    meta = {
        'collection': 'contexts',
        'indexes': [
            'context_id',
            'session_id', 
            'last_activity',
            'start_time',
            '-updated_at'  # 按更新时间倒序
        ],
        'ordering': ['-updated_at']
    }
    
    def save(self, *args, **kwargs):
        """保存时自动更新时间戳"""
        self.updated_at = datetime.now()
        if not self.created_at:
            self.created_at = datetime.now()
        return super().save(*args, **kwargs)


class SketchPadItemDocument(EmbeddedDocument):
    """SketchPad项目文档 - 对应schemas.SketchPadItem"""
    
    key = StringField(required=True)
    value = DictField()  # 使用DictField存储任意值
    timestamp = DateTimeField(default=datetime.now)
    summary = StringField()
    expires_at = DateTimeField()
    access_count = IntField(default=0)
    last_accessed = DateTimeField()
    tags = ListField(StringField())
    content_type = StringField(default="text")
    content_hash = StringField()
    
    meta = {
        'indexes': [
            'key',
            'tags',
            'content_type',
            'expires_at',
            'access_count'
        ]
    }


class SketchPadDocument(Document):
    """SketchPad文档 - 对应SketchPad数据结构"""
    
    # 基础信息
    sketch_pad_id = StringField(required=True, unique=True, primary_key=True)
    
    # 时间信息
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    # 存储项目
    items = ListField(EmbeddedDocumentField(SketchPadItemDocument))
    
    # 统计信息
    total_items = IntField(default=0)
    max_items = IntField(default=1000)
    total_accesses = IntField(default=0)
    
    # 元数据
    metadata = DictField(default=dict)
    
    meta = {
        'collection': 'sketch_pads',
        'indexes': [
            'sketch_pad_id',
            'updated_at',
            'total_items',
            'items.key',
            'items.tags',
            'items.content_type'
        ],
        'ordering': ['-updated_at']
    }
    
    def save(self, *args, **kwargs):
        """保存时自动更新时间戳和统计信息"""
        self.updated_at = datetime.now()
        if not self.created_at:
            self.created_at = datetime.now()
        self.total_items = len(self.items)
        self.total_accesses = sum(item.access_count for item in self.items)
        return super().save(*args, **kwargs)


class ConversationDocument(Document):
    """对话文档 - 对应Conversation数据结构"""
    
    # 基础信息
    conversation_id = StringField(required=True, unique=True, primary_key=True)
    
    # 关联的Context和SketchPad ID
    context_id = StringField(required=True)
    sketch_pad_id = StringField(required=True)
    
    # 时间信息
    created_at = DateTimeField(default=datetime.now)
    last_accessed = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    # 状态信息
    is_active = BooleanField(default=True)
    
    # 元数据
    metadata = DictField(default=dict)
    
    # 统计信息
    total_messages = IntField(default=0)
    total_sketch_items = IntField(default=0)
    
    meta = {
        'collection': 'conversations',
        'indexes': [
            'conversation_id',
            'context_id',
            'sketch_pad_id',
            'last_accessed',
            'is_active',
            '-updated_at'
        ],
        'ordering': ['-updated_at']
    }
    
    def save(self, *args, **kwargs):
        """保存时自动更新时间戳"""
        self.updated_at = datetime.now()
        if not self.created_at:
            self.created_at = datetime.now()
        return super().save(*args, **kwargs)


class ContextStatisticsDocument(Document):
    """上下文统计文档 - 用于系统监控和分析"""
    
    # 时间维度
    date = DateTimeField(required=True)
    hour = IntField()  # 0-23
    
    # 统计数据
    total_contexts = IntField(default=0)
    active_contexts = IntField(default=0)
    total_messages = IntField(default=0)
    total_conversations = IntField(default=0)
    total_sketch_items = IntField(default=0)
    
    # 性能数据
    avg_response_time = FloatField()
    cache_hit_rate = FloatField()
    
    meta = {
        'collection': 'context_statistics',
        'indexes': [
            'date',
            'hour',
            ('date', 'hour')  # 复合索引
        ],
        'ordering': ['-date', '-hour']
    }


class SystemLogDocument(Document):
    """系统日志文档 - 用于操作日志记录"""
    
    # 基础信息
    timestamp = DateTimeField(default=datetime.now)
    level = StringField(choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    operation = StringField(required=True)  # create, update, delete, query等
    
    # 关联信息
    context_id = StringField()
    conversation_id = StringField()
    sketch_pad_id = StringField()
    
    # 操作详情
    details = DictField()
    
    # 性能信息
    execution_time = FloatField()  # 毫秒
    
    # 错误信息
    error_message = StringField()
    stack_trace = StringField()
    
    meta = {
        'collection': 'system_logs',
        'indexes': [
            'timestamp',
            'level',
            'operation',
            'context_id',
            'conversation_id',
            'sketch_pad_id',
            ('timestamp', 'level'),
            ('operation', 'timestamp')
        ],
        'ordering': ['-timestamp']
    }


# ==================== 工具函数 ====================

def serialize_for_mongo(data: Any) -> Dict[str, Any]:
    """
    将Python对象序列化为MongoDB兼容的字典格式
    
    这个函数专门用于处理MessageContent，确保所有类型都能存储在DictField中
    
    Args:
        data: 要序列化的数据
        
    Returns:
        Dict[str, Any]: MongoDB兼容的字典格式数据
    """
    if data is None:
        return {"type": "null", "value": None}
    elif isinstance(data, str):
        return {"type": "string", "value": data}
    elif isinstance(data, list):
        # 处理多模态内容列表
        serialized_items = []
        for item in data:
            if hasattr(item, 'model_dump'):
                serialized_items.append(item.model_dump())
            elif isinstance(item, dict):
                serialized_items.append({k: serialize_content_value(v) for k, v in item.items()})
            else:
                serialized_items.append(serialize_content_value(item))
        return {"type": "list", "value": serialized_items}
    elif isinstance(data, dict):
        return {"type": "dict", "value": {k: serialize_content_value(v) for k, v in data.items()}}
    elif hasattr(data, 'model_dump'):
        # Pydantic模型
        return {"type": "pydantic", "value": data.model_dump()}
    else:
        # 其他类型转为字符串
        return {"type": "string", "value": str(data)}


def serialize_content_value(data: Any) -> Any:
    """辅助函数：序列化内容值"""
    if hasattr(data, 'model_dump'):
        return data.model_dump()
    elif isinstance(data, dict):
        return {k: serialize_content_value(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_content_value(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


def deserialize_from_mongo(data: Any) -> Any:
    """
    将MongoDB数据反序列化为Python对象
    
    Args:
        data: MongoDB返回的数据
        
    Returns:
        Any: Python兼容的数据
    """
    if isinstance(data, dict) and "type" in data and "value" in data:
        # 新的序列化格式
        data_type = data["type"]
        value = data["value"]
        
        if data_type == "null":
            return None
        elif data_type == "string":
            return value
        elif data_type == "list":
            return [deserialize_content_value(item) for item in value] if value else []
        elif data_type == "dict":
            return {k: deserialize_content_value(v) for k, v in value.items()} if value else {}
        elif data_type == "pydantic":
            return value  # 返回原始字典，让调用者处理
        else:
            return value
    elif isinstance(data, dict):
        # 旧格式或普通字典
        return {k: deserialize_from_mongo(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [deserialize_from_mongo(item) for item in data]
    else:
        return data


def deserialize_content_value(data: Any) -> Any:
    """辅助函数：反序列化内容值"""
    if isinstance(data, dict):
        return {k: deserialize_content_value(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [deserialize_content_value(item) for item in data]
    else:
        return data
