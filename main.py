"""
CAD Assistant

Usage:
    python main.py
"""

import asyncio
import sys
from time import sleep

from rich.console import Console
from rich.panel import Panel

from agent import get_agent, BaseAgent
from SimpleLLMFunc.llm_decorator.utils import extract_content_from_stream_response
from context.conversation_manager import get_conversation_manager

console = Console()


def setup_agent() -> BaseAgent | None:
    """
    设置代理
    """
    try:
        # 使用全局Agent单例
        agent = get_agent(
            model_name="cadagent",
        )
        console.print("CAD Assistant initialized successfully!")
        return agent
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return None


def get_input() -> str:
    """
    获取用户输入
    """
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
        console.print(
            Panel.fit(
                "[bold cyan]Special Commands:[/bold cyan]\n"
                "[yellow]/help[/yellow] - Show this help\n"
                "[yellow]/pad[/yellow] - Show SketchPad contents\n"
                "[yellow]/pad_search <query>[/yellow] - Search SketchPad\n"
                "[yellow]/pad_get <key>[/yellow] - Get content from SketchPad\n"
                "[yellow]quit[/yellow] - Exit"
            )
        )
        return True

    if query_lower == "/pad":
        try:
            # 使用BaseAgent的_get_sketch_pad_summary方法获取摘要
            summary = agent.get_sketch_pad_summary()
            if summary.strip():
                console.print(
                    Panel.fit(
                        summary,
                        title="[ SketchPad Contents ]",
                        border_style="cyan",
                    )
                )
            else:
                console.print("[yellow]SketchPad is empty.[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Unable to access SketchPad: {e}[/red]")
        return True

    if query_lower.startswith("/pad_search "):
        search_query = query[12:].strip()
        if search_query:
            try:
                results = agent.search_sketch_pad(search_query, 5)
                if results:
                    content = "\n".join(
                        [
                            f"• {item.get('key', 'Unknown')}: {item.get('snippet', 'No summary')[:50]}..."
                            for item in results
                        ]
                    )
                    console.print(
                        Panel.fit(
                            content,
                            title=f"[ SketchPad Search: '{search_query}' ]",
                            border_style="magenta",
                        )
                    )
                else:
                    console.print(
                        f"[yellow]No SketchPad items found for '{search_query}'[/yellow]"
                    )
            except Exception as e:
                console.print(f"[red]❌ Search failed: {e}[/red]")
        else:
            console.print("[red]❌ Please provide a search query[/red]")
        return True

    if query_lower.startswith("/pad_get "):
        key = query[9:].strip()
        if key:
            try:
                value = agent.get_from_sketch_pad(key)
                if value is not None:
                    # 截断长内容
                    display_value = str(value)
                    if len(display_value) > 500:
                        display_value = display_value[:500] + "..."

                    console.print(
                        Panel.fit(
                            display_value,
                            title=f"[ SketchPad Item: {key} ]",
                            border_style="green",
                        )
                    )
                else:
                    console.print(
                        f"[yellow]Key '{key}' not found in SketchPad[/yellow]"
                    )
            except Exception as e:
                console.print(f"[red]❌ Get failed: {e}[/red]")
        else:
            console.print("[red]❌ Usage: /pad_get <key>[/red]")
        return True

    return False


async def main() -> None:
    """
    主函数
    """
    agent = setup_agent()
    if not agent:
        return

    # 创建一个新的 conversation 上下文
    conversation_manager = get_conversation_manager()
    conversation = conversation_manager.create_conversation()

    console.print(
        Panel.fit(
            f"[bold green]Ready![/bold green] Started new conversation session: [yellow]{conversation.uuid[:8]}...[/yellow]\n"
            "[dim]Previous conversations are saved but not loaded automatically.[/dim]\n"
            "[yellow]Create a new line and press [bold]Ctrl+D[/bold] (or [bold]Ctrl+Z[/bold] on Windows) to submit your query.[/yellow]\n"
            "[cyan]Input 'quit' to exit the program.[/cyan]\n"
            "[dim]Type '/help' for special commands, '/full_history' to view saved history.[/dim]",
            title="[ CAD Assistant ]",
            border_style="blue",
        )
    )

    # 在 conversation 上下文中运行
    with conversation:
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
                        # 兼容 raw 包：提取文本 delta
                        try:
                            delta = extract_content_from_stream_response(chunk, "cli") or ""
                        except Exception:
                            delta = ""
                        if not delta:
                            continue
                        for char in delta:
                            if char == "\r":
                                char = "\n"
                            if char.strip() == "" and char not in ("\n", " "):
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

    # 保存 conversation
    conversation_manager.save_conversation(conversation.uuid)
    console.print(f"[dim]Conversation {conversation.uuid[:8]}... saved.[/dim]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
