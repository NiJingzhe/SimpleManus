from SimpleLLMFunc import tool
from .common import print_tool_output, safe_asyncio_run
from context.conversation_manager import get_current_sketch_pad


@tool(
    name="execute_command",
    description="Execute a system command in shell and return the output, with automatic SketchPad integration for command history and results.",
)
def execute_command(command: str, store_result: bool = True) -> str:
    """Execute a system command in shell and return the output.

    Args:
        command: The system command to execute, recommended commands are python <script path>
        store_result: Whether to automatically store command and result in SketchPad
    Returns:
        The command output with SketchPad key information
    """
    import subprocess
    import time

    try:
        # 显示命令执行开始
        print_tool_output("⚡ SYSTEM 执行命令", f"正在执行: {command}")

        start_time = time.time()
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=180
        )

        execution_time = time.time() - start_time

        # 准备存储内容
        execution_record = {
            "command": command,
            "return_code": result.returncode,
            "execution_time": execution_time,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 打印结果
        if result.returncode == 0:
            print_tool_output(
                "✅ SYSTEM 命令执行完成",
                f"命令执行成功！\nReturn code: {result.returncode}\nExecution time: {execution_time:.2f}s\nOutput length: {len(result.stdout)} chars",
            )

            output = result.stdout.strip()

            # 自动存储到SketchPad
            if store_result:
                import uuid

                async def _store_execution():
                    # 在闭包内部重新获取sketch_pad，确保是最新状态
                    sketch_pad = get_current_sketch_pad()
                    if sketch_pad is None:
                        raise ValueError("无活动conversation上下文，无法存储执行结果到SketchPad")
                    
                    # 生成自定义key
                    exec_key = f"exec_{uuid.uuid4().hex[:8]}"

                    # 存储执行记录
                    record_key = await sketch_pad.set_item(
                        key=exec_key,
                        value=str(execution_record),
                        ttl=None,
                        summary=None,
                        tags={"command_execution", "success", "history"},
                    )

                    # 如果有输出，单独存储输出
                    output_key = None
                    if output:
                        output_key = f"output_{uuid.uuid4().hex[:8]}"
                        await sketch_pad.set_item(
                            key=output_key,
                            value=output,
                            ttl=None,
                            summary=None,
                            tags={"command_output", "result"},
                        )

                    return record_key, output_key

                try:
                    record_key, output_key = safe_asyncio_run(_store_execution)

                    print_tool_output(
                        title="💾 命令执行记录已存储",
                        content=f"执行记录Key: {record_key}"
                        + (f"\n输出结果Key: {output_key}" if output_key else ""),
                    )

                    result_info = f"""命令执行成功并已存储到SketchPad:

🔑 执行记录Key: {record_key}
{f"📄 输出结果Key: {output_key}" if output_key else ""}

⚡ 命令: {command}
✅ 返回码: {result.returncode}
⏱️ 执行时间: {execution_time:.2f}s

📋 输出内容:
{output if output else "(无输出)"}

💡 提示: 您可以使用这些key在后续的操作中使用SketchPad相关的工具来查看历史命令"""

                    return result_info

                except ValueError as ve:
                    # 处理sketch_pad为None的情况
                    print_tool_output("⚠️ 警告", str(ve))
                    return f"{output}\n\n⚠️ 警告: {str(ve)}"
                except Exception as e:
                    print_tool_output("❌ 存储失败", f"Failed to store execution: {e}")
                    return output  # 返回原始输出

            return output
        else:
            print_tool_output(
                "❌ SYSTEM 命令执行失败",
                f"命令执行失败！\n错误信息: {result.stderr.strip()}",
            )

            error_output = (
                result.stderr.strip()
                + "\n\n超时可能是程序等待input导致的，请使用测试代码来进行测试。"
            )

            # 存储失败记录
            if store_result:
                import uuid

                async def _store_error():
                    # 在闭包内部重新获取sketch_pad，确保是最新状态
                    sketch_pad = get_current_sketch_pad()
                    if sketch_pad is None:
                        raise ValueError("无活动conversation上下文，无法存储错误记录到SketchPad")
                    
                    error_key = f"error_{uuid.uuid4().hex[:8]}"
                    return await sketch_pad.set_item(
                        key=error_key,
                        value=str(execution_record),
                        ttl=None,
                        summary=None,
                        tags={"command_execution", "error", "failed"},
                    )

                try:
                    error_key = safe_asyncio_run(_store_error)

                    print_tool_output(
                        title="💾 错误记录已存储", content=f"错误记录Key: {error_key}"
                    )

                    return f"""命令执行失败，错误记录已存储:

🔑 错误记录Key: {error_key}

❌ 错误信息:
{error_output}

💡 提示: 您可以使用key "{error_key}" 查看详细的执行记录"""

                except ValueError as ve:
                    # 处理sketch_pad为None的情况
                    print_tool_output("⚠️ 警告", str(ve))
                except Exception as e:
                    print_tool_output("❌ 存储失败", f"Failed to store error: {e}")

            return error_output

    except Exception as e:
        print_tool_output("💥 SYSTEM 错误", f"执行命令失败: {str(e)}")
        error_msg = f"执行命令失败: {str(e)}"

        # 存储异常记录
        if store_result:
            try:
                import uuid

                async def _store_exception():
                    # 在闭包内部重新获取sketch_pad，确保是最新状态
                    sketch_pad = get_current_sketch_pad()
                    if sketch_pad is None:
                        raise ValueError("无活动conversation上下文，无法存储异常记录到SketchPad")
                    
                    exception_key = f"exception_{uuid.uuid4().hex[:8]}"
                    return await sketch_pad.set_item(
                        key=exception_key,
                        value=f"Command: {command}\nException: {str(e)}\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                        ttl=None,
                        summary=f"Command execution exception: {command}",
                        tags={"command_execution", "exception", "error"},
                    )

                exception_key = safe_asyncio_run(_store_exception)
                print_tool_output(
                    title="💾 异常记录已存储", content=f"异常记录Key: {exception_key}"
                )

                return f"""命令执行异常，记录已存储:

🔑 异常记录Key: {exception_key}

💥 异常信息:
{error_msg}"""

            except ValueError as ve:
                # 处理sketch_pad为None的情况
                print_tool_output("⚠️ 警告", str(ve))
            except Exception:
                pass  # 如果存储也失败，只返回原始错误

        return error_msg
