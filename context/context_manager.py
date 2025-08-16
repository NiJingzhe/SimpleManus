import os
import json
import uuid
import threading
from typing import Dict, Optional, List, Type, Any, Literal
from datetime import datetime
from SimpleLLMFunc import OpenAICompatible
from context.schemas import Message
from context.context import ContextBackend, RedisFileContextBackend
from config.config import get_config
from SimpleLLMFunc.logger import push_warning, app_log


class ContextManager:
    """
    通用的上下文管理器，支持不同的后端实现。

    主要职责：
    1. 管理ContextBackend实例的创建和生命周期
    2. 提供高级的便捷接口
    3. 处理批量操作和清理任务
    4. 支持可插拔的后端实现
    """

    _instance = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, backend_class: Type[ContextBackend] = RedisFileContextBackend):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ContextManager, cls).__new__(cls)
                    cls._instance.backend_class = backend_class
        return cls._instance

    def __init__(self, backend_class: Type[ContextBackend]):
        """
        初始化上下文管理器

        Args:
            backend_class: 后端实现类，默认为RedisFileBackend
        """
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return

        self.backend_class = backend_class
        self.config = get_config()
        self.context_dir = self.config.CONTEXT_DIR
        self._active_contexts: Dict[str, ContextBackend] = {}

        # 确保目录存在
        os.makedirs(self.context_dir, exist_ok=True)

        self._initialized = True

    def create_context(
        self,
        context_id: Optional[str] = None,
        llm_interface: Optional[
            OpenAICompatible
        ] = get_config().CONTEXT_SUMMARY_INTERFACE,
        max_history_length: int = get_config().CONTEXT_MAX_HISTORY_LENGTH,
        **backend_kwargs,
    ) -> ContextBackend:
        """
        创建新的上下文对象

        Args:
            context_id: 上下文ID，如果为None则自动生成
            llm_interface: LLM接口
            max_history_length: 最大历史长度
            **backend_kwargs: 传递给后端的额外参数

        Returns:
            ContextBackend: 创建的上下文对象
        """
        with self._lock:
            if context_id is None:
                context_id = str(uuid.uuid4())

            # 检查是否已存在
            if context_id in self._active_contexts:
                app_log(f"Context {context_id} already exists, and is in active contexts. Returning the existing context.")
                return self._active_contexts[context_id]

            # 生成文件路径（如果后端需要）
            if "file_path" not in backend_kwargs:
                context_file = os.path.join(self.context_dir, f"ctx_{context_id}.json")
                backend_kwargs["file_path"] = context_file
                push_warning(f"Context file path: {context_file}")

            # 创建上下文对象
            context = self.backend_class(
                context_id=context_id,
                llm_interface=llm_interface,
                max_history_length=max_history_length,
                **backend_kwargs,
            )

            # 加入活动上下文列表
            self._active_contexts[context_id] = context

            return context

    def get_context(self, context_id: str) -> Optional[ContextBackend]:
        """
        获取指定ID的上下文对象

        Args:
            context_id: 上下文ID

        Returns:
            ContextBackend: 上下文对象，如果不存在则返回None
        """
        with self._lock:
            # 先检查活动上下文
            if context_id in self._active_contexts:
                return self._active_contexts[context_id]

            # 尝试从文件加载（如果后端支持）
            context_file = os.path.join(self.context_dir, f"ctx_{context_id}.json")
            if os.path.exists(context_file):
                try:
                    context = self.backend_class(
                        context_id=context_id,
                        llm_interface=self.config.CONTEXT_SUMMARY_INTERFACE,  # 可以后续设置
                        max_history_length=5,
                        file_path=context_file,
                    )
                    self._active_contexts[context_id] = context
                    return context
                except Exception as e:
                    print(f"Warning: Failed to load context {context_id}: {e}")

            return None

    def delete_context(self, context_id: str) -> bool:
        """
        删除指定ID的上下文对象

        Args:
            context_id: 上下文ID

        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            success = False

            # 从活动上下文中移除
            if context_id in self._active_contexts:
                del self._active_contexts[context_id]
                success = True

            # 删除文件（如果存在）
            context_file = os.path.join(self.context_dir, f"ctx_{context_id}.json")
            if os.path.exists(context_file):
                try:
                    os.remove(context_file)
                    success = True
                except Exception as e:
                    print(f"Warning: Failed to delete context file {context_file}: {e}")

            return success

    def list_contexts(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的上下文

        Returns:
            List[Dict]: 上下文信息列表
        """
        contexts = []

        # 扫描文件系统中的上下文文件
        try:
            for filename in os.listdir(self.context_dir):
                if filename.startswith("ctx_") and filename.endswith(".json"):
                    context_id = filename[4:-5]  # 移除 "ctx_" 前缀和 ".json" 后缀

                    context_info = {
                        "context_id": context_id,
                        "file_path": os.path.join(self.context_dir, filename),
                        "is_active": context_id in self._active_contexts,
                    }

                    # 尝试读取基本信息
                    try:
                        file_path = context_info["file_path"]
                        if isinstance(file_path, str):
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                metadata = data.get("metadata", {})
                                context_info.update(
                                    {
                                        "start_time": metadata.get("start_time"),
                                        "last_activity": metadata.get("last_activity"),
                                        "total_messages": metadata.get(
                                            "total_messages", 0
                                        ),
                                    }
                                )
                    except Exception:
                        pass  # 忽略读取错误

                    contexts.append(context_info)

        except Exception as e:
            print(f"Warning: Failed to list contexts: {e}")

        return contexts

    async def save_context(self, context_id: str) -> bool:
        """
        手动保存指定上下文到文件

        Args:
            context_id: 上下文ID

        Returns:
            bool: 是否成功保存
        """
        with self._lock:
            if context_id in self._active_contexts:
                try:
                    context = self._active_contexts[context_id]
                    return await context.persist()
                except Exception as e:
                    print(f"Warning: Failed to save context {context_id}: {e}")

            return False

    async def save_all_contexts(self) -> int:
        """
        保存所有活动上下文到文件

        Returns:
            int: 成功保存的上下文数量
        """
        saved_count = 0
        with self._lock:
            for context_id in list(self._active_contexts.keys()):
                if await self.save_context(context_id):
                    saved_count += 1

        return saved_count

    async def cleanup_inactive_contexts(self, max_inactive_time: int = 3600) -> int:
        """
        清理长时间未活动的上下文

        Args:
            max_inactive_time: 最大不活动时间（秒）

        Returns:
            int: 清理的上下文数量
        """
        cleaned_count = 0
        current_time = datetime.now()

        with self._lock:
            contexts_to_remove = []

            for context_id, context in self._active_contexts.items():
                try:
                    metadata = context.get_metadata()
                    last_activity_str = metadata.get("last_activity")
                    if last_activity_str:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        inactive_time = (current_time - last_activity).total_seconds()

                        if inactive_time > max_inactive_time:
                            # 保存上下文后移除
                            await context.persist()
                            contexts_to_remove.append(context_id)
                            cleaned_count += 1
                except Exception as e:
                    print(
                        f"Warning: Error checking activity for context {context_id}: {e}"
                    )

            # 移除非活动上下文
            for context_id in contexts_to_remove:
                del self._active_contexts[context_id]

        return cleaned_count

    # ===== 便捷接口 =====

    async def add_message(
        self,
        context_id: str,
        message: Message,
    ) -> bool:
        """
        便捷添加消息

        Args:
            context_id: 上下文ID
            role: 消息角色
            content: 消息内容
            **message_kwargs: 其他消息参数

        Returns:
            bool: 是否成功添加
        """
        backend = self.get_context(context_id)
        if not backend:
            return False

        try:
            await backend.store_message(message)
            return True
        except Exception as e:
            print(f"Warning: Failed to add message: {e}")
            return False

    def get_history(self, context_id: str, limit: Optional[int] = None) -> List:
        """
        获取对话历史

        Args:
            context_id: 上下文ID
            limit: 限制返回的消息数量

        Returns:
            List: 消息历史
        """
        backend = self.get_context(context_id)
        if not backend:
            return []

        return backend.retrieve_messages(limit)

    async def summarize_context(self, context_id: str) -> Optional[str]:
        """
        总结上下文

        Args:
            context_id: 上下文ID

        Returns:
            Optional[str]: 总结内容
        """
        backend = self.get_context(context_id)
        if not backend:
            return None

        return await backend.auto_summarize()


# 全局实例
_global_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局 ContextManager 实例"""
    global _global_context_manager
    if _global_context_manager is None:
        # 从config获取Redis配置
        config = get_config()

        # redis config
        redis_host = config.REDIS_HOST
        redis_port = int(config.REDIS_PORT)
        redis_db = int(config.REDIS_DB)

        # 创建自定义backend类，预配置Redis参数
        class ConfiguredRedisFileBackend(RedisFileContextBackend):
            def __init__(
                self,
                context_id: str,
                llm_interface: Optional[
                    OpenAICompatible
                ] = config.CONTEXT_SUMMARY_INTERFACE,
                max_history_length: int = config.CONTEXT_MAX_HISTORY_LENGTH,
                redis_host: str = redis_host,
                redis_port: int = redis_port,
                redis_db: int = redis_db,
                file_path: str = "",
            ):
                super().__init__(
                    context_id=context_id,
                    llm_interface=llm_interface,
                    max_history_length=max_history_length,
                    redis_host=redis_host,
                    redis_port=redis_port,
                    redis_db=redis_db,
                    file_path=file_path,
                )
                self.file_path = file_path
                self.context_id = context_id
                self.llm_interface = llm_interface
                self.max_history_length = max_history_length
                self.redis_host = redis_host
                self.redis_port = redis_port
                self.redis_db = redis_db

        # 使用配置好的backend类创建ContextManager
        _global_context_manager = ContextManager(
            backend_class=ConfiguredRedisFileBackend
        )
    return _global_context_manager
