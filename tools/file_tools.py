"""
文件操作工具模块
"""

from SimpleLLMFunc import tool
from typing import Optional
import os
import re
from .common import print_tool_output, safe_asyncio_run
from context.conversation_manager import get_current_sketch_pad


def _sync_sketchpad_copies(file_path: str, sketch_pad) -> None:
    """
    同步更新SketchPad中该文件的所有副本

    Args:
        file_path: 文件路径
        sketch_pad: SketchPad实例
    """
    try:
        # 标准化文件路径
        normalized_path = os.path.abspath(file_path)

        # 构建可能的文件路径标签
        possible_tags = {
            f"file_path:{file_path}",
            f"file_path:{normalized_path}",
            f"source_file:{file_path}",
            f"source_file:{normalized_path}",
        }

        # 搜索可能相关的SketchPad条目
        updated_count = 0
        for tag in possible_tags:
            try:
                results = sketch_pad.search_by_tags({tag})
            except Exception as e:
                print_tool_output("⚠️ 标签搜索失败", f"Tag: {tag}, Error: {e}")
                continue

            if results:
                # 读取最新的文件内容
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        latest_content = f.read()
                except Exception:
                    continue

                # 更新找到的副本
                for key, old_item in results:
                    if old_item and str(old_item.value) != latest_content:
                        try:
                            async def _store_updated_content():
                                return await sketch_pad.set_item(
                                    key=key,
                                    value=latest_content,
                                    ttl=None,
                                    summary=f"Updated content from {file_path}",
                                    tags=old_item.tags,
                                )

                            _ = safe_asyncio_run(_store_updated_content)
                            updated_count += 1
                        except Exception as e:
                            print_tool_output("⚠️ 副本更新失败", f"Key: {key}, Error: {e}")

        if updated_count > 0:
            print_tool_output(
                "🔄 SketchPad副本已同步",
                f"已更新 {updated_count} 个相关副本",
            )

    except Exception as e:
        print_tool_output("⚠️ 副本同步失败", f"Error: {e}")


@tool(
    name="write_file",
    description="Perform file writing operations: overwrite, modify, insert, or append content. Supports SketchPad key for content input and automatically syncs changes with existing SketchPad copies.",
)
def write_file(
    file_path: str,
    operation: str,
    content: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Perform file writing operations with SketchPad integration.

    Args:
        file_path: Path to the file to be modified.
        operation: One of "modify", "insert", "append", "overwrite", modify with line numbers and sketch key is the recommanded way.
        content: Content for the operation OR a SketchPad key (format: "key:sketch_key").
        start_line: Start line (1-based). Required for "modify" and "insert".
        end_line: End line (1-based, inclusive). Required for "modify".

    Returns:
        str: A confirmation message of the operation.
    """

    sync_sketchpad: bool = True

    def print_error(msg: str):
        print_tool_output("❌ 文件写入错误", msg)
        return f"Error: {msg}"

    if operation not in {"modify", "insert", "append", "overwrite"}:
        return print_error(f"未知或不支持的写入操作类型 '{operation}'")

    sketch_pad = get_current_sketch_pad()
    if sketch_pad is None:
        print_tool_output("⚠️ 警告", "无活动conversation上下文，将跳过SketchPad集成功能")

    # 处理content参数中的SketchPad key
    actual_content = content
    if content.startswith("key:") and sketch_pad is not None:
        sketch_key = content[4:]
        pad_content = sketch_pad.get_value(sketch_key)
        if pad_content is not None:
            actual_content = str(pad_content)
            print_tool_output(
                title="📋 从SketchPad获取内容",
                content=f"Key: {sketch_key}\n内容长度: {len(actual_content)} 字符",
            )
        else:
            print_tool_output(
                title="⚠️ SketchPad Key未找到",
                content=f"Key: {sketch_key} 不存在，将使用原始内容",
            )
            actual_content = content
            actual_content = content

    if actual_content is None:
        return print_error("Content must be provided for write operations.")

    # 显示操作开始信息
    op_details = (
        f"File: {file_path}\n"
        f"Operation: {operation}\n"
        f"Content length: {len(actual_content)} chars"
    )
    if start_line:
        op_details += f"\nStart line: {start_line}"
    if end_line:
        op_details += f"\nEnd line: {end_line}"
    print_tool_output("📂 文件写入操作开始", op_details)

    # 获取目录路径并创建
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)

    # 文件不存在则自动创建
    if not os.path.isfile(file_path):
        open(file_path, "a").close()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        total_lines = len(lines)

        result_msg = ""

        if operation == "overwrite":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(actual_content)
            result_msg = "File overwritten successfully."

        elif operation == "append":
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(actual_content)
            result_msg = "Content appended to file."

        elif operation == "insert":
            if start_line is None or not (1 <= start_line <= total_lines + 1):
                return print_error(
                    f"Invalid start_line for insert. Must be in [1, {total_lines+1}]."
                )
            if not actual_content.endswith("\n"):
                actual_content += "\n"
            new_lines = actual_content.splitlines(keepends=True)
            idx = start_line - 1
            lines = lines[:idx] + new_lines + lines[idx:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            result_msg = f"Inserted at line {start_line}."

        elif operation == "modify":
            if start_line is None or end_line is None:
                return print_error("start_line and end_line are required for modify.")
            if not (1 <= start_line <= end_line <= total_lines):
                return print_error(f"Modify range must be within [1, {total_lines}].")
            if not actual_content.endswith("\n"):
                actual_content += "\n"
            new_lines = actual_content.splitlines(keepends=True)
            lines = lines[: start_line - 1] + new_lines + lines[end_line:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            result_msg = f"Lines {start_line}-{end_line} modified successfully."

        if sync_sketchpad and sketch_pad is not None:
            _sync_sketchpad_copies(file_path, sketch_pad)

        print_tool_output("✅ 文件写入成功", result_msg)
        return result_msg

    except Exception as e:
        return print_error(str(e))


@tool(
    name="read_or_search_file",
    description="Perform file reading or searching operations: read file content (all or specific lines) or search with regex. Supports SketchPad key for search content and stores results back to SketchPad.",
)
def read_or_search_file(
    operation: str,
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    pattern: Optional[str] = None,
    context_lines: int = 2,
) -> str:
    """
    Read or search in files with SketchPad integration.

    Args:
        operation: One of "read", "search".
        file_path: Path to file. Required for "read" and file-based "search".
        content: Content to search in, can be a SketchPad key (format: "key:sketch_key"). Used only in "search" operation.
        start_line: Start line for "read" (1-based).
        end_line: End line for "read" (1-based, inclusive).
        pattern: Regular expression for "search".
        context_lines: Number of context lines for "search" results.

    Returns:
        str: Result of the operation, potentially with a SketchPad key.
    """

    store_result: bool = True
    include_line_numbers: bool = True

    def print_error(msg: str):
        print_tool_output("❌ 文件操作错误", msg)
        return f"Error: {msg}"

    if operation not in {"read", "search"}:
        return print_error(f"未知或不支持的读取/搜索操作 '{operation}'")

    sketch_pad = get_current_sketch_pad()
    if sketch_pad is None:
        print_tool_output("⚠️ 警告", "无活动conversation上下文，将跳过SketchPad集成功能")
        
    search_content_from_arg = None

    # Validate arguments
    if operation == "read" and not file_path:
        return print_error("file_path is required for 'read' operation.")
    if operation == "search" and not pattern:
        return print_error("pattern is required for 'search' operation.")
    if operation == "search" and not file_path and not content:
        return print_error(
            "Either file_path or content must be provided for 'search' operation."
        )

    # Handle content from SketchPad for search
    if operation == "search" and content:
        if content.startswith("key:") and sketch_pad is not None:
            sketch_key = content[4:]
            pad_content = sketch_pad.get_value(sketch_key)
            if pad_content is not None:
                search_content_from_arg = str(pad_content)
                print_tool_output(
                    title="📋 从SketchPad获取搜索内容",
                    content=f"Key: {sketch_key}\n内容长度: {len(search_content_from_arg)} 字符",
                )
            else:
                print_tool_output(
                    title="⚠️ SketchPad Key未找到",
                    content=f"Key: {sketch_key} 不存在，将忽略content参数",
                )
        else:
            search_content_from_arg = content

    # Display operation start info
    op_details_list = [f"Operation: {operation}"]
    if file_path:
        op_details_list.append(f"File: {file_path}")
    if operation == "read":
        if start_line:
            op_details_list.append(f"Start line: {start_line}")
        if end_line:
            op_details_list.append(f"End line: {end_line}")
    if operation == "search":
        if pattern:
            op_details_list.append(f"Pattern: {pattern}")
        if search_content_from_arg:
            op_details_list.append("Searching in: Provided content")

    print_tool_output(f"📂 文件{operation}操作开始", "\n".join(op_details_list))

    # Check for file existence
    if file_path and not os.path.isfile(file_path):
        return print_error(f"File not found: {file_path}")

    try:
        lines = []
        source_description = ""
        if operation == "search" and search_content_from_arg:
            lines = search_content_from_arg.splitlines(keepends=True)
            source_description = "provided content"
            if content and content.startswith("key:"):
                source_description = f"SketchPad content (key: {content[4:]})"
        elif file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            source_description = f"file: {file_path}"

        total_lines = len(lines)

        if operation == "read":
            s = start_line - 1 if start_line else 0
            e = end_line if end_line else total_lines
            if s < 0 or e > total_lines or s >= e:
                return print_error("Invalid read range.")

            selected = lines[s:e]
            read_content = (
                "".join(f"{i+1}: {line}" for i, line in enumerate(selected, s))
                if include_line_numbers
                else "".join(selected)
            )

            if store_result and read_content.strip() and file_path and sketch_pad is not None:
                import uuid

                content_key = f"file_{uuid.uuid4().hex[:8]}"

                async def _store_read_content():
                    tags = {
                        "file_content",
                        "read_result", 
                        "text",
                        f"file_path:{file_path}",
                        f"source_file:{os.path.abspath(file_path)}",
                    }
                    return await sketch_pad.set_item(
                        key=content_key,
                        value=read_content.strip(),
                        ttl=None,
                        summary=f"Content from {file_path} (lines {s+1}-{e})",
                        tags=tags,
                    )

                try:
                    _ = safe_asyncio_run(_store_read_content)
                    print_tool_output(
                        title="💾 文件内容已存储到SketchPad",
                        content=f"Key: {content_key}\n内容长度: {len(read_content)} 字符",
                    )
                    return (
                        f"文件读取完成并存储到SketchPad:\n\n"
                        f"🔑 SketchPad Key: {content_key}\n\n"
                        f"📁 文件: {file_path}\n"
                        f"📏 范围: 第{s+1}行到第{e}行\n"
                        f"📄 内容:\n{read_content}\n"
                        f'💡 提示: 您可以使用key "{content_key}" 引用此内容'
                    )
                except Exception as e:
                    print_tool_output(
                        "❌ 存储失败", f"Failed to store read content: {e}"
                    )
            return read_content

        elif operation == "search":
            if not pattern:
                return print_error("Pattern is required for search operation.")
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return print_error(f"Invalid regex pattern: {e}")

            matches = [i + 1 for i, line in enumerate(lines) if regex.search(line)]

            if not matches:
                result = (
                    f"No matches found for pattern '{pattern}' in {source_description}"
                )
                print_tool_output("🔍 搜索结果", "未找到匹配项")
                return result

            # Build search result string
            search_result_str = f"Found {len(matches)} match(es) for pattern '{pattern}' in {source_description}:\n\n"
            all_context_lines = set()
            for match_line in matches:
                for i in range(
                    max(1, match_line - context_lines),
                    min(total_lines, match_line + context_lines) + 1,
                ):
                    all_context_lines.add(i)

            # Simplified context block generation
            for line_num in sorted(all_context_lines):
                line_content = lines[line_num - 1].rstrip()
                prefix = ">>>" if line_num in matches else "   "
                search_result_str += f"{prefix} {line_num:4d}: {line_content}\n"

            if store_result and sketch_pad is not None:
                import uuid

                search_key = f"search_{uuid.uuid4().hex[:8]}"

                async def _store_search_result():
                    return await sketch_pad.set_item(
                        key=search_key,
                        value=search_result_str,
                        ttl=None,
                        summary=f"Regex search for '{pattern}' in {source_description} ({len(matches)} matches)",
                        tags={"search_result", "regex_match", "text"},
                    )

                try:
                    _ = safe_asyncio_run(_store_search_result)
                    print_tool_output(
                        title="🔍 搜索结果已存储到SketchPad",
                        content=f"Key: {search_key}\n匹配数量: {len(matches)}",
                    )
                    return (
                        f"搜索完成并存储到SketchPad:\n\n"
                        f"🔑 SketchPad Key: {search_key}\n\n"
                        f"📄 结果:\n{search_result_str}"
                        f'💡 提示: 您可以使用key "{search_key}" 引用此结果'
                    )
                except Exception as e:
                    print_tool_output(
                        "❌ 存储失败", f"Failed to store search result: {e}"
                    )

            return search_result_str

        return print_error("Invalid operation state.")

    except Exception as e:
        return print_error(str(e))

