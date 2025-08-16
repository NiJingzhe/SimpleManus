from typing import Dict, List, Optional, Any, Union, override
from SimpleLLMFunc import async_llm_function, OpenAICompatible
import json
import os
import redis
import threading
from datetime import datetime
from abc import ABC, abstractmethod
from context.schemas import Message, ChatMessages


class ContextBackend(ABC):
    """
    ContextBackend 是上下文存储的后端接口，定义了面向实现侧的各种接口。
    
    主要职责：
    1. 定义存储、查询、序列化、持久化的核心接口
    2. 提供统一的抽象层，支持不同的存储实现
    3. 管理对话历史、摘要、元数据等核心数据
    """

    @abstractmethod
    def __init__(
        self,
        context_id: str,
        llm_interface: Optional[OpenAICompatible] = None,
        max_history_length: int = 5,
        file_path: Optional[str] = None,
    ):
        """
        初始化上下文后端

        Args:
            context_id: 上下文唯一标识符
            llm_interface: LLM接口，用于历史总结
            max_history_length: 最大历史记录长度
            file_path: 文件持久化路径（可选）
        """
        pass

    # ===== 核心存储接口 =====

    @abstractmethod
    async def store_message(self, message: Message) -> None:
        """存储一条消息"""
        pass

    @abstractmethod
    def retrieve_messages(self, limit: Optional[int] = None) -> List[Message]:
        """获取消息历史"""
        pass

    @abstractmethod
    def update_summary(self, summary: str) -> None:
        """更新对话摘要"""
        pass

    @abstractmethod
    def get_summary(self) -> Optional[str]:
        """获取对话摘要"""
        pass

    @abstractmethod
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新元数据"""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        pass

    # ===== 查询接口 =====

    @abstractmethod
    def search_messages(self, query: str, limit: int = 5) -> List[Message]:
        """搜索消息"""
        pass

    @abstractmethod
    def get_message_count(self) -> int:
        """获取消息数量"""
        pass

    @abstractmethod
    def clear_messages(self, keep_summary: bool = True) -> None:
        """清空消息历史"""
        pass

    # ===== 序列化接口 =====

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """序列化为字典"""
        pass

    @abstractmethod
    def deserialize(self, data: Dict[str, Any]) -> None:
        """从字典反序列化"""
        pass

    # ===== 持久化接口 =====

    @abstractmethod
    async def persist(self) -> bool:
        """持久化到存储"""
        pass

    @abstractmethod
    async def restore(self) -> bool:
        """从存储恢复"""
        pass

    # ===== 高级功能接口 =====

    @abstractmethod
    async def auto_summarize(self) -> str:
        """自动总结历史记录"""
        pass

    @abstractmethod
    def get_context_for_llm(self) -> str:
        """获取适合LLM的上下文字符串"""
        pass


class RedisFileContextBackend(ContextBackend):
    """
    ## RedisFileContextBackend 结合Redis即时存储和文件系统持久化的上下文后端实现。
    
    特点：
    1. Redis提供高性能的即时访问
    2. 文件系统提供可靠的持久化
    3. 支持自动同步和恢复
    4. 利用Redis AOF + RDB机制
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
        file_path: Optional[str] = None,
    ):
        """
        初始化Redis文件后端

        Args:
            context_id: 上下文唯一标识符
            llm_interface: LLM接口，用于历史总结
            max_history_length: 最大历史记录长度
            redis_host: Redis主机地址
            redis_port: Redis端口
            redis_db: Redis数据库编号
            file_path: 文件持久化路径
        """
        self.context_id = context_id
        self.llm_interface = llm_interface
        self.max_history_length = max_history_length
        self.file_path = file_path or f"contexts/ctx_{context_id}.json"
        
        # Redis连接
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 初始化历史总结函数
        self._summarize_func = None
        if self.llm_interface:
            self._summarize_func = async_llm_function(
                llm_interface=self.llm_interface,
                toolkit=[],
                timeout=600,
            )(self._summarize_history_impl)
        
        # 初始化元数据
        self._init_metadata()
        
        # 尝试从存储恢复数据
        self._restore_from_storage()

    def _init_metadata(self) -> None:
        """初始化元数据"""
        self._metadata = {
            "context_id": self.context_id,
            "session_id": self._generate_session_id(),
            "start_time": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "total_messages": 0,
            "max_history_length": self.max_history_length,
        }

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _get_redis_key(self, key: str) -> str:
        """获取Redis键名"""
        return f"context:{self.context_id}:{key}"

    @override
    async def store_message(self, message: Message) -> None:
        """
        存储一条消息
        如果消息数量超过了max_history_length，则会自动触发总结策略，然后按照这个策略来更新对话记录
        Args:
            message: 要存储的消息

        Returns:
            None
        """
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
            current_total = self._metadata.get("total_messages", 0)
            if isinstance(current_total, (int, float)):
                self._metadata["total_messages"] = int(current_total) + 1
            else:
                self._metadata["total_messages"] = 1
            self._metadata["last_activity"] = datetime.now().isoformat()
            
            # 自动持久化
            await self.persist()
            

    @override
    def retrieve_messages(self, limit: Optional[int] = None) -> List[Message]:
        """获取消息历史"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            message_data_list = self.redis_client.lrange(messages_key, 0, -1)
            
            messages = []
            for message_data in message_data_list:
                try:
                    message_dict = json.loads(message_data)
                    message = Message(**message_dict)
                    messages.append(message)
                except Exception as e:
                    print(f"Warning: Failed to deserialize message: {e}")
            
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
            return self.redis_client.get(summary_key)

    @override
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新元数据"""
        with self._lock:
            self._metadata.update(metadata)
            metadata_key = self._get_redis_key("metadata")
            self.redis_client.set(metadata_key, json.dumps(self._metadata))

    @override
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        with self._lock:
            return self._metadata.copy()

    @override
    def search_messages(self, query: str, limit: int = 5) -> List[Message]:
        """
        搜索消息

        Args:
            query: 搜索关键词
            limit: 搜索结果数量限制

        Returns:
            List[Message]: 搜索结果列表
        """
        messages = self.retrieve_messages()
        results = []
        query_lower = query.lower()

        for message in reversed(messages):
            content = message.content
            if isinstance(content, str) and query_lower in content.lower():
                results.append(message)
                if len(results) >= limit:
                    break

        return list(reversed(results))

    @override
    def get_message_count(self) -> int:
        """获取消息数量"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            return self.redis_client.llen(messages_key)

    @override
    def clear_messages(self, keep_summary: bool = True) -> None:
        """清空消息历史"""
        with self._lock:
            messages_key = self._get_redis_key("messages")
            self.redis_client.delete(messages_key)
            
            if not keep_summary:
                summary_key = self._get_redis_key("summary")
                self.redis_client.delete(summary_key)
            
            self._metadata["total_messages"] = 0
            self._metadata["last_activity"] = datetime.now().isoformat()

    @override
    def serialize(self) -> Dict[str, Any]:
        """序列化为字典"""
        with self._lock:
            return {
                "context_id": self.context_id,
                "metadata": self._metadata,
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
                self._metadata.update(data["metadata"])
            
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
                        print(f"Warning: Failed to deserialize message: {e}")
            
            # 恢复摘要
            if "summary" in data and data["summary"]:
                self.update_summary(data["summary"])

    @override
    async def persist(self) -> bool:
        """持久化到文件"""
        try:
            # 确保目录存在
            dir_path = os.path.dirname(self.file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # 序列化数据
            data = self.serialize()
            
            # 写入文件
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Warning: Failed to persist context: {e}")
            return False

    @override
    async def restore(self) -> bool:
        """从文件恢复"""
        if not os.path.exists(self.file_path):
            return False
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.deserialize(data)
            return True
        except Exception as e:
            print(f"Warning: Failed to restore context: {e}")
            return False

    def _restore_from_storage(self) -> None:
        """从存储恢复数据"""
        # 尝试从Redis恢复
        metadata_key = self._get_redis_key("metadata")
        stored_metadata = self.redis_client.get(metadata_key)
        if stored_metadata:
            try:
                self._metadata.update(json.loads(stored_metadata))
            except Exception as e:
                print(f"Warning: Failed to restore metadata from Redis: {e}")
        
        # 尝试从文件恢复
        if os.path.exists(self.file_path):
            import asyncio
            asyncio.create_task(self.restore())

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
