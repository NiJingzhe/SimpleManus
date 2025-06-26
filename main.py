import asyncio
import sys
from time import sleep

from rich.console import Console
from rich.panel import Panel

from agent.BaseAgent import BaseAgent
from config.config import get_config
from context.context import initialize_global_context
from tools import (
    execute_command,
    file_operations,
    make_user_query_more_detailed,
    cad_query_code_generator,
    sketch_pad_operations,
    render_multi_view_model,
)

console = Console()


def setup_agent():
    try:
        config = get_config()
        
        # 首先初始化全局context
        initialize_global_context(
            llm_interface=config.BASIC_INTERFACE,
            max_history_length=20,
            save_to_file=True,
            context_file="context/conversation_history.json"
        )
        
        toolkit = [
            make_user_query_more_detailed,
            execute_command,
            file_operations,
            cad_query_code_generator,
            sketch_pad_operations,
            render_multi_view_model,
        ]
        agent = BaseAgent(
            name="CAD Assistant",
            description="Professional CAD modeling assistant",
            toolkit=toolkit,
            llm_interface=config.BASIC_INTERFACE,
        )
        console.print("CAD Assistant initialized successfully!")
        return agent
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return None


def get_input() -> str:
    lines = []
    console.print("\n===========================")
    console.print(">>> ", end="")
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    except KeyboardInterrupt:
        return ""
    return "\n".join(lines).strip()


def handle_special_commands(agent: BaseAgent, query: str) -> bool:
    """处理特殊命令，返回True表示已处理，False表示需要继续正常处理"""
    query_lower = query.lower().strip()
    
    if query_lower == "/help":
        console.print(Panel.fit(
            "[bold cyan]Special Commands:[/bold cyan]\n"
            "[yellow]/help[/yellow] - Show this help\n"
            "[yellow]/history[/yellow] - Show current session history\n"
            "[yellow]/full_history[/yellow] - Show complete saved history\n"
            "[yellow]/clear[/yellow] - Clear current session history\n"
            "[yellow]/summary[/yellow] - Show current session summary\n"
            "[yellow]/full_summary[/yellow] - Show complete saved summary\n"
            "[yellow]/export <filename>[/yellow] - Export current session to file\n"
            "[yellow]/session[/yellow] - Show session information\n"
            "[yellow]/search <query>[/yellow] - Search current session history\n"
            "[yellow]/search_all <query>[/yellow] - Search complete saved history\n"
            "[yellow]/pad[/yellow] - Show SketchPad contents\n"
            "[yellow]/pad_stats[/yellow] - Show SketchPad statistics\n"
            "[yellow]/pad_clear[/yellow] - Clear SketchPad\n"
            "[yellow]/pad_search <query>[/yellow] - Search SketchPad\n"
            "[yellow]/pad_store <key> <value>[/yellow] - Store content in SketchPad\n"
            "[yellow]/pad_get <key>[/yellow] - Get content from SketchPad\n"
            "[yellow]/pad_delete <key>[/yellow] - Delete item from SketchPad\n"
            "[yellow]/pad_update <key> <new_value>[/yellow] - Update existing item\n"
            "[yellow]/pad_tag <key> <tags>[/yellow] - Add tags to existing item\n"
            "[yellow]Ctrl+C[/yellow] - Exit"
        ))
        return True
    
    elif query_lower == "/history":
        history = agent.get_conversation_history(10)  # 当前会话最近10条
        if history:
            console.print(Panel.fit(
                "\n".join([f"[{msg['role']}]: {msg['content'][:100]}..." 
                          if len(msg['content']) > 100 else f"[{msg['role']}]: {msg['content']}" 
                          for msg in history[-5:]]),  # 显示最近5条
                title="[ Current Session History ]",
                border_style="yellow",
            ))
        else:
            console.print("[yellow]No conversation history in current session.[/yellow]")
        return True
    
    elif query_lower == "/full_history":
        # 获取完整保存的历史记录
        from context.context import get_global_context
        global_context = get_global_context()
        if global_context:
            full_history = global_context.get_full_saved_history(20)  # 最近20条
            if full_history:
                console.print(Panel.fit(
                    "\n".join([f"[{msg['role']}]: {msg['content'][:100]}..." 
                              if len(msg['content']) > 100 else f"[{msg['role']}]: {msg['content']}" 
                              for msg in full_history[-10:]]),  # 显示最近10条
                    title="[ Complete Saved History ]",
                    border_style="blue",
                ))
            else:
                console.print("[yellow]No saved history found.[/yellow]")
        else:
            console.print("[red]❌ Global context not available.[/red]")
        return True
    
    elif query_lower == "/clear":
        agent.clear_conversation()
        console.print("[green]✅ Current session history cleared![/green]")
        console.print("[dim]Note: Complete history is still saved in file[/dim]")
        return True
    
    elif query_lower == "/summary":
        summary = agent.get_conversation_summary()
        if summary:
            console.print(Panel.fit(
                summary,
                title="[ Current Session Summary ]",
                border_style="green",
            ))
        else:
            console.print("[yellow]No conversation summary in current session.[/yellow]")
        return True
    
    elif query_lower == "/full_summary":
        # 获取完整保存的摘要
        from context.context import get_global_context
        global_context = get_global_context()
        if global_context:
            full_summary = global_context.get_full_saved_summary()
            if full_summary:
                console.print(Panel.fit(
                    full_summary,
                    title="[ Complete Saved Summary ]",
                    border_style="blue",
                ))
            else:
                console.print("[yellow]No saved summary found.[/yellow]")
        else:
            console.print("[red]❌ Global context not available.[/red]")
        return True
    
    elif query_lower.startswith("/export "):
        filename = query[8:].strip()
        if filename:
            try:
                agent.export_conversation(filename)
                console.print(f"[green]✅ Conversation exported to {filename}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Export failed: {e}[/red]")
        else:
            console.print("[red]❌ Please provide a filename[/red]")
        return True
    
    elif query_lower == "/session":
        session_info = agent.get_session_info()
        console.print(Panel.fit(
            f"Agent: {session_info['agent_name']}\n"
            f"Conversations: {session_info['conversation_count']}\n"
            f"SketchPad items: {session_info['sketch_pad_stats']['total_items']}\n"
            f"Memory usage: {session_info['sketch_pad_stats']['memory_usage_percent']:.1f}%",
            title="[ Session Info ]",
            border_style="blue",
        ))
        return True
    
    elif query_lower.startswith("/search "):
        search_query = query[8:].strip()
        if search_query:
            results = agent.search_conversation(search_query, 3)
            if results:
                console.print(Panel.fit(
                    "\n---\n".join([f"[{msg['role']}]: {msg['content']}" for msg in results]),
                    title=f"[ Current Session Search: '{search_query}' ]",
                    border_style="magenta",
                ))
            else:
                console.print(f"[yellow]No results found in current session for '{search_query}'[/yellow]")
        else:
            console.print("[red]❌ Please provide a search query[/red]")
        return True
    
    elif query_lower.startswith("/search_all "):
        search_query = query[12:].strip()
        if search_query:
            # 搜索完整保存的历史记录
            from context.context import get_global_context
            global_context = get_global_context()
            if global_context:
                results = global_context.search_full_history(search_query, 5)
                if results:
                    console.print(Panel.fit(
                        "\n---\n".join([f"[{msg['role']}]: {msg['content']}" for msg in results]),
                        title=f"[ Complete History Search: '{search_query}' ]",
                        border_style="magenta",
                    ))
                else:
                    console.print(f"[yellow]No results found in complete history for '{search_query}'[/yellow]")
            else:
                console.print("[red]❌ Global context not available.[/red]")
        else:
            console.print("[red]❌ Please provide a search query[/red]")
        return True
    
    elif query_lower == "/pad":
        items = agent.sketch_pad.list_all(include_details=True)
        if items:
            content = "\n".join([
                f"• {item['key']}: {item.get('summary', 'No summary')[:50]}..." 
                for item in items[:10]
            ])
            if len(items) > 10:
                content += f"\n... and {len(items) - 10} more items"
            console.print(Panel.fit(
                content,
                title="[ SketchPad Contents ]",
                border_style="cyan",
            ))
        else:
            console.print("[yellow]SketchPad is empty.[/yellow]")
        return True
    
    elif query_lower == "/pad_stats":
        stats = agent.get_sketch_pad_stats()
        content = f"Total items: {stats['total_items']}\n"
        content += f"Memory usage: {stats['memory_usage_percent']:.1f}%\n"
        content += f"Items with summary: {stats['items_with_summary']}\n"
        content += f"Total accesses: {stats['total_accesses']}"
        if stats['popular_tags']:
            content += f"\nPopular tags: {', '.join(list(stats['popular_tags'].keys())[:5])}"
        console.print(Panel.fit(
            content,
            title="[ SketchPad Statistics ]",
            border_style="cyan",
        ))
        return True
    
    elif query_lower == "/pad_clear":
        agent.clear_sketch_pad()
        console.print("[green]✅ SketchPad cleared![/green]")
        return True
    
    elif query_lower.startswith("/pad_search "):
        search_query = query[12:].strip()
        if search_query:
            results = agent.search_sketch_pad(search_query, 5)
            if results:
                content = "\n".join([
                    f"• {item['key']}: {item.get('summary', 'No summary')[:50]}..." 
                    for item in results
                ])
                console.print(Panel.fit(
                    content,
                    title=f"[ SketchPad Search: '{search_query}' ]",
                    border_style="magenta",
                ))
            else:
                console.print(f"[yellow]No SketchPad items found for '{search_query}'[/yellow]")
        else:
            console.print("[red]❌ Please provide a search query[/red]")
        return True
    
    elif query_lower.startswith("/pad_store "):
        # 解析 key 和 value
        parts = query[11:].strip().split(' ', 1)
        if len(parts) >= 2:
            key, value = parts
            try:
                # 使用异步函数存储
                async def _store():
                    return await agent.store_in_sketch_pad(value, key)
                
                # 在同步环境中运行异步函数
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _store())
                    actual_key = future.result(timeout=30)
                
                console.print(f"[green]✅ Stored in SketchPad with key: {actual_key}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed to store: {e}[/red]")
        else:
            console.print("[red]❌ Usage: /pad_store <key> <value>[/red]")
        return True
    
    elif query_lower.startswith("/pad_get "):
        key = query[9:].strip()
        if key:
            value = agent.get_from_sketch_pad(key)
            if value is not None:
                # 截断长内容
                display_value = str(value)
                if len(display_value) > 500:
                    display_value = display_value[:500] + "..."
                
                console.print(Panel.fit(
                    display_value,
                    title=f"[ SketchPad Item: {key} ]",
                    border_style="green",
                ))
            else:
                console.print(f"[yellow]Key '{key}' not found in SketchPad[/yellow]")
        else:
            console.print("[red]❌ Usage: /pad_get <key>[/red]")
        return True
    
    elif query_lower.startswith("/pad_delete "):
        key = query[12:].strip()
        if key:
            success = agent.sketch_pad.delete(key)
            if success:
                console.print(f"[green]✅ Deleted key '{key}' from SketchPad[/green]")
            else:
                console.print(f"[yellow]Key '{key}' not found in SketchPad[/yellow]")
        else:
            console.print("[red]❌ Usage: /pad_delete <key>[/red]")
        return True
    
    elif query_lower.startswith("/pad_update "):
        # 解析 key 和 new_value
        parts = query[12:].strip().split(' ', 1)
        if len(parts) >= 2:
            key, new_value = parts
            # 先检查key是否存在
            if agent.sketch_pad.backend.exists(key):
                try:
                    # 删除旧的，添加新的（保持相同key）
                    agent.sketch_pad.delete(key)
                    
                    async def _update():
                        return await agent.store_in_sketch_pad(new_value, key)
                    
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _update())
                        actual_key = future.result(timeout=30)
                    
                    console.print(f"[green]✅ Updated key '{key}' in SketchPad[/green]")
                except Exception as e:
                    console.print(f"[red]❌ Failed to update: {e}[/red]")
            else:
                console.print(f"[yellow]Key '{key}' not found. Use /pad_store to create new items.[/yellow]")
        else:
            console.print("[red]❌ Usage: /pad_update <key> <new_value>[/red]")
        return True
    
    elif query_lower.startswith("/pad_tag "):
        # 解析 key 和 tags
        parts = query[9:].strip().split(' ', 1)
        if len(parts) >= 2:
            key, tags_str = parts
            # 获取现有项目
            item = agent.sketch_pad.get_item(key)
            if item:
                try:
                    # 解析新标签
                    new_tags = set(tag.strip() for tag in tags_str.split(','))
                    # 合并现有标签
                    combined_tags = item.tags.union(new_tags)
                    
                    # 重新存储（更新标签）
                    agent.sketch_pad.delete(key)
                    
                    async def _retag():
                        return await agent.store_in_sketch_pad(item.value, key, tags=list(combined_tags))
                    
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _retag())
                        actual_key = future.result(timeout=30)
                    
                    console.print(f"[green]✅ Added tags to '{key}': {', '.join(new_tags)}[/green]")
                    console.print(f"[dim]All tags: {', '.join(combined_tags)}[/dim]")
                except Exception as e:
                    console.print(f"[red]❌ Failed to add tags: {e}[/red]")
            else:
                console.print(f"[yellow]Key '{key}' not found in SketchPad[/yellow]")
        else:
            console.print("[red]❌ Usage: /pad_tag <key> <tag1,tag2,tag3>[/red]")
        return True

    return False


async def main():
    agent = setup_agent()
    if not agent:
        return

    console.print(
        Panel.fit(
            "[bold green]Ready![/bold green] This is a fresh conversation session.\n"
            "[dim]Previous conversations are saved but not loaded automatically.[/dim]\n"
            "[yellow]Create a new line and press [bold]Ctrl+D[/bold] (or [bold]Ctrl+Z[/bold] on Windows) to submit your query.[/yellow]\n"
            "[cyan]Input 'quit' to exit the program.[/cyan]\n"
            "[dim]Type '/help' for special commands, '/full_history' to view saved history.[/dim]",
            title="[ CAD Assistant ]",
            border_style="blue",
        )
    )

    while True:
        try:
            query = get_input()
            if not query:
                continue

            if query.lower() == "quit":
                break

            # 处理特殊命令
            if handle_special_commands(agent, query):
                continue

            try:
                console.print("===========================")
                console.print("[🤖] >>> ", end="")

                async for chunk in agent.run(query):
                    if chunk.strip():
                        for char in chunk:
                            if char == "\r":
                                char = "\n"
                            if char.strip() == "" and char != "\n" and char != " ":
                                continue
                            console.print(char, end="")
                            sleep(0.01)
                console.print("\n===========================")
            except Exception as e:
                console.print(f"\nError: {e}")

        except KeyboardInterrupt:
            console.print("\nType 'quit' to exit.")
            continue
        except Exception as e:
            console.print(f"Error: {e}")
            continue


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
