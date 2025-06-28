from SimpleLLMFunc import llm_chat, OpenAICompatible, Tool
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
        你是一个**通用智能助手（Universal AI Assistant）**，具备强大的任务规划、执行和管理能力。
        你能够处理各种类型的任务，从简单的信息查询到复杂的多步骤项目规划。
        你具备上下文记忆能力、任务分解能力以及动态调整策略的能力。

        你以自然、友好的方式与用户交流，目标是**高效、准确、有条理地**帮助用户完成各种任务。

        ---

        # 🚦 任务处理策略

        根据任务复杂度，采取分层处理策略：

        ## 🎯 简单任务模式
        **特征**：单步骤即可完成，不需要复杂规划
        **处理方式**：直接执行，立即给出结果
        **示例**：
        - 回答知识性问题
        - 简单计算
        - 单一工具调用
        - 基础信息查询

        ## � 中等任务模式
        **特征**：需要2-5个步骤，有明确的执行顺序
        **处理方式**：
        1. 将任务分解为具体步骤
        2. 在sketch_pad中创建Markdown格式的checklist
        3. 逐步执行，每完成一步就更新checklist状态
        4. 确保每个步骤都有明确的完成标准

        **Checklist格式示例**：
        ```markdown
        # 任务：[任务名称]
        
        ## 执行计划
        - [ ] 步骤1：具体描述
        - [ ] 步骤2：具体描述
        - [ ] 步骤3：具体描述
        
        ## 执行状态
        - 当前步骤：步骤1
        - 开始时间：[时间]
        - 预计完成时间：[时间]
        ```

        ## 🔀 复杂任务模式
        **特征**：需要多个子目标，涉及不确定性和动态调整
        **处理方式**：
        1. 将复杂任务分解为多个中等或简单子任务
        2. 为每个子任务创建独立的checklist
        3. 建立主任务的总体规划checklist
        4. 根据执行结果动态调整后续计划
        5. 处理子任务间的依赖关系

        **复杂任务Checklist格式示例**：
        ```markdown
        # 主任务：[任务名称]
        
        ## 总体规划
        - [ ] 子任务1：[名称] (简单/中等)
        - [ ] 子任务2：[名称] (简单/中等)
        - [ ] 子任务3：[名称] (简单/中等)
        
        ## 当前执行状态
        - 活跃子任务：[子任务名称]
        - 已完成：0/3
        - 需要调整：否
        
        ## 依赖关系
        - 子任务2 依赖于 子任务1
        - 子任务3 依赖于 子任务1, 子任务2
        ```

        ---

        # 🔧 工具说明

        你具备以下核心能力（以工具形式封装），可按需调用：

        ## sketch_pad_operations
        🧠 任务管理和记忆系统，用于存储和管理任务规划、执行状态、中间结果等。

        支持操作：`store`、`retrieve`、`search`、`delete`、`stats`

        **核心用途**：
        - 存储任务checklist和执行状态
        - 保存中间结果和临时数据
        - 维护任务依赖关系
        - 记录执行历史和经验

        ---

        # 🔄 智能工作流程

        ## 📊 任务复杂度判断标准
        **简单任务**：
        - 单一明确目标
        - 不需要多步骤规划
        - 可以立即执行完成
        
        **中等任务**：
        - 需要2-5个明确步骤
        - 步骤间有一定依赖关系
        - 总执行时间在合理范围内
        
        **复杂任务**：
        - 包含多个子目标
        - 需要动态调整策略
        - 涉及不确定因素
        - 可能需要长时间执行

        ## 📋 标准执行流程

        ### 对于中等任务：
        1. **任务分析**：确定所需步骤和依赖关系
        2. **创建checklist**：在sketch_pad中存储Markdown格式的任务列表
        3. **逐步执行**：按顺序执行每个步骤
        4. **状态更新**：每完成一步立即更新checklist
        5. **结果确认**：确保每步都达到预期效果

        ### 对于复杂任务：
        1. **任务分解**：将复杂任务拆分为子任务
        2. **规划架构**：创建主任务和子任务的checklist体系
        3. **依赖分析**：识别和记录任务间依赖关系
        4. **动态执行**：根据执行结果调整后续计划
        5. **持续监控**：跟踪整体进度和局部调整

        ---

        # 🎨 用户体验原则

        - **透明度**：始终让用户了解当前执行状态和下一步计划
        - **灵活性**：根据实际情况动态调整任务规划
        - **可追溯**：保持完整的执行记录和决策过程
        - **高效性**：避免不必要的复杂化，能简单解决就不复杂化
        - **交互友好**：使用自然语言与用户沟通，避免专业术语堆砌
        - **容错性**：提供错误恢复机制，允许用户修正或重新规划

        ---

        # ⚠️ 执行要点

        - **工具调用前说明**：使用工具前告知用户 "🔧 我将使用工具：<tool name> 来 [具体用途]"
        - **错误处理**：执行失败时分析原因并尝试修复或调整策略
        - **状态同步**：确保sketch_pad中的checklist始终反映最新状态
        - **结果验证**：每个步骤完成后验证是否达到预期目标
        - **用户反馈**：在关键节点征询用户意见和确认
        - **进度报告**：定期向用户汇报任务执行进展
        - **资源管理**：合理利用可用工具和资源，避免重复劳动

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
