from SimpleLLMFunc import llm_chat, OpenAICompatible, Tool, llm_function
from typing import (
    Dict,
    List,
    Optional,
    Callable,
    Generator,
    Tuple,
    Sequence,
    AsyncGenerator,
)
from context.context import ensure_global_context
from context.sketch_pad import get_global_sketch_pad


class BaseAgent:

    def __init__(
        self,
        name: str,
        description: str,
        toolkit: Optional[Sequence[Tool | Callable]] = None,
        llm_interface: Optional[OpenAICompatible] = None,
        max_history_length: int = 5,
        save_context: bool = True,
        context_file: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.toolkit = toolkit if toolkit is not None else []
        self.llm_interface = llm_interface

        if not self.llm_interface:
            raise ValueError("llm_interface must be provided")

        # 使用全局单例的上下文管理器
        self.context = ensure_global_context(
            llm_interface=self.llm_interface,
            max_history_length=max_history_length,
            save_to_file=save_context,
            context_file=context_file,
        )

        # 使用全局 SketchPad
        self.sketch_pad = get_global_sketch_pad()

        self.chat = llm_chat(
            llm_interface=self.llm_interface,
            toolkit=self.toolkit,  # type: ignore[call-arg]
            stream=True,
            max_tool_calls=2000,
            timeout=600,
        )(self.chat_impl)

        # 移除原来的历史总结功能，现在由ConversationContext处理
        # self.history: List[Dict[str, str]] = []

    @staticmethod
    def chat_impl(
        history: List[Dict[str, str]], query: str, time: str, sketch_pad_summary: str
    ) -> Generator[Tuple[str, List[Dict[str, str]]], None, None]:  # type: ignore[override]
        """
        # 🧠 身份说明
        你是一个**智能家庭大脑助手（Smart Home Brain）**，名叫**小智**或者**xiaozhi**，
        负责管理用户的智能家居系统，包括但不限于家庭设备联动、环境调控、能耗优化、安全监控、日程提醒等。
        你具备强大的上下文记忆能力、行为学习能力以及跨设备协同管理能力。


        你以中文与用户口语交流，说话要自然口语化，目标是让家庭变得**更智能、更舒适、更节能、更安全**。

        ---

        # 🚦 策略说明

        根据用户意图，采取如下应对策略：

        ## 🧭 通用对话模式
        用于闲聊、指令表达、信息咨询。你应快速理解用户意图，判断是否需调用具体工具，保持高响应性与自然交互体验。

        ## 🔄 自动化任务模式
        用户提出需求后，你会拆解为多步骤自动化流程，例如：
        - 「早上起床自动打开窗帘、播放音乐、烧水」
        - 「出门时关闭所有灯具与空调，启动安防系统」

        你需要合理规划触发条件、设备调度与异常处理。

        ## ⚙️ 状态管理模式
        对设备状态、家庭成员行为、能耗数据、环境信息进行持续感知与反馈。对用户的状态请求，提供清晰、简洁的数据反馈。例如：
        - 当前各房间温湿度、电器开启状态、空气质量、安防布防状态等。

        ## 🧠 学习增强模式
        在长期使用中，你会自动分析用户偏好与生活节律，生成个性化建议。例如：
        - 「你每天22:30会关灯，是否需要自动设定睡眠模式？」
        - 「检测到连续3天客厅湿度低于30%，是否建议自动加湿？」

        ---

        # 🔧 工具说明

        你具备以下核心能力（以工具形式封装），可按需调用：

        ## sketch_pad_operations
        🧠 内部记忆管理系统，用于存储与检索家庭配置、场景记录、行为习惯等。

        支持操作：`store`、`retrieve`、`search`、`delete`、`stats`

        **用途**：
        - 存储场景设置、用户偏好
        - 检索历史操作记录
        - 自动分析生活模式

        ---

        # 🔄 智能工作流建议

        ## 📋 标准场景设定流程
        1. 用户表达需求（如「回家时自动开灯」）
        2. 拆解成触发器 + 行为组 → 结构化存储
        3. 确认并写入场景管理器
        4. 调用测试/验证状态
        5. 后续自动运行 + 用户反馈学习

        ---

        ## 📌 场景命名建议
        - 根据行为与目的命名：如 “起床模式”、“离家布防”、“睡眠加湿”
        - 文件或记录结构使用语义化命名，便于管理

        ---

        # 🎨 用户体验原则

        - 所有交互需自然、直观，避免专业术语堆砌
        - 优先以对话方式引导用户设定而非命令式灌输
        - 所有操作均需具备回退机制与安全验证
        - 支持多成员个性化偏好管理（如张三喜冷、李四喜静）

        ---

        # ⚠️ 注意事项

        - 在每次工具调用前，需告诉用户说，“🔧 我将要使用工具：<tool name> 来 xxxxxx”
        - 若调用失败或执行结果不一致，必须进行分析并尝试修复
        - 所有用户偏好必须在首次建立后持久记忆
        - 所有自动化场景必须提供“立即生效”与“延时测试”选项
        - 若存在多设备冲突（如加湿器与除湿器），应主动提示并优化协调策略

        """

    def _get_sketch_pad_summary(self) -> str:
        """获取SketchPad的摘要信息，包括所有keys和截断的values"""
        try:
            # 获取所有项目的详细信息
            all_items = self.sketch_pad.list_all(include_details=True)

            if not all_items:
                return "SketchPad为空：无存储内容"

            summary_lines = [f"SketchPad当前状态 (共{len(all_items)}个项目):"]

            for item in all_items[:20]:  # 限制显示前20个项目
                key = item["key"]
                tags = ", ".join(item["tags"]) if item["tags"] else "无标签"
                timestamp = item["timestamp"]
                content_type = item["content_type"]

                # 获取完整内容并截断
                full_item = self.sketch_pad.get_item(key)
                if full_item:
                    value_str = str(full_item.value)
                    # 截断内容到合理长度
                    if len(value_str) > 100:
                        value_preview = value_str[:100] + "..."
                    else:
                        value_preview = value_str

                    # 处理换行符
                    value_preview = value_preview.replace("\n", "\\n")

                    summary_lines.append(
                        f"  • {key}: [{content_type}] {value_preview} "
                        f"(标签: {tags}, 时间: {timestamp[:19]})"
                    )
                else:
                    summary_lines.append(f"  • {key}: [已删除或无法访问]")

            if len(all_items) > 20:
                summary_lines.append(f"  ... 还有 {len(all_items) - 20} 个项目未显示")

            return "\n".join(summary_lines)

        except Exception as e:
            return f"获取SketchPad摘要时出错: {str(e)}"

    async def run(self, query: str) -> AsyncGenerator[str, None]:
        """Run the agent with the given query.

        Args:
            query (str): The query to process.

        Returns:
            Generator[str, None, None]: The response chunks from the agent.
        """
        if not query:
            raise ValueError("Query must not be empty")

        # 获得时间字符串
        import time

        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # 获得SketchPad的key和截断的value内容
        sketch_pad_summary = self._get_sketch_pad_summary()

        # 获取格式化的历史记录用于LLM调用
        history = self.context.get_formatted_history()

        response = self.chat(history, query, current_time, sketch_pad_summary)

        # 处理响应流并获取最终的历史记录
        final_history = history

        for response_str, updated_history in response:
            final_history = updated_history
            yield response_str

        # 同步chat函数更新后的历史记录到context
        await self.context.sync_with_external_history(final_history)

    # 上下文管理的便捷方法
    def get_conversation_history(self, limit: Optional[int] = None):
        """获取当前会话的对话历史"""
        return self.context.get_history(limit)

    def get_full_saved_history(self, limit: Optional[int] = None):
        """获取完整保存的对话历史"""
        return self.context.get_full_saved_history(limit)

    def search_conversation(self, query: str, limit: int = 5):
        """搜索当前会话的对话历史"""
        return self.context.search_history(query, limit)

    def search_full_history(self, query: str, limit: int = 5):
        """搜索完整保存的对话历史"""
        return self.context.search_full_history(query, limit)

    def clear_conversation(self, keep_summary: bool = True):
        """清空当前会话的对话历史"""
        self.context.clear_history(keep_summary)

    def get_conversation_summary(self):
        """获取当前会话的对话摘要"""
        return self.context.get_context_summary()

    def get_full_saved_summary(self):
        """获取完整保存的对话摘要"""
        return self.context.get_full_saved_summary()

    def export_conversation(self, file_path: str):
        """导出当前会话的对话记录"""
        self.context.export_context(file_path)

    def import_conversation(self, file_path: str, merge: bool = False):
        """导入对话记录"""
        self.context.import_context(file_path, merge)

    # SketchPad 管理的便捷方法
    async def store_in_sketch_pad(
        self,
        value,
        key: Optional[str] = None,
        tags: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ):
        """存储数据到 SketchPad"""
        return await self.sketch_pad.store(value, key, ttl=ttl, tags=tags)

    def get_from_sketch_pad(self, key: str):
        """从 SketchPad 获取数据"""
        return self.sketch_pad.retrieve(key)

    def search_sketch_pad(self, query: str, limit: int = 5):
        """搜索 SketchPad 内容"""
        return self.sketch_pad.search(query, limit)

    def get_sketch_pad_stats(self):
        """获取 SketchPad 统计信息"""
        return self.sketch_pad.get_statistics()

    def clear_sketch_pad(self):
        """清空 SketchPad"""
        self.sketch_pad.clear_all()

    def get_session_info(self):
        """获取会话信息（包括对话历史和 SketchPad 统计）"""
        return {
            "agent_name": self.name,
            "conversation_count": len(self.get_conversation_history()),
            "sketch_pad_stats": self.get_sketch_pad_stats(),
            "conversation_summary": self.get_conversation_summary(),
        }
