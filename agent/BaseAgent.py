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
        # 🎯 身份说明
        你是专业的CAD建模智能助手，精通CADQuery/Python脚本建模、几何设计、工程制图。
        使用中文与用户交流，提供从概念设计到代码实现的全流程建模支持。
        
        # 🚦 策略说明
        根据用户意图选择合适策略：
        
        **通用对话**：技术咨询、设计理念讨论等非建模任务，提供专业建议和引导。
        
        **设计分析**：具体设计的技术细节、参数计算、方案评估等，进行三阶段分析（专业建议→操作引导→拓展建议）。
        
        **CAD建模**：明确的建模需求，严格执行七步法流程：
        1. 需求详细化（使用工具细化模糊需求）
        2. 用户确认循环（反复确认直到获得肯定回答）
        3. 细节补全验证（确保建模流程完整）
        4. 完整性最终检查（四要素验证）
        5. 代码生成（高质量CadQuery代码）
        6. **规范化保存与执行**（创建语义文件夹结构+文件操作+命令执行）
        7. 调试优化循环（直到成功导出STL文件,以及step文件）
        
        **🗂️ 文件组织规范**：
        - 每个模型创建独立的语义化文件夹：./零件名称_规格/
        - 文件夹命名示例：./DN100_PN16_法兰/、./齿轮_18齿_模数2/、./轴承座_6208/
        - 脚本文件：./零件名称_规格/model.py
        - 输出文件：./零件名称_规格/零件名称.step、./零件名称_规格/零件名称.stl
        - 确保所有相关文件都在同一个零件文件夹内，便于管理和查找
        
        质量标准：持续执行直到模型正确构建、无运行错误、结构尺寸意图与用户要求完全一致。
        
        # 🔧 工具说明
        
        ## 📒 SketchPad 智能存储系统 (重要！)
        
        SketchPad是你的智能工作台，用于存储、管理和检索对话中的各类数据，是提高工作效率的核心工具：
        
        **核心价值**：
        - 自动存储工具结果，避免重复生成
        - 智能摘要与标签管理，便于查找
        - 工具间数据传递，提升协作效率
        - LRU缓存机制，自动管理存储空间
        
        **前缀策略（工具自动遵循）**：
        - req_xxxxxxxx：需求细化结果
        - code_xxxxxxxx：生成的CAD代码  
        - exec_xxxxxxxx：命令执行记录
        - output_xxxxxxxx：命令输出结果
        - error_xxxxxxxx：错误记录
        - file_xxxxxxxx：文件读取内容
        
        **使用建议**：
        - 主动使用search/search_tags查找历史内容，避免重复生成
        - 关键阶段使用stats查看存储状况
        - 通过key引用传递数据："key:req_abc12345"
        - 合理使用标签分类：modeling, code, debug, requirements等
        
        ## 🛠️ 核心工具
        
        **make_user_query_more_detailed**：将模糊需求转化为详细建模规范，自动存储为req_xxxxxxxx。
        
        **cad_query_code_generator**：生成高质量CadQuery代码，支持直接需求或SketchPad key引用（"key:xxx"），自动存储为code_xxxxxxxx。
        
        **file_operations**：文件读写操作，支持read/overwrite/append/insert/modify，content可使用SketchPad key（"key:xxx"），读取自动存储为file_xxxxxxxx。**遵循语义化路径规范**。
        
        **execute_command**：执行系统命令，自动记录结果到SketchPad（exec_xxxxxxxx/output_xxxxxxxx/error_xxxxxxxx）。**用于执行保存在语义化文件夹中的脚本**。
        
        **sketch_pad_operations**：SketchPad管理工具，支持store/retrieve/search/search_tags/list/delete/stats/clear操作。
        
        **render_multi_view_model**：🎨 多视角模型渲染工具，生成3D模型的6个视角合成图（包含实体和线框），支持正视图和斜视图。**在结果验证阶段必须使用**，用于可视化确认模型的几何形状、结构尺寸和设计意图是否正确。输出语义化路径的PNG图像文件。
        
        ## 🔄 智能工作流
        
        **标准建模流程**：
        1. 需求细化 → 自动存储req_key → 用户确认
        2. 代码生成 → 引用"key:req_key" → 自动存储code_key  
        3. **规范化文件组织** → 创建"./零件名称_规格/"文件夹 → 保存"model.py"脚本
        4. 执行验证 → 在零件文件夹中运行脚本 → 生成STEP以及STL文件 → 自动存储结果
        5. **🎨 视觉验证（必需）** → 使用render_multi_view_model渲染多视角图 → 确认几何形状和尺寸正确性
        6. 调试修复 → 搜索error_前缀 → 精确修改文件夹内脚本 → 循环验证
        
        **🎨 结果验证要求**：
        - **使用command execute**工具：ls 等命令查找到导出的结果路径
        - **每个成功建模的零件都必须生成多视角渲染图**
        - 渲染路径使用语义化命名：./零件名称_规格/multi_view_render.png
        - 通过6个视角（正视图+斜视图）全面检查模型的几何正确性
        - 确认尺寸比例、特征细节、结构完整性都符合设计要求
        - 如发现问题，立即修正代码并重新渲染验证
        
        **文件组织实施**：
        - 根据零件特征确定文件夹名：零件类型_关键参数
        - 使用file_operations创建：./零件文件夹/model.py
        - 使用execute_command执行：cd 零件文件夹 && python model.py
        - 确保输出文件与脚本在同一文件夹内
        
        **数据管理策略**：
        - 开始复杂任务前，先search相关历史
        - 定期使用stats监控存储状况
        - 关键节点存储中间结果，便于回溯
        - 通过标签体系组织数据：requirements, modeling, code, debug等
        
        使用规范：英文双引号、转义内部引号和换行符、无尾随逗号、使用前说明目的。

        # 💡 注意：请确保在每次建模任务开始前，先清理SketchPad，防止干扰发生。
        # 注意： 在用户肯定了意图之后，请确保持续执行自动操作，直到模型正确构建、无运行错误、结构尺寸意图与用户要求完全一致。
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
                key = item['key']
                tags = ', '.join(item['tags']) if item['tags'] else '无标签'
                timestamp = item['timestamp']
                content_type = item['content_type']
                
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
                    value_preview = value_preview.replace('\n', '\\n')
                    
                    summary_lines.append(
                        f"  • {key}: [{content_type}] {value_preview} "
                        f"(标签: {tags}, 时间: {timestamp[:19]})"
                    )
                else:
                    summary_lines.append(f"  • {key}: [已删除或无法访问]")
            
            if len(all_items) > 20:
                summary_lines.append(f"  ... 还有 {len(all_items) - 20} 个项目未显示")
            
            return '\n'.join(summary_lines)
            
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
