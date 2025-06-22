import sys
from time import sleep
from agent.BaseAgent import BaseAgent
from config.config import get_config
from tools.tools import (
    cad_query_code_generation,
    pythonocc_code_generation,
    make_user_query_more_detailed,
    execute_command,
    interactive_terminal,
    file_operations,
)

from rich.console import Console
from rich.panel import Panel


console = Console()


def setup_agent():
    try:
        config = get_config()
        toolkit = [
            cad_query_code_generation,
            pythonocc_code_generation,
            make_user_query_more_detailed,
            execute_command,
            interactive_terminal,
            file_operations,
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


def main():
    agent = setup_agent()
    if not agent:
        return

    console.print(
        Panel.fit(
            "[bold green]Ready![/bold green] Enter your queries below.\n"
            "[yellow]Create a new line and press [bold]Ctrl+D[/bold] (or [bold]Ctrl+Z[/bold] on Windows) to submit your query.[/yellow]\n"
            "[cyan]Input 'quit' to exit the program.[/cyan]",
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

            try:
                console.print("===========================")
                console.print("[🤖] >>> ", end="")

                for chunk in agent.run(query):
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
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
