"""
文件操作工具模块
"""
from SimpleLLMFunc import tool
from typing import Optional
import os
from rich.table import Table
from .common import (
    print_tool_output, safe_asyncio_run, get_global_sketch_pad
)


@tool(
    name="file_operations",
    description="Perform line-level file operations with SketchPad integration: read (all or specific lines), modify, insert, append, or overwrite. Supports SketchPad key input/output.",
)
def file_operations(
    file_path: str,
    operation: str,
    content: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    include_line_numbers: bool = False,
    store_result: bool = True,
) -> str:  # type: ignore
    """
    File operations with line-level granularity and SketchPad integration.
    Also prints detailed console instructions with content boundaries.

    Args:
        file_path: Path to file.
        operation: One of "read", "modify", "insert", "append", "overwrite".
        content: Content for write/modify OR SketchPad key (format: "key:sketch_key"). Optional for read.
        start_line: Start line (1-based). Required for modify/insert/read.
        end_line: End line (1-based, inclusive). Required for modify/read.
        include_line_numbers: Whether to include line numbers in "read" output.
        store_result: Whether to store read results in SketchPad automatically.

    Returns:
        str: Result of the operation or file content with SketchPad key info.
    """

    def print_action(header: str, content_info: Optional[str] = None):
        """增强的操作显示函数"""
        if content_info:
            print_tool_output(f"📁 {header}", content_info)
        else:
            print_tool_output(f"📁 {header}", "操作执行中...")

    def print_error(msg: str):
        print_tool_output("❌ 文件操作错误", msg)
        return f"Error: {msg}"

    if operation not in {"read", "modify", "insert", "append", "overwrite"}:
        return print_error(f"未知操作类型 '{operation}'")

    sketch_pad = get_global_sketch_pad()
    
    # 处理content参数中的SketchPad key
    actual_content = content
    if operation in {"modify", "insert", "append", "overwrite"} and content:
        if content.startswith("key:"):
            # 从SketchPad获取内容
            sketch_key = content[4:]  # 去掉 "key:" 前缀
            pad_content = sketch_pad.retrieve(sketch_key)
            if pad_content is not None:
                actual_content = str(pad_content)
                print_tool_output(
                    title="📋 从SketchPad获取内容",
                    content=f"Key: {sketch_key}\n内容长度: {len(actual_content)} 字符"
                )
            else:
                print_tool_output(
                    title="⚠️ SketchPad Key未找到",
                    content=f"Key: {sketch_key} 不存在，将使用原始内容"
                )
                actual_content = content  # 使用原始内容
        else:
            # 直接使用提供的内容
            actual_content = content

    # 显示操作开始信息
    op_table = Table.grid()
    op_table.add_column(style="cyan", justify="right")
    op_table.add_column()
    op_table.add_row("File:", f"[bold white]{file_path}[/bold white]")
    op_table.add_row("Operation:", f"[bold yellow]{operation}[/bold yellow]")
    if start_line:
        op_table.add_row("Start line:", str(start_line))
    if end_line:
        op_table.add_row("End line:", str(end_line))
    if actual_content:
        op_table.add_row("Content length:", f"{len(actual_content)} chars")

    print_tool_output("📂 文件操作开始", f"正在执行 {operation} 操作")

    # 获取目录路径
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)

    # 处理写操作（文件不存在则自动创建）
    if operation in {"overwrite", "append", "insert", "modify"} and not os.path.isfile(
        file_path
    ):
        open(file_path, "a").close()  # 创建空文件

    # 处理读操作（文件不存在时报错）
    if operation == "read" and not os.path.isfile(file_path):
        return print_error(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total_lines = len(lines)

        if operation == "read":
            s = start_line - 1 if start_line else 0
            e = end_line if end_line else total_lines
            if s < 0 or e > total_lines or s >= e:
                return print_error("Invalid read range.")

            print_action(f"Reading lines {s+1} to {e} from file: {file_path}")
            selected = lines[s:e]
            read_content = ""
            if include_line_numbers:
                read_content = "".join([f"{i+1}: {line}" for i, line in enumerate(selected, s)])
            else:
                read_content = "".join(selected)
            
            # 自动存储读取内容到SketchPad
            if store_result and read_content.strip():
                import uuid
                content_key = f"file_{uuid.uuid4().hex[:8]}"
                
                async def _store_read_content():
                    return await sketch_pad.store(
                        value=read_content.strip(),
                        key=content_key,
                        tags={"file_content", "read_result", "text"},
                        auto_summarize=True,
                        summary=f"Content from {file_path} (lines {s+1}-{e})"
                    )
                
                try:
                    actual_key = safe_asyncio_run(_store_read_content)
                    
                    print_tool_output(
                        title="💾 文件内容已存储到SketchPad",
                        content=f"Key: {content_key}\n内容长度: {len(read_content)} 字符"
                    )
                    
                    return f"""文件读取完成并存储到SketchPad:

🔑 SketchPad Key: {content_key}

📁 文件: {file_path}
📏 范围: 第{s+1}行到第{e}行
📄 内容长度: {len(read_content)} 字符

📋 文件内容:
{read_content}

💡 提示: 您可以使用key "{content_key}" 在后续操作中引用此文件内容"""
                
                except Exception as e:
                    print_tool_output("❌ 存储失败", f"Failed to store read content: {e}")
                    return read_content
            
            return read_content

        elif operation == "overwrite":
            print_action(f"Overwriting entire file: {file_path}", actual_content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(actual_content or "")
            return "File overwritten successfully."

        elif operation == "append":
            print_action(f"Appending content to file: {file_path}", actual_content)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(actual_content or "")
            return "Content appended to file."

        elif operation == "insert":
            if actual_content is None:
                return print_error("You must provide content to insert.")
            if start_line is None or not (1 <= start_line <= total_lines + 1):
                return print_error(
                    f"Invalid start_line for insert. Must be in [1, {total_lines+1}]."
                )
            print_action(
                f"Inserting at line {start_line} in file: {file_path}", actual_content
            )
            new_lines = actual_content.splitlines(keepends=True)
            idx = start_line - 1
            lines = lines[:idx] + new_lines + lines[idx:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return f"Inserted at line {start_line}."

        elif operation == "modify":
            if actual_content is None:
                return print_error("You must provide content to modify.")
            if start_line is None or end_line is None:
                return print_error("start_line and end_line are required for modify.")
            if not (1 <= start_line <= end_line <= total_lines):
                return print_error(f"Modify range must be within [1, {total_lines}].")
            print_action(
                f"Modifying lines {start_line}-{end_line} in file: {file_path}", actual_content
            )
            new_lines = actual_content.splitlines(keepends=True)
            lines = lines[: start_line - 1] + new_lines + lines[end_line:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return f"Lines {start_line}-{end_line} modified successfully."

    except Exception as e:
        return print_error(str(e))
