from typing import Dict, List, Optional, Any, Union
from SimpleLLMFunc import async_llm_function, OpenAICompatible
import json
import os
from datetime import datetime
import threading


class ConversationContext:
    """对话上下文管理类，提供历史记录的存储、查询和管理功能（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConversationContext, cls).__new__(cls)
        return cls._instance
    
    def __init__(
        self, 
        llm_interface: Optional[OpenAICompatible] = None,
        max_history_length: int = 5,
        save_to_file: bool = True,
        context_file: Optional[str] = None
    ):
        """
        初始化对话上下文管理器
        
        Args:
            llm_interface: LLM接口，用于历史总结
            max_history_length: 最大历史记录长度，超过会触发总结
            save_to_file: 是否保存到文件
            context_file: 上下文文件路径
        """
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self.llm_interface = llm_interface
        self.max_history_length = max_history_length
        self.save_to_file = save_to_file
        self.context_file = context_file or "context/conversation_history.json"
        
        # 对话历史记录
        self.history: List[Dict[str, Any]] = []
        
        # 对话摘要（用于长期记忆）
        self.conversation_summary: Optional[str] = None
        
        # 会话元数据
        self.session_metadata = {
            "session_id": self._generate_session_id(),
            "start_time": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "total_messages": 0
        }
        
        # 初始化历史总结函数
        if self.llm_interface:
            self.summarize_history = async_llm_function(
                llm_interface=self.llm_interface,
                toolkit=[],
                timeout=600,
            )(self._summarize_history_impl)
        
        # 加载已有的上下文
        self._load_context()
        
        # 标记已初始化
        self._initialized = True
    
    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    async def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加一条消息到历史记录
        
        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            metadata: 可选的元数据
        """
        message: Dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if metadata:
            message["metadata"] = metadata
        
        self.history.append(message)
        self.session_metadata["total_messages"] += 1
        self.session_metadata["last_activity"] = datetime.now().isoformat()
        
        # 自动管理内存
        await self._auto_memory_manage()
        
        # 保存到文件
        if self.save_to_file:
            self._save_context()
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取对话历史
        
        Args:
            limit: 限制返回的消息数量
            
        Returns:
            对话历史列表
        """
        if limit is None:
            return self.history.copy()
        return self.history[-limit:] if limit > 0 else []
    
    def get_formatted_history(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        获取格式化的对话历史（用于LLM调用）
        
        Args:
            include_metadata: 是否包含元数据
            
        Returns:
            格式化的对话历史
        """
        formatted_history = []
        for msg in self.history:
            formatted_msg = msg 
            
            if include_metadata and "metadata" in msg:
                formatted_msg["metadata"] = msg["metadata"]
            formatted_history.append(formatted_msg)
        
        return formatted_history
    
    def search_history(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        在历史记录中搜索相关消息
        
        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            
        Returns:
            相关的历史消息
        """
        results = []
        query_lower = query.lower()
        
        for msg in reversed(self.history):
            if query_lower in msg["content"].lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        
        return list(reversed(results))
    
    def clear_history(self, keep_summary: bool = True) -> None:
        """
        清空历史记录
        
        Args:
            keep_summary: 是否保留摘要
        """
        if not keep_summary:
            self.conversation_summary = None
        
        self.history.clear()
        self.session_metadata["total_messages"] = 0
        self.session_metadata["last_activity"] = datetime.now().isoformat()
        
        if self.save_to_file:
            self._save_context()
    
    def get_context_summary(self) -> Optional[str]:
        """获取对话摘要"""
        return self.conversation_summary
    
    def set_context_summary(self, summary: str) -> None:
        """设置对话摘要"""
        self.conversation_summary = summary
        if self.save_to_file:
            self._save_context()
    
    def get_session_metadata(self) -> Dict[str, Any]:
        """获取会话元数据"""
        return self.session_metadata.copy()
    
    async def _auto_memory_manage(self) -> None:
        """自动内存管理"""
        if len(self.history) > self.max_history_length and self.llm_interface:
            # 创建摘要
            summary = await self.summarize_history(self.history)
            
            # 保存摘要并清理历史
            if self.conversation_summary:
                self.conversation_summary = f"{self.conversation_summary}\n\n{summary}"
            else:
                self.conversation_summary = summary
            
            # 保留最近的一条消息作为上下文连接
            last_message = self.history[-1] if self.history else None
            self.history = []
            
            if last_message:
                # 添加摘要消息
                self.history.append({
                    "role": "assistant",
                    "content": f"During the conversation happened just a moment ago, {summary}.\nNow you are supposed to continue to assist the user to achieve their target.",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"type": "summary"}
                })
    
    def _save_context(self) -> None:
        """保存上下文到文件（追加模式保存历史记录）"""
        try:
            # 确保context_file有有效路径
            if not self.context_file:
                return
                
            # 确保目录存在
            dir_path = os.path.dirname(self.context_file)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # 读取现有的历史记录（如果文件存在）
            existing_data = {}
            if os.path.exists(self.context_file):
                try:
                    with open(self.context_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    existing_data = {}
            
            # 合并历史记录（追加到现有历史记录）
            existing_history = existing_data.get("history", [])
            combined_history = existing_history + self.history
            
            # 合并摘要
            existing_summary = existing_data.get("conversation_summary", "")
            combined_summary = ""
            if existing_summary and self.conversation_summary:
                combined_summary = f"{existing_summary}\n\n{self.conversation_summary}"
            elif existing_summary:
                combined_summary = existing_summary
            elif self.conversation_summary:
                combined_summary = self.conversation_summary
            
            context_data = {
                "session_metadata": self.session_metadata,
                "history": combined_history,  # 保存所有历史记录
                "conversation_summary": combined_summary  # 保存合并的摘要
            }
            
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"警告：保存上下文失败: {e}")
    
    def _load_context(self) -> None:
        """从文件加载上下文（但不加载历史记录）"""
        if not self.context_file or not os.path.exists(self.context_file):
            return
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            # 只加载session元数据，不加载历史记录和摘要
            # 这样可以保持历史记录文件的存在，但每次启动都是全新的对话
            # self.session_metadata.update(context_data.get("session_metadata", {}))
            # self.history = context_data.get("history", [])  # 不加载历史记录
            # self.conversation_summary = context_data.get("conversation_summary")  # 不加载摘要
            
            print("历史记录文件存在但不会被加载，每次启动都是全新对话")
            
        except Exception as e:
            print(f"警告：检查上下文文件失败: {e}")
    
    async def _summarize_history_impl(self, history: List[Dict[str, Any]]) -> str:
        """
        总结对话历史的实现
        
        Args:
            history: 对话历史记录
            
        Returns:
            对话摘要
        """
        """Summarize the conversation history.
        Focus on what the user wants to achieve, and what the agent has done to help the user achieve it.

        Args:
            history (List[Dict[str, Any]]): The conversation history.

        Returns:
            str: The summarized conversation

        Example:
        input: [
            {"role": "user", "content": "What is the design specification for part X?"},
            {"role": "assistant", "content": "The design specification for part X is..."},
            {"role": "user", "content": "Can you help me model part Y?"},
            {"role": "assistant", "content": "Sure, I can help you with that."}
        ]
        output: "User asked about design specification for part X and requested help with modeling part Y. Agent provided the design specification and agreed to help with modeling."

        
        DO NOT COMPRESS CODE CONTENT, DO NOT ADD ANY EXTRA TEXT.
        """
        return ""  # 这个函数会被llm_function装饰器替换
    
    def export_context(self, file_path: str) -> None:
        """
        导出完整的上下文到指定文件
        
        Args:
            file_path: 导出文件路径
        """
        export_data = {
            "session_metadata": self.session_metadata,
            "history": self.history,
            "conversation_summary": self.conversation_summary,
            "export_time": datetime.now().isoformat()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def import_context(self, file_path: str, merge: bool = False) -> None:
        """
        从文件导入上下文
        
        Args:
            file_path: 导入文件路径
            merge: 是否与现有上下文合并
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        if merge:
            # 合并历史记录
            imported_history = import_data.get("history", [])
            self.history.extend(imported_history)
            
            # 合并摘要
            imported_summary = import_data.get("conversation_summary")
            if imported_summary:
                if self.conversation_summary:
                    self.conversation_summary = f"{self.conversation_summary}\n\n{imported_summary}"
                else:
                    self.conversation_summary = imported_summary
        else:
            # 完全替换
            self.history = import_data.get("history", [])
            self.conversation_summary = import_data.get("conversation_summary")
            self.session_metadata.update(import_data.get("session_metadata", {}))
        
        if self.save_to_file:
            self._save_context()
    
    async def sync_with_external_history(self, external_history: List[Dict[str, str]]) -> None:
        """
        同步外部历史列表的更新到内部上下文
        
        Args:
            external_history: 来自chat函数的历史列表（通常不包含timestamp等元数据）
        """
        # 计算需要添加的新消息数量
        current_count = len(self.history)
        external_count = len(external_history)
        
        if external_count > current_count:
            # 添加新的消息，补充时间戳等元数据
            for i in range(current_count, external_count):
                msg = external_history[i].copy()
                msg["timestamp"] = datetime.now().isoformat()
                self.history.append(msg)
                
                # 更新会话元数据
                self.session_metadata["total_messages"] = len(self.history)
                self.session_metadata["last_activity"] = datetime.now().isoformat()
        
        # 自动管理内存
        await self._auto_memory_manage()
        
        # 保存到文件
        if self.save_to_file:
            self._save_context()
    
    def get_full_saved_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取文件中保存的完整对话历史（不影响当前session）
        
        Args:
            limit: 限制返回的消息数量，从最新开始
            
        Returns:
            完整的对话历史列表
        """
        if not self.context_file or not os.path.exists(self.context_file):
            return []
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            full_history = context_data.get("history", [])
            
            if limit is None:
                return full_history
            return full_history[-limit:] if limit > 0 else []
            
        except Exception as e:
            print(f"警告：读取完整历史失败: {e}")
            return []
    
    def get_full_saved_summary(self) -> Optional[str]:
        """
        获取文件中保存的完整对话摘要
        
        Returns:
            完整的对话摘要
        """
        if not self.context_file or not os.path.exists(self.context_file):
            return None
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            return context_data.get("conversation_summary")
            
        except Exception as e:
            print(f"警告：读取完整摘要失败: {e}")
            return None
    
    def search_full_history(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        在完整保存的历史记录中搜索相关消息
        
        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            
        Returns:
            相关的历史消息
        """
        full_history = self.get_full_saved_history()
        results = []
        query_lower = query.lower()
        
        for msg in reversed(full_history):
            if query_lower in msg["content"].lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        
        return list(reversed(results))

# 全局单例实例管理
_global_context: Optional[ConversationContext] = None

def get_global_context() -> Optional[ConversationContext]:
    """获取全局的ConversationContext单例实例"""
    return _global_context

def initialize_global_context(
    llm_interface: Optional[OpenAICompatible] = None,
    max_history_length: int = 5,
    save_to_file: bool = True,
    context_file: Optional[str] = None
) -> ConversationContext:
    """
    初始化全局的ConversationContext实例
    
    Args:
        llm_interface: LLM接口，用于历史总结
        max_history_length: 最大历史记录长度，超过会触发总结
        save_to_file: 是否保存到文件
        context_file: 上下文文件路径
        
    Returns:
        ConversationContext: 全局上下文实例
    """
    global _global_context
    _global_context = ConversationContext(
        llm_interface=llm_interface,
        max_history_length=max_history_length,
        save_to_file=save_to_file,
        context_file=context_file
    )
    return _global_context

def ensure_global_context(
    llm_interface: Optional[OpenAICompatible] = None,
    **kwargs
) -> ConversationContext:
    """
    确保全局上下文存在，如果不存在则创建
    
    Args:
        llm_interface: LLM接口
        **kwargs: 其他初始化参数
        
    Returns:
        ConversationContext: 全局上下文实例
    """
    global _global_context
    if _global_context is None:
        _global_context = initialize_global_context(llm_interface=llm_interface, **kwargs)
    return _global_context
