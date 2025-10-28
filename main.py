"""
SimpleAgent CLI客户端

一个现代化的CLI界面，提供丰富的交互体验和完整的会话管理功能。

Usage:
    python main.py [options]
    
Commands:
    python main.py                    # 启动交互式CLI
    python main.py --list-agents      # 列出所有可用的Agent
    python main.py --list-conversations  # 列出所有会话
"""

import asyncio
import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any
import readline  # 启用输入历史和编辑功能
import threading
import queue
from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.markdown import Markdown

from agent import get_agent, BaseAgent, get_agent_registry
from SimpleLLMFunc.base.post_process import extract_content_from_stream_response
from context.conversation_manager import get_conversation_manager, ConversationManager, Conversation

console = Console()


class CLIApp:
    """现代化CLI应用程序"""
    
    def __init__(self):
        self.console = console
        self.conversation_manager: ConversationManager = get_conversation_manager()
        self.current_agent: Optional[BaseAgent] = None
        self.current_conversation: Optional[Conversation] = None
        self.running = True
        
    def setup_agent(self, model_name: str = "sampleagent") -> BaseAgent:
        """设置并返回指定的Agent"""
        try:
            agent = get_agent(model_name=model_name)
            self.console.print(f"[green]✅ Agent '{model_name}' initialized successfully![/green]")
            return agent
        except Exception as e:
            self.console.print(f"[red]❌ Failed to initialize agent '{model_name}': {e}[/red]")
            raise
            
    def show_welcome(self):
        """显示欢迎信息"""
        welcome_panel = Panel.fit(
            "[bold blue]🤖 SimpleAgent CLI[/bold blue]\n\n"
            "[dim]现代化的AI助手命令行界面[/dim]\n"
            "[yellow]输入消息直接与AI对话，或使用以下命令：[/yellow]\n\n"
            "[cyan]/help[/cyan] - 显示帮助信息\n"
            "[cyan]/agents[/cyan] - 列出可用的Agent\n"
            "[cyan]/conversations[/cyan] - 管理会话\n"
            "[cyan]/delete <id>[/cyan] - 删除指定会话\n"
            "[cyan]/clear_all[/cyan] - 清空所有会话\n"
            "[cyan]/pad[/cyan] - SketchPad操作\n"
            "[cyan]/settings[/cyan] - 设置选项\n"
            "[cyan]quit[/cyan] 或 [cyan]exit[/cyan] - 退出程序\n\n"
            "[dim]💡 输入提示：[/dim]\n"
            "[dim]• 支持多行输入，带行号提示[/dim]\n"
            "[dim]• 每行输入后按回车继续[/dim]\n"
            "[dim]• 按 Ctrl+D (EOF) 提交消息[/dim]",
            title="[ 欢迎使用 SimpleAgent ]",
            border_style="blue"
        )
        self.console.print(welcome_panel)
        
    def get_user_input(self) -> str:
        """获取用户输入，使用可编辑的Panel界面，支持多行输入直到EOF"""
        try:
            return self._get_multiline_input_with_panel()
        except KeyboardInterrupt:
            return ""
        except EOFError:
            return "quit"
            
    def _get_multiline_input_with_panel(self) -> str:
        """使用Panel界面获取多行输入"""
        self.console.print("\n[dim]💡 多行输入模式：每行输入后按回车，完成后按 Ctrl+D 提交[/dim]")
        
        # 显示输入提示Panel
        prompt_panel = Panel(
            "[dim]请开始输入您的消息...[/dim]",
            title="[cyan]✏️ 等待输入[/cyan]",
            border_style="cyan",
            padding=(0, 1),
            title_align="left"
        )
        self.console.print(prompt_panel)
        
        input_lines = []
        line_number = 1
        
        try:
            while True:
                try:
                    # 显示行号提示，但不使用Live组件
                    line = input(f"[{line_number:2d}] ")
                    input_lines.append(line)
                    line_number += 1
                    
                except EOFError:
                    # 用户按了Ctrl+D，结束输入
                    # 先换行，让Panel显示更自然
                    print()
                    break
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]输入已取消[/yellow]")
            return ""
        
        # 合并所有输入行
        current_text = '\n'.join(input_lines).strip()
        
        # 输入完成，显示最终的不可编辑Panel
        if current_text:
            final_panel = Panel(
                current_text,
                title="[dim]👤 你[/dim]",
                border_style="cyan",
                padding=(0, 1),
                title_align="left"
            )
            self.console.print(final_panel)
            
        return current_text
            
    def display_user_message(self, message: str):
        """显示用户消息，使用Panel包装"""
        if message:
            user_panel = Panel(
                message,
                title="[dim]👤 你[/dim]",
                border_style="cyan",
                padding=(0, 1),
                title_align="left"
            )
            self.console.print(user_panel)
            
    def handle_command(self, command: str) -> bool | str:
        """处理特殊命令，返回True表示已处理"""
        cmd = command.lower().strip()
        
        # 帮助命令
        if cmd == "/help":
            self.show_help()
            return True
            
        # Agent管理命令
        if cmd == "/agents":
            self.show_agents()
            return True
            
        if cmd.startswith("/use "):
            agent_name = command[5:].strip()
            self.switch_agent(agent_name)
            return True
            
        # 会话管理命令
        if cmd == "/conversations" or cmd == "/convs":
            self.manage_conversations()
            return True
            
        if cmd.startswith("/new"):
            # 标记需要异步处理
            return "async_new_conversation"
            
        if cmd.startswith("/load "):
            conv_id = command[6:].strip()
            self.load_conversation(conv_id)
            return True
            
        if cmd.startswith("/delete "):
            conv_id = command[8:].strip()
            self.delete_conversation(conv_id)
            return True
            
        if cmd == "/clear_all":
            self.clear_all_conversations()
            return True
            
        # SketchPad命令
        if cmd == "/pad":
            self.show_sketch_pad()
            return True
            
        if cmd.startswith("/pad_search "):
            query = command[12:].strip()
            self.search_sketch_pad(query)
            return True
            
        if cmd.startswith("/pad_get "):
            key = command[9:].strip()
            self.get_sketch_pad_item(key)
            return True
            
        if cmd == "/pad_clear":
            self.clear_sketch_pad()
            return True
            
        # 设置命令
        if cmd == "/settings":
            self.show_settings()
            return True
            
        # 状态命令
        if cmd == "/status":
            self.show_status()
            return True
            
        if cmd == "/history":
            self.show_conversation_history()
            return True

        return False
        
    def show_help(self):
        """显示详细帮助信息"""
        help_table = Table(title="命令帮助", show_header=True, header_style="bold magenta")
        help_table.add_column("命令", style="cyan", no_wrap=True)
        help_table.add_column("描述", style="white")
        help_table.add_column("示例", style="yellow")
        
        commands = [
            ("/help", "显示此帮助信息", "/help"),
            ("/agents", "列出所有可用的Agent", "/agents"),
            ("/use <agent>", "切换到指定的Agent", "/use cadagent"),
            ("/conversations", "管理会话列表", "/conversations"),
            ("/new", "创建新会话", "/new"),
            ("/load <id>", "加载指定会话", "/load abc123"),
            ("/delete <id>", "删除指定会话", "/delete abc123"),
            ("/clear_all", "清空所有会话", "/clear_all"),
            ("/pad", "显示SketchPad内容", "/pad"),
            ("/pad_search <query>", "搜索SketchPad", "/pad_search 任务"),
            ("/pad_get <key>", "获取SketchPad项目", "/pad_get task_1"),
            ("/pad_clear", "清空SketchPad", "/pad_clear"),
            ("/status", "显示当前状态", "/status"),
            ("/history", "显示对话历史", "/history"),
            ("/settings", "显示设置选项", "/settings"),
            ("quit/exit", "退出程序", "quit"),
        ]
        
        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)
            
        self.console.print(help_table)
        
    def show_agents(self):
        """显示所有可用的Agent"""
        try:
            agent_registry = get_agent_registry()
            models = agent_registry.list_models()
            active_agents = agent_registry.get_all_agents_info()
            
            if not models:
                self.console.print("[yellow]没有找到可用的Agent[/yellow]")
                return
                
            agent_table = Table(title="可用的Agent", show_header=True, header_style="bold green")
            agent_table.add_column("模型名称", style="cyan", no_wrap=True)
            agent_table.add_column("描述", style="white")
            agent_table.add_column("状态", style="green")
            
            for model_name in models:
                if model_name in active_agents:
                    # 已创建的Agent实例
                    agent_info = active_agents[model_name]
                    description = agent_info.get("description", "无描述")
                    status = "✅ 当前" if hasattr(self, 'current_agent') and self.current_agent and self.current_agent.model_name == model_name else "🟢 已创建"
                else:
                    # 未创建的Agent类
                    description = "可创建的Agent类"
                    status = "⚪ 可用"
                    
                agent_table.add_row(model_name, description[:50] + "..." if len(description) > 50 else description, status)
                
            self.console.print(agent_table)
        except Exception as e:
            self.console.print(f"[red]❌ 获取Agent列表失败: {e}[/red]")
            
    def switch_agent(self, agent_name: str):
        """切换到指定的Agent"""
        try:
            agent = get_agent(model_name=agent_name)
            self.current_agent = agent
            self.console.print(f"[green]✅ 已切换到Agent: {agent_name}[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ 切换Agent失败: {e}[/red]")
            
    def manage_conversations(self):
        """管理会话"""
        try:
            conversations = self.conversation_manager.list_conversations()
            
            if not conversations:
                self.console.print("[yellow]没有找到已保存的会话[/yellow]")
                if Confirm.ask("是否创建新会话？"):
                    # 这里需要异步处理，但由于是在同步方法中，先提示用户使用命令
                    self.console.print("[cyan]请使用 '/new' 命令创建新会话[/cyan]")
                return
                
            # 显示会话列表
            conv_table = Table(title="会话列表", show_header=True, header_style="bold blue")
            conv_table.add_column("ID", style="cyan", no_wrap=True)
            conv_table.add_column("创建时间", style="white")
            conv_table.add_column("最后访问", style="white")
            conv_table.add_column("消息数", style="yellow")
            conv_table.add_column("状态", style="green")
            
            for conv in conversations[:10]:  # 只显示最近10个
                conv_id = conv["conversation_id"]  # 显示完整ID
                created = conv.get("created_at", "未知")[:19] if conv.get("created_at") else "未知"
                accessed = conv.get("last_accessed", "未知")[:19] if conv.get("last_accessed") else "未知"
                msg_count = str(conv.get("context_total_messages", 0))
                status = "🔵 当前" if self.current_conversation and self.current_conversation.uuid == conv["conversation_id"] else "⚪ 可用"
                
                conv_table.add_row(conv_id, created, accessed, msg_count, status)
                
            self.console.print(conv_table)
            
            # 提供操作选项
            self.console.print("\n[yellow]操作选项:[/yellow]")
            self.console.print("• 输入会话ID来加载: [cyan]/load <conversation_id>[/cyan]")
            self.console.print("• 删除指定会话: [cyan]/delete <conversation_id>[/cyan]")
            self.console.print("• 创建新会话: [cyan]/new[/cyan]")
            self.console.print("• 清空所有会话: [cyan]/clear_all[/cyan]")
            
        except Exception as e:
            self.console.print(f"[red]❌ 获取会话列表失败: {e}[/red]")
            
    async def create_new_conversation(self):
        """创建新会话"""
        try:
            # 如果当前有会话，先保存
            if self.current_conversation:
                await self.conversation_manager.save_conversation(self.current_conversation.uuid)
                
            conversation = self.conversation_manager.create_conversation()
            self.current_conversation = conversation
            self.console.print(f"[green]✅ 已创建新会话: {conversation.uuid[:8]}...[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ 创建会话失败: {e}[/red]")
            
    def load_conversation(self, conv_id: str):
        """加载指定会话"""
        try:
            # 如果输入的是短ID，尝试匹配完整ID
            conversations = self.conversation_manager.list_conversations()
            full_id = None
            
            for conv in conversations:
                conversation_id = conv["conversation_id"]
                if conversation_id.startswith(conv_id):
                    full_id = conversation_id
                    break
                    
            if not full_id:
                self.console.print(f"[red]❌ 未找到ID匹配的会话: {conv_id}[/red]")
                # 显示可用的会话ID前缀供参考
                self.console.print("[yellow]可用的会话ID前缀：[/yellow]")
                for conv in conversations[:5]:  # 只显示前5个
                    conv_id_short = conv["conversation_id"][:8]
                    self.console.print(f"  {conv_id_short}...")
                return
                
            conversation = self.conversation_manager.get_conversation(full_id)
            if conversation:
                # 保存当前会话（这里暂时忽略，因为在同步方法中）
                # TODO: 将load_conversation也改为异步方法
                    
                self.current_conversation = conversation
                self.console.print(f"[green]✅ 已加载会话: {full_id[:8]}...[/green]")
            else:
                self.console.print(f"[red]❌ 加载会话失败: {conv_id}[/red]")
        except Exception as e:
            self.console.print(f"[red]❌ 加载会话时发生错误: {e}[/red]")
            
    def delete_conversation(self, conv_id: str):
        """删除指定会话"""
        if not conv_id:
            self.console.print("[red]❌ 请提供会话ID[/red]")
            return
            
        try:
            # 如果输入的是短ID，尝试匹配完整ID
            conversations = self.conversation_manager.list_conversations()
            full_id = None
            
            for conv in conversations:
                conversation_id = conv["conversation_id"]
                if conversation_id.startswith(conv_id):
                    full_id = conversation_id
                    break
                    
            if not full_id:
                self.console.print(f"[red]❌ 未找到ID匹配的会话: {conv_id}[/red]")
                return
            
            # 确认删除
            if not Confirm.ask(f"确定要删除会话 {full_id[:8]}... 吗？此操作不可恢复"):
                self.console.print("[yellow]已取消删除操作[/yellow]")
                return
                
            # 如果删除的是当前会话，清除当前会话引用
            if self.current_conversation and self.current_conversation.uuid == full_id:
                self.current_conversation = None
                
            # 执行删除
            success = self.conversation_manager.delete_conversation(full_id)
            
            if success:
                self.console.print(f"[green]✅ 已成功删除会话: {full_id[:8]}...[/green]")
            else:
                self.console.print(f"[red]❌ 删除会话失败: {conv_id}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]❌ 删除会话时发生错误: {e}[/red]")
            
    def clear_all_conversations(self):
        """清空所有会话"""
        try:
            conversations = self.conversation_manager.list_conversations()
            
            if not conversations:
                self.console.print("[yellow]没有会话需要清空[/yellow]")
                return
                
            # 显示警告信息
            warning_panel = Panel.fit(
                f"[bold red]⚠️  危险操作警告 ⚠️[/bold red]\n\n"
                f"即将删除 [bold]{len(conversations)}[/bold] 个会话\n"
                f"此操作将永久删除：\n"
                f"• 所有对话历史\n"
                f"• 所有SketchPad数据\n"
                f"• MongoDB和Redis中的相关数据\n\n"
                f"[bold red]此操作不可恢复！[/bold red]",
                title="[ 确认清空所有会话 ]",
                border_style="red"
            )
            self.console.print(warning_panel)
            
            # 双重确认
            if not Confirm.ask("确定要清空所有会话吗？"):
                self.console.print("[yellow]已取消清空操作[/yellow]")
                return
                
            if not Confirm.ask("[bold red]最后确认：真的要删除所有会话吗？[/bold red]"):
                self.console.print("[yellow]已取消清空操作[/yellow]")
                return
            
            # 清除当前会话引用
            self.current_conversation = None
            
            # 执行批量删除
            deleted_count = 0
            failed_count = 0
            
            with self.console.status("[bold red]正在删除会话...") as status:
                for conv in conversations:
                    conv_id = conv["conversation_id"]
                    try:
                        success = self.conversation_manager.delete_conversation(conv_id)
                        if success:
                            deleted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        self.console.print(f"[dim]删除会话 {conv_id[:8]}... 失败: {e}[/dim]")
            
            # 显示结果
            if failed_count == 0:
                self.console.print(f"[green]✅ 已成功删除所有 {deleted_count} 个会话[/green]")
            else:
                self.console.print(f"[yellow]⚠️ 删除完成：成功 {deleted_count} 个，失败 {failed_count} 个[/yellow]")
                
        except Exception as e:
            self.console.print(f"[red]❌ 清空会话时发生错误: {e}[/red]")
            
    def show_sketch_pad(self):
        """显示SketchPad内容"""
        if not self.current_agent:
            self.console.print("[red]❌ 请先选择一个Agent[/red]")
            return
            
        try:
            summary = self.current_agent.get_sketch_pad_summary()
            if summary.strip():
                self.console.print(Panel.fit(
                        summary,
                    title="[ SketchPad 内容 ]",
                    border_style="cyan"
                ))
            else:
                self.console.print("[yellow]SketchPad为空[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ 获取SketchPad内容失败: {e}[/red]")
            
    def search_sketch_pad(self, query: str):
        """搜索SketchPad"""
        if not self.current_agent:
            self.console.print("[red]❌ 请先选择一个Agent[/red]")
            return
            
        if not query:
            self.console.print("[red]❌ 请提供搜索关键词[/red]")
            return
            
        try:
            results = self.current_agent.search_sketch_pad(query, 10)
            if results:
                search_table = Table(title=f"搜索结果: '{query}'", show_header=True, header_style="bold magenta")
                search_table.add_column("键", style="cyan", no_wrap=True)
                search_table.add_column("摘要", style="white")
                
                for item in results:
                    key = item.get('key', 'Unknown')
                    snippet = item.get('snippet', 'No summary')[:100] + "..." if len(item.get('snippet', '')) > 100 else item.get('snippet', 'No summary')
                    search_table.add_row(key, snippet)
                    
                self.console.print(search_table)
            else:
                self.console.print(f"[yellow]未找到匹配'{query}'的内容[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ 搜索失败: {e}[/red]")
            
    def get_sketch_pad_item(self, key: str):
        """获取SketchPad项目"""
        if not self.current_agent:
            self.console.print("[red]❌ 请先选择一个Agent[/red]")
            return
            
        if not key:
            self.console.print("[red]❌ 请提供项目键名[/red]")
            return
            
        try:
            value = self.current_agent.get_from_sketch_pad(key)
            if value is not None:
                display_value = str(value)
                # 如果内容太长，截断显示
                if len(display_value) > 1000:
                    display_value = display_value[:1000] + "\n\n[dim]... (内容已截断)[/dim]"
                    
                self.console.print(Panel.fit(
                    display_value,
                    title=f"[ SketchPad 项目: {key} ]",
                    border_style="green"
                ))
            else:
                self.console.print(f"[yellow]未找到键名为'{key}'的项目[/yellow]")
        except Exception as e:
            self.console.print(f"[red]❌ 获取项目失败: {e}[/red]")
            
    def clear_sketch_pad(self):
        """清空SketchPad"""
        if not self.current_agent:
            self.console.print("[red]❌ 请先选择一个Agent[/red]")
            return
            
        if Confirm.ask("确定要清空SketchPad吗？此操作不可恢复"):
            try:
                # 这里需要调用相应的清空方法
                # self.current_agent.clear_sketch_pad()
                self.console.print("[green]✅ SketchPad已清空[/green]")
            except Exception as e:
                self.console.print(f"[red]❌ 清空失败: {e}[/red]")
                
    def show_settings(self):
        """显示设置选项"""
        settings_panel = Panel.fit(
            "[bold cyan]当前设置[/bold cyan]\n\n"
            f"[yellow]当前Agent:[/yellow] {self.current_agent.name if self.current_agent else '未设置'}\n"
            f"[yellow]当前会话:[/yellow] {self.current_conversation.uuid[:8] + '...' if self.current_conversation else '未设置'}\n"
            f"[yellow]会话创建时间:[/yellow] {self.current_conversation.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.current_conversation else '无'}\n"
            f"[yellow]最后访问时间:[/yellow] {self.current_conversation.last_accessed.strftime('%Y-%m-%d %H:%M:%S') if self.current_conversation else '无'}\n\n"
            "[dim]使用相应命令可以修改这些设置[/dim]",
            title="[ 设置 ]",
            border_style="blue"
        )
        self.console.print(settings_panel)
        
    def show_status(self):
        """显示当前状态"""
        status_table = Table(title="系统状态", show_header=True, header_style="bold green")
        status_table.add_column("项目", style="cyan", no_wrap=True)
        status_table.add_column("状态", style="white")
        
        status_items = [
            ("Agent", self.current_agent.name if self.current_agent else "未设置"),
            ("会话", self.current_conversation.uuid[:8] + "..." if self.current_conversation else "未设置"),
            ("会话管理器", "✅ 已初始化" if self.conversation_manager else "❌ 未初始化"),
            ("系统时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ]
        
        # 如果有当前会话，添加更多信息
        if self.current_conversation:
            try:
                with self.current_conversation:
                    msg_count = self.current_conversation.context.get_message_count()
                    sketch_stats = self.current_conversation.sketch_pad.get_statistics()
                    status_items.extend([
                        ("消息数量", str(msg_count)),
                        ("SketchPad项目", str(sketch_stats.total_items)),
                        ("内存使用", f"{sketch_stats.memory_usage_percent:.1f}%"),
                    ])
            except Exception as e:
                status_items.append(("会话状态", f"❌ 错误: {e}"))
        
        for item, status in status_items:
            status_table.add_row(item, status)
            
        self.console.print(status_table)
        
    def show_conversation_history(self):
        """显示对话历史"""
        if not self.current_conversation:
            self.console.print("[red]❌ 当前没有活动会话[/red]")
            return

        try:
            with self.current_conversation:
                messages = self.current_conversation.context.retrieve_messages()
                
                if not messages:
                    self.console.print("[yellow]当前会话没有历史消息[/yellow]")
                    return

                history_table = Table(title="对话历史", show_header=True, header_style="bold blue")
                history_table.add_column("角色", style="cyan", no_wrap=True)
                history_table.add_column("内容", style="white", max_width=80)
                history_table.add_column("时间", style="yellow")
                
                for msg in messages[-10:]:  # 只显示最近10条
                    role = "🤖 助手" if msg.role == "assistant" else "👤 用户"
                    content = str(msg.content)[:200] + "..." if len(str(msg.content)) > 200 else str(msg.content)
                    # 处理时间戳格式
                    if hasattr(msg, 'timestamp') and msg.timestamp:
                        if isinstance(msg.timestamp, str):
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(msg.timestamp.replace('Z', '+00:00'))
                                timestamp = dt.strftime("%H:%M:%S")
                            except:
                                timestamp = msg.timestamp[:8] if len(msg.timestamp) >= 8 else msg.timestamp
                        else:
                            timestamp = msg.timestamp.strftime("%H:%M:%S")
                    else:
                        timestamp = "未知"
                    
                    history_table.add_row(role, content, timestamp)
                    
                self.console.print(history_table)
                
        except Exception as e:
            self.console.print(f"[red]❌ 获取历史记录失败: {e}[/red]")
            
    async def chat_with_agent(self, query: str):
        """与Agent进行对话"""
        if not self.current_agent:
            self.console.print("[red]❌ 请先选择一个Agent[/red]")
            return
            
        if not self.current_conversation:
            self.console.print("[yellow]⚠️ 没有活动会话，正在创建新会话...[/yellow]")
            await self.create_new_conversation()
            
        try:
            # 确保有会话后再运行
            if self.current_conversation:
                # 在会话上下文中运行
                with self.current_conversation:
                    # 使用Rich Live组件配合Panel包装的Markdown实现更好的流式显示效果
                    response_text = ""
                    
                    # 创建初始的Panel包装的Markdown，使用简洁的样式
                    markdown_content = Panel(
                        Markdown("", style="none"),
                        title="[dim]🤖 AI[/dim]",
                        border_style="dim",
                        padding=(0, 1),
                        title_align="left"
                    )
                    
                    with Live(
                        markdown_content, 
                        console=self.console, 
                        refresh_per_second=4, 
                        auto_refresh=True,
                        screen=False  # 允许内容超出屏幕，让终端自然滚动
                    ) as live:
                        async for chunk in self.current_agent.run(query):
                            try:
                                delta = extract_content_from_stream_response(chunk, "agent_stream") or ""
                            except Exception as e:
                                # 如果提取失败，尝试直接从chunk获取文本
                                delta = ""
                                if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content'):
                                    delta = chunk.delta.content or ""
                                elif isinstance(chunk, dict) and 'delta' in chunk:
                                    delta = chunk.get('delta', {}).get('content', "")
                                elif isinstance(chunk, str):
                                    delta = chunk
                                
                            if delta:
                                response_text += delta
                                # 更新Panel中的Markdown内容
                                markdown_content = Panel(
                                    Markdown(response_text, style="none"),
                                    title="[dim]🤖 AI[/dim]",
                                    border_style="dim",
                                    padding=(0, 1),
                                    title_align="left"
                                )
                                live.update(markdown_content)
            else:
                self.console.print("[red]❌ 无法创建会话，请重试[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]❌ 对话过程中发生错误: {e}[/red]")
            
    async def run(self):
        """运行CLI应用程序主循环"""
        try:
            # 初始化默认Agent
            self.current_agent = self.setup_agent()
            
            # 创建或加载会话
            await self.create_new_conversation()
            
            # 显示欢迎信息
            self.show_welcome()
            
            # 主循环
            while self.running:
                try:
                    user_input = self.get_user_input()
                    
                    if not user_input:
                        continue
                        
                    # 检查退出命令
                    if user_input.lower() in ["quit", "exit", "bye"]:
                        break
                        
                    # 处理特殊命令
                    command_result = self.handle_command(user_input)
                    if command_result == "async_new_conversation":
                        await self.create_new_conversation()
                        continue
                    elif command_result:
                        continue
                        
                    # 普通对话
                    await self.chat_with_agent(user_input)

                except KeyboardInterrupt:
                    self.console.print("\n[yellow]使用 'quit' 或 'exit' 退出程序[/yellow]")
                    continue
                except Exception as e:
                    self.console.print(f"[red]❌ 发生错误: {e}[/red]")
                    continue

        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """清理资源"""
        try:
            # 保存当前会话
            if self.current_conversation:
                await self.conversation_manager.save_conversation(self.current_conversation.uuid)
                self.console.print(f"[dim]会话 {self.current_conversation.uuid[:8]}... 已保存[/dim]")
                
            self.console.print("[green]👋 再见！[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ 清理时发生错误: {e}[/red]")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="SimpleAgent CLI客户端")
    parser.add_argument("--list-agents", action="store_true", help="列出所有可用的Agent")
    parser.add_argument("--list-conversations", action="store_true", help="列出所有会话")
    parser.add_argument("--agent", type=str, default="sampleagent", help="指定要使用的Agent名称")
    return parser.parse_args()


async def main(args):
    """主函数"""
    # 处理非交互式命令
    if args.list_agents:
        try:
            agent_registry = get_agent_registry()
            models = agent_registry.list_models()
            active_agents = agent_registry.get_all_agents_info()
            
            table = Table(title="可用的Agent", show_header=True, header_style="bold green")
            table.add_column("模型名称", style="cyan")
            table.add_column("描述", style="white")
            table.add_column("状态", style="green")
            
            for model_name in models:
                if model_name in active_agents:
                    # 已创建的Agent实例
                    agent_info = active_agents[model_name]
                    description = agent_info.get("description", "无描述")
                    status = "🟢 已创建"
                else:
                    # 未创建的Agent类
                    description = "可创建的Agent类"
                    status = "⚪ 可用"
                    
                table.add_row(model_name, description, status)
                
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ 获取Agent列表失败: {e}[/red]")
        return
        
    if args.list_conversations:
        try:
            conversation_manager = get_conversation_manager()
            conversations = conversation_manager.list_conversations()
            
            if not conversations:
                console.print("[yellow]没有找到已保存的会话[/yellow]")
                return
                
            table = Table(title="会话列表", show_header=True, header_style="bold blue")
            table.add_column("ID", style="cyan")
            table.add_column("创建时间", style="white")
            table.add_column("最后访问", style="white")
            table.add_column("消息数", style="yellow")
            
            for conv in conversations:
                conv_id = conv["conversation_id"]  # 显示完整ID
                created = conv.get("created_at", "未知")[:19] if conv.get("created_at") else "未知"
                accessed = conv.get("last_accessed", "未知")[:19] if conv.get("last_accessed") else "未知"
                msg_count = str(conv.get("context_total_messages", 0))
                
                table.add_row(conv_id, created, accessed, msg_count)
                
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ 获取会话列表失败: {e}[/red]")
        return
    
    # 启动交互式CLI
    app = CLIApp()
    await app.run()


if __name__ == "__main__":
    try:
        # 在异步运行之前解析参数，避免SystemExit异常
        args = parse_arguments()
        asyncio.run(main(args))
    except KeyboardInterrupt:
        console.print("\n[yellow]程序被中断[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ 致命错误: {e}[/red]")
        sys.exit(1)