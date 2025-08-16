from __future__ import annotations  
import uuid
import threading
import os
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass
from SimpleLLMFunc import OpenAICompatible
from SimpleLLMFunc.logger import push_warning, push_error, app_log
from context.context_manager import get_context_manager, ContextManager
from context.sketch_manager import get_sketch_manager, SketchManager
from context.sketch_pad import SketchPadBackend
from context.context import ContextBackend
from config.config import get_config 



# 全局当前conversation上下文变量
_current_conversation: Optional[Conversation] = None
_conversation_context_lock = threading.RLock()


def get_current_conversation() -> Optional[Conversation]:
    """获取当前上下文中的Conversation"""
    global _current_conversation
    with _conversation_context_lock:
        return _current_conversation


def get_current_context() -> Optional[ContextBackend]:
    """获取当前上下文中的Context"""
    conversation = get_current_conversation()
    return conversation.context if conversation else None


def get_current_sketch_pad() -> Optional[SketchPadBackend]:
    """获取当前上下文中的SketchPad"""
    conversation = get_current_conversation()
    return conversation.sketch_pad if conversation else None


@dataclass
class Conversation:
    """
    Conversation 数据类，表示一个完整的对话会话
    包含唯一的 UUID、关联的 Context 和 SketchPad
    支持作为上下文管理器使用
    """
    uuid: str
    context: ContextBackend
    sketch_pad: SketchPadBackend
    created_at: datetime
    last_accessed: datetime
    
    def update_access_time(self):
        """更新最后访问时间"""
        self.last_accessed = datetime.now()
    
    def __enter__(self):
        """进入上下文管理器"""
        global _current_conversation
        with _conversation_context_lock:
            if _current_conversation is not None:
                raise RuntimeError("Cannot nest conversation contexts")
            _current_conversation = self
            self.update_access_time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        global _current_conversation
        with _conversation_context_lock:
            _current_conversation = None
        return False


class ConversationManager:
    """
    Conversation 管理器，负责创建、管理和协调 Conversation 的生命周期。
    每个 Conversation 包含一个 Context 和一个 SketchPad，它们共享相同的 UUID。
    
    ConversationManager 是全局单例，通过 ContextManager 和 SketchManager 
    来管理底层的 Context 和 SketchPad 对象。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConversationManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化 ConversationManager"""
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self.config = get_config()
        self.context_manager: ContextManager = get_context_manager()
        self.sketch_manager: SketchManager = get_sketch_manager()
        self._active_conversations: Dict[str, Conversation] = {}
        self._lock = threading.RLock()
        
        # 创建conversations目录
        self.conversations_dir = os.path.join(os.path.dirname(self.config.CONTEXT_DIR), "conversations")
        os.makedirs(self.conversations_dir, exist_ok=True)
        
        self._initialized = True
    
    def create_conversation(
        self,
        conversation_id: Optional[str] = None,
        llm_interface: Optional[OpenAICompatible] = None,
        max_history_length: int = 5
    ) -> Conversation:
        """
        创建新的 Conversation
        
        Args:
            conversation_id: Conversation UUID，如果为None则自动生成
            llm_interface: LLM接口，用于 Context
            max_history_length: Context 最大历史长度
            
        Returns:
            Conversation: 创建的 Conversation 对象
        """
        with self._lock:
            if conversation_id is None:
                conversation_id = str(uuid.uuid4())
            
            # 检查是否已存在
            if conversation_id in self._active_conversations:
                conversation = self._active_conversations[conversation_id]
                conversation.update_access_time()
                return conversation
            
            # 创建 Context（前缀 ctx）
            context = self.context_manager.create_context(
                context_id=conversation_id,
                llm_interface=llm_interface,
                max_history_length=max_history_length
            )
            
            # 创建 SketchPad（前缀 skt）
            sketch_pad = self.sketch_manager.create_sketch_pad(
                sketch_id=conversation_id
            )
            
            # 创建 Conversation 对象
            now = datetime.now()
            conversation = Conversation(
                uuid=conversation_id,
                context=context,
                sketch_pad=sketch_pad,
                created_at=now,
                last_accessed=now
            )
            
            # 加入活动 Conversation 列表
            self._active_conversations[conversation_id] = conversation
            
            # 立即持久化 context 和 sketch_pad 到文件系统
            try:
                import asyncio
                # 创建事件循环来运行异步任务
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(context.persist())
                    # 同步调用sketch_pad的persist方法
                    sketch_pad.persist()
                finally:
                    loop.close()
                app_log(f"✅ Conversation {conversation_id} 已成功持久化到文件系统")
            except Exception as e:
                push_warning(f"Failed to persist conversation {conversation_id}: {e}")
            
            # 创建持久化标记文件
            self._create_conversation_marker(conversation_id)
            
            return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        获取指定ID的 Conversation
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Conversation: Conversation 对象，如果不存在则返回None
        """
        with self._lock:
            # 先检查活动 Conversation
            if conversation_id in self._active_conversations:
                conversation = self._active_conversations[conversation_id]
                conversation.update_access_time()
                return conversation
            
            # 尝试从文件系统重建
            context = self.context_manager.get_context(conversation_id)
            sketch_pad = self.sketch_manager.get_sketch_pad(conversation_id)
            
            if context is not None and sketch_pad is not None:
                # 重建 Conversation 对象
                now = datetime.now()
                conversation = Conversation(
                    uuid=conversation_id,
                    context=context,
                    sketch_pad=sketch_pad,
                    created_at=now,  # 使用当前时间作为重建时间
                    last_accessed=now
                )
                
                self._active_conversations[conversation_id] = conversation
                return conversation
            
            return None
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除指定ID的 Conversation
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            success = False
            
            # 从活动 Conversation 中移除
            if conversation_id in self._active_conversations:
                del self._active_conversations[conversation_id]
                success = True
            
            # 删除底层的 Context 和 SketchPad
            context_deleted = self.context_manager.delete_context(conversation_id)
            sketch_deleted = self.sketch_manager.delete_sketch_pad(conversation_id)
            
            # 删除标记文件
            marker_file = os.path.join(self.conversations_dir, f"conv_{conversation_id}.marker")
            if os.path.exists(marker_file):
                try:
                    os.remove(marker_file)
                except Exception as e:
                    push_warning(f"Failed to delete marker file {marker_file}: {e}")
            
            return success or context_deleted or sketch_deleted
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的 Conversation
        
        Returns:
            List[Dict]: Conversation 信息列表
        """
        conversations = []
        
        # 扫描标记文件
        try:
            for filename in os.listdir(self.conversations_dir):
                if filename.startswith("conv_") and filename.endswith(".marker"):
                    conversation_id = filename[5:-7]  # 移除 "conv_" 前缀和 ".marker" 后缀
                    
                    conversation_info = {
                        "conversation_id": conversation_id,
                        "marker_file": os.path.join(self.conversations_dir, filename),
                        "is_active": conversation_id in self._active_conversations
                    }
                    
                    # 获取 Context 和 SketchPad 信息
                    context = self.context_manager.get_context(conversation_id)
                    sketch_pad = self.sketch_manager.get_sketch_pad(conversation_id)
                    
                    if context:
                        metadata = context.get_metadata()
                        conversation_info.update({
                            "context_start_time": metadata.get("start_time"),
                            "context_last_activity": metadata.get("last_activity"),
                            "context_total_messages": context.get_message_count(),
                            "context_has_summary": bool(context.get_summary())
                        })
                    
                    if sketch_pad:
                        stats = sketch_pad.get_statistics()
                        conversation_info.update({
                            "sketch_total_items": stats.total_items,
                            "sketch_max_items": stats.max_items,
                            "sketch_memory_usage": stats.memory_usage_percent
                        })
                    
                    conversations.append(conversation_info)
        
        except Exception as e:
            push_warning(f"Failed to list conversations: {e}")
        
        return conversations
    
    async def save_conversation(self, conversation_id: str) -> bool:
        """
        手动保存指定 Conversation 到文件
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            bool: 是否成功保存
        """
        with self._lock:
            if conversation_id in self._active_conversations:
                try:
                    conversation = self._active_conversations[conversation_id]
                    
                    # 保存 Context
                    context_saved = await conversation.context.persist()
                    
                    # 保存 SketchPad
                    conversation.sketch_pad.persist()
                    sketch_saved = True
                    
                    return bool(context_saved and sketch_saved)
                except Exception as e:
                    push_warning(f"Failed to save conversation {conversation_id}: {e}")
            
            return False
    
    async def save_all_conversations(self) -> int:
        """
        保存所有活动 Conversation 到文件
        
        Returns:
            int: 成功保存的 Conversation 数量
        """
        saved_count = 0
        with self._lock:
            for conversation_id in list(self._active_conversations.keys()):
                if await self.save_conversation(conversation_id):
                    saved_count += 1
        
        return saved_count
    
    async def cleanup_inactive_conversations(self, max_inactive_time: int = 3600) -> int:
        """
        清理长时间未活动的 Conversation
        
        Args:
            max_inactive_time: 最大不活动时间（秒）
            
        Returns:
            int: 清理的 Conversation 数量
        """
        cleaned_count = 0
        current_time = datetime.now()
        
        with self._lock:
            conversations_to_remove = []
            
            for conversation_id, conversation in self._active_conversations.items():
                try:
                    inactive_time = (current_time - conversation.last_accessed).total_seconds()
                    
                    if inactive_time > max_inactive_time:
                        # 保存 Conversation 后移除
                        await self.save_conversation(conversation_id)
                        conversations_to_remove.append(conversation_id)
                        cleaned_count += 1
                except Exception as e:
                    push_warning(f"Error checking activity for conversation {conversation_id}: {e}")
            
            # 移除非活动 Conversation
            for conversation_id in conversations_to_remove:
                del self._active_conversations[conversation_id]
        
        return cleaned_count
    
    def _create_conversation_marker(self, conversation_id: str) -> None:
        """
        创建 Conversation 标记文件
        
        Args:
            conversation_id: Conversation UUID
        """
        try:
            marker_file = os.path.join(self.conversations_dir, f"conv_{conversation_id}.marker")
            with open(marker_file, "w") as f:
                f.write(f"Conversation {conversation_id} created at {datetime.now().isoformat()}")
        except Exception as e:
            push_warning(f"Failed to create marker file for conversation {conversation_id}: {e}")


# 全局实例
_global_conversation_manager: Optional[ConversationManager] = None

def get_conversation_manager() -> ConversationManager:
    """获取全局 ConversationManager 实例"""
    global _global_conversation_manager
    if _global_conversation_manager is None:
        _global_conversation_manager = ConversationManager()
    return _global_conversation_manager