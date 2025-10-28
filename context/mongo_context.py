"""
基于MongoDB持久化和Redis缓存的Context后端实现
"""

import json
import threading
from typing import Dict, List, Optional, Any, override, cast
from datetime import datetime
from SimpleLLMFunc import async_llm_function, OpenAICompatible
import redis
from mongoengine.errors import DoesNotExist, ValidationError  # type: ignore

from context.schemas import Message, ChatMessages
from context.context import ContextBackend
from context.mongo_schemas import ContextDocument, MessageDocument, serialize_for_mongo, deserialize_from_mongo
from context.mongo_connection import ensure_mongo_connection
from SimpleLLMFunc.logger import push_warning, push_error, app_log


class RedisMongoContextBackend(ContextBackend):
    """
    基于Redis缓存和MongoDB持久化的上下文后端实现
    
    特点：
    1. Redis提供高性能的即时访问和缓存
    2. MongoDB提供可靠的持久化存储和复杂查询能力
    3. 支持自动同步和故障恢复
    4. 提供丰富的查询和分析功能
    """

    @override
    def __init__(
        self,
        context_id: str,
        llm_interface: Optional[OpenAICompatible] = None,
        max_history_length: int = 5,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        file_path: Optional[str] = None,  # 保持兼容性，但不使用
    ):
        """
        初始化Redis MongoDB后端

        Args:
            context_id: 上下文唯一标识符
            llm_interface: LLM接口，用于历史总结
            max_history_length: 最大历史记录长度
            redis_host: Redis主机地址
            redis_port: Redis端口
            redis_db: Redis数据库编号
            file_path: 文件路径（保持兼容性，实际不使用）
        """
        self.context_id = context_id
        self.llm_interface = llm_interface
        self.max_history_length = max_history_length
        
        # Redis连接
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            password=redis_password
        )
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 确保MongoDB连接
        if not ensure_mongo_connection():
            push_error("无法连接到MongoDB")
            raise ConnectionError("MongoDB connection failed")
        
        # 初始化历史总结函数
        self._summarize_func = None
        if self.llm_interface:
            self._summarize_func = async_llm_function(
                llm_interface=self.llm_interface,
                toolkit=[],
                timeout=600,
            )(cast(Any, self._summarize_history_impl))
        
        # 初始化或加载上下文
        self._init_context()

    def _init_context(self) -> None:
        """初始化或加载上下文"""
        try:
            # 尝试从MongoDB加载现有上下文
            context_doc = ContextDocument.objects(context_id=self.context_id).first()
            
            if context_doc:
                app_log(f"从MongoDB加载现有上下文: {self.context_id}")
                # 同步到Redis缓存
                self._sync_from_mongo_to_redis(context_doc)
            else:
                app_log(f"创建新的上下文: {self.context_id}")
                # 创建新的上下文文档
                context_doc = ContextDocument(
                    context_id=self.context_id,
                    session_id=self._generate_session_id(),
                    start_time=datetime.now(),
                    last_activity=datetime.now(),
                    max_history_length=self.max_history_length,
                    metadata={
                        "context_id": self.context_id,
                        "session_id": self._generate_session_id(),
                        "start_time": datetime.now().isoformat(),
                        "last_activity": datetime.now().isoformat(),
                        "total_messages": 0,
                        "max_history_length": self.max_history_length,
                    }
                )
                context_doc.save()
                
        except Exception as e:
            push_error(f"初始化上下文失败: {e}")
            raise

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _get_redis_key(self, key: str) -> str:
        """获取Redis键名"""
        return f"context:{self.context_id}:{key}"

    def _sync_from_mongo_to_redis(self, context_doc: ContextDocument) -> None:
        """从MongoDB同步数据到Redis缓存"""
        try:
            with self._lock:
                # 同步消息
                messages_key = self._get_redis_key("messages")
                self.redis_client.delete(messages_key)
                
                for msg_doc in context_doc.messages:
                    # 处理content类型转换
                    content = None
                    if msg_doc.content:
                        deserialized_content = deserialize_from_mongo(msg_doc.content)
                        if isinstance(deserialized_content, (str, list)):
                            content = deserialized_content
                        elif isinstance(deserialized_content, dict):
                            # 如果是字典，尝试提取text字段或转换为字符串
                            content = deserialized_content.get('text', str(deserialized_content))
                        else:
                            content = str(deserialized_content)
                    
                    # 修正数据一致性：当role是assistant且有tool_calls时，content必须为None
                    final_content = content
                    if msg_doc.role == "assistant" and msg_doc.tool_calls and content is not None:
                        final_content = None
                    
                    message = Message(
                        role=msg_doc.role,
                        content=final_content,
                        name=msg_doc.name,
                        tool_calls=msg_doc.tool_calls,
                        tool_call_id=msg_doc.tool_call_id,
                        timestamp=msg_doc.timestamp.isoformat() if msg_doc.timestamp else None
                    )
                    self.redis_client.lpush(messages_key, message.model_dump_json())
                
                # 同步摘要
                if context_doc.summary:
                    summary_key = self._get_redis_key("summary")
                    self.redis_client.set(summary_key, context_doc.summary)
                
                # 同步元数据
                metadata_key = self._get_redis_key("metadata")
                self.redis_client.set(metadata_key, json.dumps(context_doc.metadata))
                
        except Exception as e:
            push_warning(f"从MongoDB同步到Redis失败: {e}")

    def _sync_from_redis_to_mongo(self) -> bool:
        """从Redis同步数据到MongoDB"""
        try:
            with self._lock:
                # 获取或创建上下文文档
                context_doc = ContextDocument.objects(context_id=self.context_id).first()
                if not context_doc:
                    context_doc = ContextDocument(context_id=self.context_id)
                
                # 同步消息
                messages_key = self._get_redis_key("messages")
                message_data_list = self.redis_client.lrange(messages_key, 0, -1)
                
                context_doc.messages = []
                # 确保message_data_list是列表类型
                data_list = message_data_list if isinstance(message_data_list, list) else []
                for message_data in reversed(data_list):  # Redis是LIFO，需要反转
                    try:
                        message_dict = json.loads(str(message_data))
                        msg_doc = MessageDocument(
                            role=message_dict.get('role'),
                            content=serialize_for_mongo(message_dict.get('content')),
                            name=message_dict.get('name'),
                            tool_calls=message_dict.get('tool_calls', []),
                            tool_call_id=message_dict.get('tool_call_id'),
                            timestamp=datetime.fromisoformat(message_dict['timestamp']) if message_dict.get('timestamp') else datetime.now()
                        )
                        context_doc.messages.append(msg_doc)
                    except Exception as e:
                        push_warning(f"同步消息失败: {e}")
                
                # 同步摘要
                summary_key = self._get_redis_key("summary")
                summary = self.redis_client.get(summary_key)
                if summary:
                    context_doc.summary = summary
                
                # 同步元数据
                metadata_key = self._get_redis_key("metadata")
                metadata_str = self.redis_client.get(metadata_key)
                if metadata_str:
                    try:
                        context_doc.metadata = json.loads(str(metadata_str))
                    except:
                        pass
                
                # 更新统计信息
                context_doc.total_messages = len(context_doc.messages)
                context_doc.last_activity = datetime.now()
                
                # 保存到MongoDB
                context_doc.save()
                return True
                
        except Exception as e:
            push_error(f"从Redis同步到MongoDB失败: {e}")
            return False

    @override
    async def store_message(self, message: Message) -> None:
        """存储一条消息"""
        with self._lock:
            # 确保消息有时间戳
            if message.timestamp is None:
                message.timestamp = datetime.now().isoformat()
            
            # 存储到Redis
            messages_key = self._get_redis_key("messages")
            message_data = message.model_dump_json()
            self.redis_client.lpush(messages_key, message_data)
            
            # 自动内存管理
            await self._auto_memory_manage()

            # 限制历史长度
            self.redis_client.ltrim(messages_key, 0, self.max_history_length - 1)
            
            # 更新元数据
            metadata_key = self._get_redis_key("metadata")
            metadata_str = self.redis_client.get(metadata_key)
            metadata = json.loads(str(metadata_str)) if metadata_str else {}
            
            current_total = metadata.get("total_messages", 0)
            metadata["total_messages"] = int(current_total) + 1
            metadata["last_activity"] = datetime.now().isoformat()
            
            self.redis_client.set(metadata_key, json.dumps(metadata))
            
            # 异步同步到MongoDB
            self._sync_from_redis_to_mongo()

    @override
    def retrieve_messages(self, limit: Optional[int] = None) -> List[Message]:
        """获取消息历史"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            message_data_list = self.redis_client.lrange(messages_key, 0, -1)
            
            messages = []
            # 确保 message_data_list 是一个列表
            data_list = message_data_list if isinstance(message_data_list, list) else []
            for message_data in data_list:
                try:
                    message_dict = json.loads(str(message_data))
                    message = Message(**message_dict)
                    messages.append(message)
                except Exception as e:
                    push_warning(f"反序列化消息失败: {e}")
            
            # 按时间排序（最新的在前）
            messages.reverse()
            
            if limit is not None:
                messages = messages[-limit:]
            
            return messages

    @override
    def update_summary(self, summary: str) -> None:
        """更新对话摘要"""
        with self._lock:
            summary_key = self._get_redis_key("summary")
            self.redis_client.set(summary_key, summary)

    @override
    def get_summary(self) -> Optional[str]:
        """获取对话摘要"""
        with self._lock:
            summary_key = self._get_redis_key("summary")
            result = self.redis_client.get(summary_key)
            return str(result) if result is not None else None

    @override
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新元数据"""
        with self._lock:
            metadata_key = self._get_redis_key("metadata")
            current_metadata_str = self.redis_client.get(metadata_key)
            current_metadata = json.loads(str(current_metadata_str)) if current_metadata_str else {}
            
            current_metadata.update(metadata)
            self.redis_client.set(metadata_key, json.dumps(current_metadata))

    @override
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        with self._lock:
            metadata_key = self._get_redis_key("metadata")
            metadata_str = self.redis_client.get(metadata_key)
            return json.loads(str(metadata_str)) if metadata_str else {}

    @override
    def search_messages(self, query: str, limit: int = 5) -> List[Message]:
        """搜索消息"""
        # 先尝试从Redis缓存搜索
        messages = self.retrieve_messages()
        results = []
        query_lower = query.lower()

        for message in reversed(messages):
            content = message.content
            if isinstance(content, str) and query_lower in content.lower():
                results.append(message)
                if len(results) >= limit:
                    break

        # 如果Redis结果不足，从MongoDB搜索更多历史数据
        if len(results) < limit:
            try:
                context_doc = ContextDocument.objects(context_id=self.context_id).first()
                if context_doc:
                    for msg_doc in context_doc.messages:
                        if len(results) >= limit:
                            break
                        
                        content = msg_doc.content
                        if isinstance(content, dict) and isinstance(content.get('text'), str):
                            content_text = content['text']
                        elif isinstance(content, str):
                            content_text = content
                        else:
                            continue
                            
                        if query_lower in content_text.lower():
                            # 处理content类型转换
                            content = None
                            if msg_doc.content:
                                deserialized_content = deserialize_from_mongo(msg_doc.content)
                                if isinstance(deserialized_content, (str, list)):
                                    content = deserialized_content
                                elif isinstance(deserialized_content, dict):
                                    content = deserialized_content.get('text', str(deserialized_content))
                                else:
                                    content = str(deserialized_content)
                            
                            # 修正数据一致性：当role是assistant且有tool_calls时，content必须为None
                            final_content = content
                            if msg_doc.role == "assistant" and msg_doc.tool_calls and content is not None:
                                final_content = None
                            
                            message = Message(
                                role=msg_doc.role,
                                content=final_content,
                                name=msg_doc.name,
                                tool_calls=msg_doc.tool_calls,
                                tool_call_id=msg_doc.tool_call_id,
                                timestamp=msg_doc.timestamp.isoformat() if msg_doc.timestamp else None
                            )
                            if message not in results:
                                results.append(message)
            except Exception as e:
                push_warning(f"从MongoDB搜索消息失败: {e}")

        return list(reversed(results))

    @override
    def get_message_count(self) -> int:
        """获取消息数量"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            result = self.redis_client.llen(messages_key)
            return int(result) if isinstance(result, (int, float)) else 0

    @override
    def clear_messages(self, keep_summary: bool = True) -> None:
        """清空消息历史"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            self.redis_client.delete(messages_key)
            
            if not keep_summary:
                summary_key = self._get_redis_key("summary")
                self.redis_client.delete(summary_key)
            
            # 更新元数据
            metadata_key = self._get_redis_key("metadata")
            metadata_str = self.redis_client.get(metadata_key)
            metadata = json.loads(str(metadata_str)) if metadata_str else {}
            
            metadata["total_messages"] = 0
            metadata["last_activity"] = datetime.now().isoformat()
            
            self.redis_client.set(metadata_key, json.dumps(metadata))

    @override
    def serialize(self) -> Dict[str, Any]:
        """序列化为字典"""
        with self._lock:
            return {
                "context_id": self.context_id,
                "metadata": self.get_metadata(),
                "messages": [msg.model_dump() for msg in self.retrieve_messages()],
                "summary": self.get_summary(),
                "serialization_timestamp": datetime.now().isoformat(),
            }

    @override
    def deserialize(self, data: Dict[str, Any]) -> None:
        """从字典反序列化"""
        with self._lock:
            # 恢复元数据
            if "metadata" in data:
                self.update_metadata(data["metadata"])
            
            # 恢复消息
            if "messages" in data:
                messages_key = self._get_redis_key("messages")
                self.redis_client.delete(messages_key)
                
                for message_data in data["messages"]:
                    try:
                        message = Message(**message_data)
                        message_json = message.model_dump_json()
                        self.redis_client.rpush(messages_key, message_json)
                    except Exception as e:
                        push_warning(f"反序列化消息失败: {e}")
            
            # 恢复摘要
            if "summary" in data and data["summary"]:
                self.update_summary(data["summary"])

    @override
    async def persist(self) -> bool:
        """持久化到MongoDB"""
        return self._sync_from_redis_to_mongo()

    @override
    async def restore(self) -> bool:
        """从MongoDB恢复"""
        try:
            context_doc = ContextDocument.objects(context_id=self.context_id).first()
            if context_doc:
                self._sync_from_mongo_to_redis(context_doc)
                return True
            return False
        except Exception as e:
            push_error(f"从MongoDB恢复失败: {e}")
            return False

    async def _auto_memory_manage(self) -> None:
        """自动内存管理"""
        if self.get_message_count() > self.max_history_length and self.llm_interface:
            # 创建摘要
            summary = await self.auto_summarize()
            
            # 保存摘要
            current_summary = self.get_summary()
            if current_summary:
                self.update_summary(f"{current_summary}\n\n{summary}")
            else:
                self.update_summary(summary)
            
            # 保留最近的一条消息
            messages = self.retrieve_messages()
            if messages:
                self.clear_messages(keep_summary=True)
                await self.store_message(messages[-1])

    @override
    async def auto_summarize(self) -> str:
        """自动总结历史记录"""
        if self._summarize_func:
            messages = self.retrieve_messages()
            return await self._summarize_func(messages)
        else:
            count = self.get_message_count()
            return f"对话包含 {count} 条消息。"

    @override
    def get_context_for_llm(self) -> str:
        """获取适合LLM的上下文字符串"""
        context_parts = []
        
        # 添加摘要
        summary = self.get_summary()
        if summary:
            context_parts.append(f"对话摘要：\n{summary}\n")
        
        # 添加最近的历史记录
        messages = self.retrieve_messages()
        if messages:
            context_parts.append("最近的对话历史：")
            for message in messages:
                role = message.role
                content = message.content
                if isinstance(content, str):
                    context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)

    @staticmethod
    async def _summarize_history_impl(messages: List[Message]) -> str:  # type: ignore
        """
        请根据以下对话历史，提取并总结关键信息。要求如下：

        1. 提炼用户的核心意图，并用【用户意图】字段明确描述。
        2. 提取所有出现过的关键参数、变量名、key、文件名等信息，并以【关键信息】字段列出，格式为每行一个，注明类型（如：文件、key、参数等）。
        3. 保留对话中涉及的重要操作、决策或变更，简明扼要地归纳在【对话要点】字段。
        4. 所有字段请严格按照如下格式输出：

        【用户意图】
        ...（简明描述用户的主要需求和目标）

        【关键信息】
        - 类型: 名称
        - 类型: 名称
        ...

        【对话要点】
        - 要点1
        - 要点2

        【操作的文件】
        - 文件1
        - 文件2
        - 文件3

        【下一步的计划】
        - 计划1
        - 计划2
        - 计划3

        【总结】
        - 总结1
        - 总结2

        ...

        请确保总结内容准确、结构清晰，便于后续检索和上下文恢复。
        Args:
            messages: 消息列表
        Returns:
            str: 总结后的对话历史
        """
        pass

    # ==================== MongoDB专有功能 ====================
    
    def query_messages_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Message]:
        """按时间范围查询消息"""
        try:
            context_doc = ContextDocument.objects(context_id=self.context_id).first()
            if not context_doc:
                return []
            
            results = []
            for msg_doc in context_doc.messages:
                if msg_doc.timestamp and start_time <= msg_doc.timestamp <= end_time:
                    # 处理content类型转换
                    content = None
                    if msg_doc.content:
                        deserialized_content = deserialize_from_mongo(msg_doc.content)
                        if isinstance(deserialized_content, (str, list)):
                            content = deserialized_content
                        elif isinstance(deserialized_content, dict):
                            content = deserialized_content.get('text', str(deserialized_content))
                        else:
                            content = str(deserialized_content)
                    
                    # 修正数据一致性：当role是assistant且有tool_calls时，content必须为None
                    final_content = content
                    if msg_doc.role == "assistant" and msg_doc.tool_calls and content is not None:
                        final_content = None
                    
                    message = Message(
                        role=msg_doc.role,
                        content=final_content,
                        name=msg_doc.name,
                        tool_calls=msg_doc.tool_calls,
                        tool_call_id=msg_doc.tool_call_id,
                        timestamp=msg_doc.timestamp.isoformat()
                    )
                    results.append(message)
            
            return results
        except Exception as e:
            push_error(f"按时间范围查询消息失败: {e}")
            return []
    
    def get_context_statistics(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        try:
            context_doc = ContextDocument.objects(context_id=self.context_id).first()
            if not context_doc:
                return {}
            
            # 统计各种消息类型
            role_counts: Dict[str, int] = {}
            for msg_doc in context_doc.messages:
                role = msg_doc.role
                role_counts[role] = role_counts.get(role, 0) + 1
            
            return {
                "context_id": self.context_id,
                "total_messages": len(context_doc.messages),
                "role_distribution": role_counts,
                "has_summary": bool(context_doc.summary),
                "start_time": context_doc.start_time.isoformat() if context_doc.start_time else None,
                "last_activity": context_doc.last_activity.isoformat() if context_doc.last_activity else None,
                "created_at": context_doc.created_at.isoformat() if context_doc.created_at else None,
                "updated_at": context_doc.updated_at.isoformat() if context_doc.updated_at else None,
            }
        except Exception as e:
            push_error(f"获取上下文统计信息失败: {e}")
            return {}
