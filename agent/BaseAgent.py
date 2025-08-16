"""
BaseAgent 是所有 Agent 的基类，定义了 Agent 的基本接口和通用功能
所有具体的 Agent 实现都应该继承此类并实现抽象方法

BaseAgent 提供了以下功能：
- 单例模式
- 对话历史管理
- SketchPad 管理
- 工具集管理
"""
from typing import (
    Dict,
    List,
    Optional,
    Callable,
    Generator,
    Sequence,
    Tuple,
    AsyncGenerator,
    Any,
)
from abc import ABC, abstractmethod
from SimpleLLMFunc import llm_chat, OpenAICompatible # type: ignore
import threading
from context.conversation_manager import get_current_context, get_current_sketch_pad
from context.schemas import Message
import json
import os
import uuid


class BaseAgent(ABC):
    """
    Agent基类，定义了Agent的基本接口和通用功能

    所有具体的Agent实现都应该继承此类并实现抽象方法
    """

    # 类级别的实例缓存，确保每个Agent子类的单例
    _class_instances: Dict[str, "BaseAgent"] = {}
    _class_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        model_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        llm_interface: Optional[OpenAICompatible] = None,
        **kwargs,
    ) -> "BaseAgent":
        """
        获取Agent实例的类方法（单例模式）

        Args:
            model_name: 模型名称
            name: Agent名称
            description: Agent描述
            llm_interface: LLM接口
            **kwargs: 其他参数

        Returns:
            Agent实例
        """
        with cls._class_lock:
            # 使用类名和model_name作为唯一标识
            instance_key = f"{cls.__name__}:{model_name}"

            if instance_key not in cls._class_instances:
                if not llm_interface:
                    # 如果没有提供llm_interface，尝试从配置获取
                    from config.config import get_config

                    config = get_config()
                    llm_interface = config.BASIC_INTERFACE

                instance_name = name or f"{model_name}-agent"
                instance_description = description or f"Agent instance for {model_name}"

                cls._class_instances[instance_key] = cls(
                    name=instance_name,
                    description=instance_description,
                    llm_interface=llm_interface,
                    model_name=model_name,
                    **kwargs,
                )

            return cls._class_instances[instance_key]

    @classmethod
    def clear_instances(cls):
        """清空所有实例缓存"""
        with cls._class_lock:
            cls._class_instances.clear()

    @classmethod
    def get_all_instances(cls) -> Dict[str, "BaseAgent"]:
        """获取所有实例"""
        return cls._class_instances.copy()

    def __init__(
        self,
        name: str,
        description: str,
        llm_interface: Optional[OpenAICompatible] = None,
        model_name: Optional[str] = None,  # 添加model_name参数
        **kwargs,  # 额外的参数，子类可以处理
    ):
        self.name = name
        self.description = description
        self.model_name = model_name  # 存储model_name
        self.llm_interface = llm_interface

        if not self.llm_interface:
            raise ValueError("llm_interface must be provided")

        # 子类需要定义自己的工具集
        self.toolkit = self.get_toolkit()

        # 初始化chat函数
        self.chat = llm_chat(
            llm_interface=self.llm_interface,
            toolkit=self.toolkit,  # type: ignore
            stream=True,
            return_mode="raw",
            max_tool_calls=2000,
            timeout=600,
            temperature=1.0,
        )(self.chat_impl)

    @abstractmethod
    def get_toolkit(self) -> Sequence[Callable]:
        """
        获取Agent专用的工具集（抽象方法）

        子类必须实现此方法来定义自己的工具集

        Returns:
            工具函数列表
        """
        pass

    @abstractmethod
    def chat_impl(
        self,
        history: List[Dict[str, str]],
        query: str,
        sketch_pad_summary: str,
    ) -> Generator[Tuple[str, List[Dict[str, str]]], None, None]:
        """
        Agent的对话实现逻辑（抽象方法）

        子类必须实现此方法来定义具体的对话行为

        Args:
            history: 对话历史
            query: 用户查询
            sketch_pad_summary: SketchPad摘要

        Returns:
            Generator yielding (response_chunk, updated_history)
        """
        pass

    @abstractmethod
    def run(self, query: str) -> AsyncGenerator[str, None]:
        """
        运行Agent处理用户查询（抽象方法）

        Args:
            query: 用户查询

        Returns:
            AsyncGenerator yielding response chunks
        """
        pass

    # 通用辅助方法
    def get_sketch_pad_summary(self) -> str:
        """获取SketchPad的摘要信息，包括所有keys和截断的values"""
        try:
            sketch_pad = get_current_sketch_pad()
            if sketch_pad is None:
                return "SketchPad不可用：没有活动的conversation上下文"
            
            # 获取所有项目的详细信息（包含值）
            all_items = sketch_pad.list_items(include_value=True)

            if not all_items:
                return "SketchPad为空：无存储内容"

            summary_lines = [f"SketchPad当前状态 (共{len(all_items)}个项目):"]

            for item in all_items[:20]:  # 限制显示前20个项目
                key = item.key
                tags = ", ".join(item.tags) if item.tags else "无标签"
                timestamp = item.timestamp
                content_type = item.content_type

                # 使用列表项中包含的值进行预览
                value_obj = item.value
                value_str = str(value_obj) if value_obj is not None else ""
                if len(value_str) > 100:
                    value_preview = value_str[:100] + "..."
                else:
                    value_preview = value_str

                value_preview = value_preview.replace("\n", "\\n")

                summary_lines.append(
                    f"  • {key}: [{content_type}] {value_preview} "
                    f"(标签: {tags}, 时间: {timestamp[:19]})"
                )

            if len(all_items) > 20:
                summary_lines.append(f"  ... 还有 {len(all_items) - 20} 个项目未显示")

            return "\n".join(summary_lines)

        except Exception as e:
            return f"获取SketchPad摘要时出错: {str(e)}"

    # 上下文管理的便捷方法
    def get_conversation_history(self, limit: Optional[int] = None):
        """获取当前会话的对话历史"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        return context.retrieve_messages(limit)

    def get_full_saved_history(self, limit: Optional[int] = None):
        """获取完整保存的对话历史"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        return context.retrieve_messages(limit)

    def search_conversation(self, query: str, limit: int = 5):
        """搜索当前会话的对话历史"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        # 使用简单的搜索实现
        return context.search_messages(query, limit)

    def search_full_history(self, query: str, limit: int = 5):
        """搜索完整保存的对话历史"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        return context.search_messages(query, limit)

    def clear_conversation(self) -> None:
        """清空当前会话的对话历史"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        context.clear_messages(keep_summary=True)

    def get_conversation_summary(self) -> str:
        """获取当前会话的对话摘要"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        return context.get_summary() or ""

    def get_full_saved_summary(self) -> str:
        """获取完整保存的对话摘要"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        return context.get_summary() or ""

    def export_conversation(self, file_path: str) -> None:
        """导出当前会话的对话记录"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        data = context.serialize()
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_conversation(self, file_path: str, merge: bool = False) -> None:
        """导入对话记录"""
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not merge:
            # 清空现有消息但保留摘要
            context.clear_messages(keep_summary=True)
        context.deserialize(data)

    # SketchPad 管理的便捷方法
    async def store_in_sketch_pad(
        self,
        value,
        key: Optional[str] = None,
        tags: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        """存储数据到 SketchPad"""
        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            raise RuntimeError("No active conversation context")
        # 生成键名（若未提供）
        item_key = key or f"item_{uuid.uuid4().hex[:8]}"
        # tags 转换为 set
        tags_set = set(tags) if tags else None
        await sketch_pad.set_item(
            key=item_key,
            value=value,
            ttl=ttl,
            summary=None,
            tags=tags_set,
        )
        return item_key

    def get_from_sketch_pad(self, key: str) -> Any:
        """从 SketchPad 获取数据"""
        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            raise RuntimeError("No active conversation context")
        return sketch_pad.get_value(key)

    def search_sketch_pad(self, query: str, limit: int = 5):
        """搜索 SketchPad 内容"""
        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            raise RuntimeError("No active conversation context")
        return sketch_pad.search_by_content(query, limit)

    def get_sketch_pad_stats(self):
        """获取 SketchPad 统计信息"""
        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            raise RuntimeError("No active conversation context")
        return sketch_pad.get_statistics()

    def clear_sketch_pad(self):
        """清空 SketchPad"""
        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            raise RuntimeError("No active conversation context")
        sketch_pad.clear()

    def get_session_info(self):
        """获取会话信息（包括对话历史和 SketchPad 统计）"""
        try:
            conversation_count = len(self.get_conversation_history())
            sketch_pad_stats = self.get_sketch_pad_stats()
            conversation_summary = self.get_conversation_summary()
        except RuntimeError:
            # 如果没有活动的conversation上下文，返回基本信息
            conversation_count = 0
            sketch_pad_stats = {}
            conversation_summary = None
            
        return {
            "agent_name": self.name,
            "model_name": self.model_name,
            "agent_class": self.__class__.__name__,
            "conversation_count": conversation_count,
            "sketch_pad_stats": sketch_pad_stats,
            "conversation_summary": conversation_summary,
        }

    # ===== 通用：流式输出与按时序持久化 =====
    def _extract_text_from_chunk(self, chunk: Any) -> str:
        """从原始流式增量中提取纯文本内容（若存在）。"""
        try:
            if not hasattr(chunk, "choices") or not chunk.choices:
                return ""
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                return ""
            content = getattr(delta, "content", None)
            return content or ""
        except Exception:
            return ""

    def _msg_to_dict(self, msg: Any) -> Dict[str, Any]:
        """将后端返回的消息统一转为字典结构，兼容对象与字典两种形态。"""
        if isinstance(msg, dict):
            return msg
        return {
            "role": getattr(msg, "role", None),
            "content": getattr(msg, "content", None),
            "tool_calls": getattr(msg, "tool_calls", None),
            "tool_call_id": getattr(msg, "tool_call_id", None),
        }

    async def _stream_and_persist(
        self, response_packages: Generator[Tuple[Any, List[Any]], None, None]
    ) -> AsyncGenerator[Any, None]:
        """
        统一的流式处理与历史持久化逻辑：
        - 连续累积助手文本；遇到 tooluse/tool 结果时先落盘已累积文本，再写工具消息；
        - 确保历史中工具调用出现在其触发时刻之后，顺序正确。
        """
        context = get_current_context()
        if context is None:
            raise RuntimeError("No active conversation context")

        assistant_buffer: str = ""
        baseline_len: Optional[int] = None

        for raw_response, current_messages in response_packages:
            if baseline_len is None:
                try:
                    baseline_len = len(current_messages) if isinstance(current_messages, list) else 0
                except Exception:
                    baseline_len = 0

            # 直接把原始增量向上游转发
            yield raw_response

            # 累积文本
            delta_text = self._extract_text_from_chunk(raw_response)
            if delta_text:
                assistant_buffer += delta_text

            # 检查新产生的消息（含工具调用/工具结果）并按时序写入
            try:
                if isinstance(current_messages, list):
                    curr_len = len(current_messages)
                    if baseline_len is not None and curr_len > baseline_len:
                        new_msgs = current_messages[baseline_len:curr_len]
                        for nm in (self._msg_to_dict(x) for x in new_msgs):
                            role = nm.get("role")
                            content = nm.get("content")
                            tool_calls = nm.get("tool_calls")
                            tool_call_id = nm.get("tool_call_id")

                            # 工具相关出现前，先落盘已累积的助手文本
                            if (role == "assistant" and tool_calls) or role == "tool":
                                if assistant_buffer.strip():
                                    await context.store_message(
                                        Message(role="assistant", content=assistant_buffer)
                                    )
                                    assistant_buffer = ""

                            if role == "assistant" and tool_calls:
                                await context.store_message(
                                    Message(role="assistant", content=None, tool_calls=tool_calls)
                                )
                            elif role == "tool":
                                await context.store_message(
                                    Message(role="tool", content=content, tool_call_id=tool_call_id)
                                )
                        baseline_len = curr_len
            except Exception:
                pass

        # 流结束，写入残留的助手文本
        if assistant_buffer.strip():
            await context.store_message(Message(role="assistant", content=assistant_buffer))
