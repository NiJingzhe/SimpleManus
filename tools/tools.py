from SimpleLLMFunc import llm_function, tool
from typing import List, Optional
from config.config import get_config
import os
import subprocess
import time
import select
from rich.table import Table
from rich.status import Status


# 创建一个全局的控制台实例，使用stderr避免与主程序输出冲突
# tool_console = Console(stderr=True, force_terminal=True)


def print_tool_output(title: str, content: str, style: str = "cyan"):
    """简化版工具输出函数，使用朴素print和分割线"""
    print("\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(f"{title}")
    print(content)
    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")


@tool(
    name="cad_query_code_generation",
    description="Generate CAD modeling code using cad query framework.",
)
@llm_function(llm_interface=get_config().CODE_INTERFACE, toolkit=[], timeout=600)
def cad_query_code_generation(user_query: str, pay_attention: Optional[str]) -> str:  # type: ignore[override]
    """Generate CAD modeling code using cad query framework.
    Or generate fix code snippits according to provided context and error information.

    You should generate code with detailed comments explaining each step.
    And finally you should export the model to a STEP file in code.

    you are supposed to generate complete and executable code that can be run in a Python environment with the cadquery library installed.
    The generated code should be contained within a Python code block in your response.
    The code should include the necessary imports, define a function that creates the CAD model, and export the model to a STEP file, file name should be related with the model.
    Make good use of the cadquery library and parameterize the model as much as possible to allow for easy modifications.

    Please pay more attention to the workplane selection, and the order of operations.

    for example:

    ## 1. When you are required to generate a complete CAD Query Code:

    ```python
    # parameter definitions
    p_outerWidth = 100.0  # Outer width of box enclosure
    p_outerLength = 150.0  # Outer length of box enclosure
    p_outerHeight = 50.0  # Outer height of box enclosure

    p_thickness = 3.0  # Thickness of the box walls
    p_sideRadius = 10.0  # Radius for the curves around the sides of the box
    p_topAndBottomRadius = (
        2.0  # Radius for the curves on the top and bottom edges of the box
    )

    p_screwpostInset = 12.0  # How far in from the edges the screw posts should be place.
    p_screwpostID = 4.0  # Inner Diameter of the screw post holes, should be roughly screw diameter not including threads
    p_screwpostOD = 10.0  # Outer Diameter of the screw posts.\nDetermines overall thickness of the posts

    p_boreDiameter = 8.0  # Diameter of the counterbore hole, if any
    p_boreDepth = 1.0  # Depth of the counterbore hole, if
    p_countersinkDiameter = 0.0  # Outer diameter of countersink. Should roughly match the outer diameter of the screw head
    p_countersinkAngle = 90.0  # Countersink angle (complete angle between opposite sides, not from center to one side)
    p_flipLid = True  # Whether to place the lid with the top facing down or not.
    p_lipHeight = 1.0  # Height of lip on the underside of the lid.\nSits inside the box body for a snug fit.

    # outer shell
    oshell = (
        cq.Workplane("XY")
        .rect(p_outerWidth, p_outerLength)
        .extrude(p_outerHeight + p_lipHeight)
    )

    # weird geometry happens if we make the fillets in the wrong order
    if p_sideRadius > p_topAndBottomRadius:
        oshell = oshell.edges("|Z").fillet(p_sideRadius)
        oshell = oshell.edges("#Z").fillet(p_topAndBottomRadius)
    else:
        oshell = oshell.edges("#Z").fillet(p_topAndBottomRadius)
        oshell = oshell.edges("|Z").fillet(p_sideRadius)

    # inner shell
    ishell = (
        oshell.faces("<Z")
        .workplane(p_thickness, True)
        .rect((p_outerWidth - 2.0 * p_thickness), (p_outerLength - 2.0 * p_thickness))
        .extrude(
            (p_outerHeight - 2.0 * p_thickness), False
        )  # set combine false to produce just the new boss
    )
    ishell = ishell.edges("|Z").fillet(p_sideRadius - p_thickness)

    # make the box outer box
    box = oshell.cut(ishell)

    # make the screw posts
    POSTWIDTH = p_outerWidth - 2.0 * p_screwpostInset
    POSTLENGTH = p_outerLength - 2.0 * p_screwpostInset

    box = (
        box.faces(">Z")
        .workplane(-p_thickness)
        .rect(POSTWIDTH, POSTLENGTH, forConstruction=True)
        .vertices()
        .circle(p_screwpostOD / 2.0)
        .circle(p_screwpostID / 2.0)
        .extrude(-1.0 * (p_outerHeight + p_lipHeight - p_thickness), True)
    )

    # split lid into top and bottom parts
    (lid, bottom) = (
        box.faces(">Z")
        .workplane(-p_thickness - p_lipHeight)
        .split(keepTop=True, keepBottom=True)
        .all()
    )  # splits into two solids

    # translate the lid, and subtract the bottom from it to produce the lid inset
    lowerLid = lid.translate((0, 0, -p_lipHeight))
    cutlip = lowerLid.cut(bottom).translate(
        (p_outerWidth + p_thickness, 0, p_thickness - p_outerHeight + p_lipHeight)
    )

    # compute centers for screw holes
    topOfLidCenters = (
        cutlip.faces(">Z")
        .workplane(centerOption="CenterOfMass")
        .rect(POSTWIDTH, POSTLENGTH, forConstruction=True)
        .vertices()
    )

    # add holes of the desired type
    if p_boreDiameter > 0 and p_boreDepth > 0:
        topOfLid = topOfLidCenters.cboreHole(
            p_screwpostID, p_boreDiameter, p_boreDepth, 2.0 * p_thickness
        )
    elif p_countersinkDiameter > 0 and p_countersinkAngle > 0:
        topOfLid = topOfLidCenters.cskHole(
            p_screwpostID, p_countersinkDiameter, p_countersinkAngle, 2.0 * p_thickness
        )
    else:
        topOfLid = topOfLidCenters.hole(p_screwpostID, 2.0 * p_thickness)

    # flip lid upside down if desired
    if p_flipLid:
        topOfLid = topOfLid.rotateAboutCenter((1, 0, 0), 180)

    # return the combined result
    result = topOfLid.union(bottom)

    # Export to STEP
    exporters.export(result, 'chamfered_cube.step')
    ```

    ## 2. You may alse be required to generate a fix code snippits according to provided context and error information.

    query: <some context code>, <error log>, <how to fix>

    return:
    ```python
    <fixed code snippits>
    ```

    Ensure generating real-world usable models, do not attempt to use any simplified methods to build models.

    Pay attention to the selection of `Workplane`, when build any part of the model.

    Args:
        user_query: The user's query for CAD code generation, you are suppose to put detailed requirements in the query, such as parameters, modeling process, and any other necessary information.
        pay_attention: What need to be paied more attention to when generating code. Strongly recommended to provid when fixing code.
    Returns:
        str: The generated CAD code.
    """


@tool(
    name="pythonocc_code_generation",
    description="Generate CAD modeling code using PythonOCC framework.",
)
@llm_function(
    llm_interface=get_config().CODE_INTERFACE,
    toolkit=[],
)
def pythonocc_code_generation(user_query: str) -> str:  # type: ignore[override]
    """Generate CAD modeling code using PythonOCC framework.
    You should generate code with detailed comments explaining each step.
    And finally you should export the model to a STEP file in code.

    You are supposed to generate complete and executable code that can be run in a Python environment with the PythonOCC library installed.
    The generated code should be contained within a Python code block in your response.
    The code should include the necessary imports, define a function that creates the CAD model, and export the model to a STEP file, file name should be related with the model.
    Make good use of the PythonOCC library and parameterize the model as much as possible to allow for easy modifications.

    Args:
        user_query (str): The user's query for PythonOCC code generation.

    Returns:
        str: The generated PythonOCC code.
    """


@tool(
    name="make_user_query_more_detailed",
    description="You can use this tool to refine and expand the user's requirements",
)
@llm_function(
    llm_interface=get_config().QUICK_INTERFACE,
    toolkit=[],
)
def make_user_query_more_detailed(query: str) -> str:  # type: ignore
    """

            Args:
                query: The user's original request, combined with expanding requirements.

            Returns:
                str: Detailed user request

            ### Task:
            - You need to refine and expand the user's requirements.
            ### Example:
            - User's requirement: I want a gear
            - You can refine it to:
            '''
            以下是你提出的 18 齿、模数 2.0、压力角 20° 的齿轮建模需求的详细扩展版本，采用**结构化建模流程**，适用于 CAD 内核建模系统（如 OCC、CADQuery、Fusion API 等）。内容包括：

            ---

        # 🛠️ 齿轮建模规格书（详细版本）

        ## 一、齿轮参数（Gear Parameters）

            | 参数           | 含义                          | 值       |
            | ------------ | --------------------------- | ------- |
            | `z`          | 齿数（Number of Teeth）         | 18      |
            | `m`          | 模数（Module）                  | 2.0 mm  |
            | `α`          | 压力角（Pressure Angle）         | 20°     |
            | `t`          | 齿轮厚度（Gear Thickness）        | 10.0 mm |
            | `r_hole`     | 中心孔半径（Center Hole Radius）   | 10.0 mm |
            | `slot_width` | 半月槽宽度（Half-moon Slot Width） | 5.0 mm  |

            ---

        ## 二、整体结构拆解与建模步骤

        ### Part 1: 齿轮基体（Gear Base Body）

        #### 📐 Step 1: 生成齿轮外圆 Sketch

            * **几何定义**：

            * 外圆半径 $r_{\text{gear}} = \frac{m \\cdot z}{2} = \frac{2.0 \\cdot 18}{2} = 18.0\\, \text{mm}$

            * **线框（Wire）创建**：

            * 绘制一个圆心为原点、半径为 18.0mm 的 2D Circle（称为 `outer_circle_wire`）

            * **面（Face）生成**：

            * 将 `outer_circle_wire` 封闭成一个 `outer_face`（封闭面）

            * **实体（Body）生成**：

            * 将 `outer_face` 以厚度 10.0mm 沿 Z 轴拉伸成实体，得到圆柱体 `gear_base_body`

            ---

        ### Part 2: 齿轮齿形（Tooth Generation）

        #### 📐 Step 2: 单齿轮廓线生成（Involute Profile）

            * **计算基圆半径**：

            $$
            r_b = r_{\text{gear}} \\cdot \\cos(\alpha) = 18.0 \\cdot \\cos(20°) ≈ 16.91 \text{ mm}
            $$

            * **使用渐开线方程构造齿廓**：

            * 用极坐标定义渐开线：

                $$
                x(\theta) = r_b(\\cos\theta + \theta\\sin\theta), \\quad y(\theta) = r_b(\\sin\theta - \theta\\cos\theta)
                $$
            * 选取合适的 $\theta$ 范围（例如从 0 到 $\theta_{\text{max}}$，可通过齿顶圆截距确定）

            * **构造齿形轮廓线（Tooth Wire）**：

            * 左右渐开线各一条，顶部用圆弧或直线闭合
            * 封闭为一个封闭轮廓（闭合 wire），称为 `tooth_wire`

        #### 📦 Step 3: 拉伸齿廓形成单齿实体

            * 将 `tooth_wire` 拉伸为厚度 `t`，生成 `tooth_solid`（单齿实体）

        #### 🔁 Step 4: 复制旋转成齿轮齿阵列

            * **阵列复制**：

            * 旋转复制 `tooth_solid` 共 18 个（360° / 18 = 20°），得到多个齿实体集合 `teeth_array`

        #### ➕ Step 5: 布尔并集合并齿与基体

            * 对所有齿实体和 `gear_base_body` 进行布尔并集运算，结果命名为 `gear_with_teeth`

            ---

        ### Part 3: 中心孔 + 半月槽（Center Hole & Slot）

        #### ⚙️ Step 6: 中心孔 Sketch

            * **绘制中心孔圆线框**：

            * 半径为 `r_hole = 10.0mm` 的圆 `center_hole_wire`

            * **生成孔体**：

            * 拉伸 `center_hole_wire` 为厚度 `t` 的实体 `center_hole_cylinder`

        #### ➖ Step 7: 布尔减去中心孔
    t
            * `gear_with_hole = gear_with_teeth - center_hole_cylinder`

        #### 🌓 Step 8: 半月槽（Half-moon Slot）可选

            * **构造半月槽 sketch**（可选）：

            * 可以在中心孔边缘切除一个宽为 `slot_width` 的扇形区域
            * 或者：

                * 画一个圆弧宽 5.0mm，附着于孔边
                * 封闭区域后拉伸形成实体 `slot_body`

            * **布尔减去半月槽**：

            * `gear_final = gear_with_hole - slot_body`（如有该槽）

        ---

        ## 四、导出模型

        #### 📁 Step 9: 导出 STEP 文件

            ```python
            gear_final.exportStep("gear_18_teeth.step")
            ```
        ---

        ## 六、建模核心要点提示

        1. **渐开线生成**：

           * 使用解析函数或 CAD 内核自带 involute 工具（如 CADQuery `involute_tooth_profile()`）
        2. **Boolean 操作顺序**：

           * 先 union 所有齿 → 再 subtract center hole → 再 subtract slot（顺序会影响拓扑正确性）
        3. **闭合 Wire 检查**：

           * 齿形必须为完整封闭区域，才能拉伸为 Face 和 Solid
        4. **厚度统一**：

           * 所有 extrusion 都用同一厚度 `t` 保证布尔操作不会失败

        '''

        The real case you should return something much more detailed than the example above, and you should always return a detailed modeling process.

    """


@tool(
    name="execute_command",
    description="Execute a system command in shell and return the output, no interaction is allowed, use this tool to run python scripts or other commands that do not require user input.",
)
def execute_command(command: str) -> str:
    """Execute a system command in shell and return the output.

    Args:
        command: The system command to execute, recommended commands are python <script path>
    Returns:
        The command output
    """

    try:
        # 显示命令执行开始
        print_tool_output("⚡ SYSTEM 执行命令", f"正在执行: {command}")

        start_time = time.time()
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=35
        )

        execution_time = time.time() - start_time

        # 打印结果
        if result.returncode == 0:
            print_tool_output(
                "✅ SYSTEM 命令执行完成",
                f"命令执行成功！\nReturn code: {result.returncode}\nExecution time: {execution_time:.2f}s\nOutput length: {len(result.stdout)} chars",
            )
            return result.stdout.strip()
        else:
            print_tool_output(
                "❌ SYSTEM 命令执行失败",
                f"命令执行失败！\n错误信息: {result.stderr.strip()}",
            )
            return (
                result.stderr.strip()
                + "\n\n超时可能是程序等待input导致的，请使用测试代码来进行测试。"
            )

    except Exception as e:
        print_tool_output("💥 SYSTEM 错误", f"执行命令失败: {str(e)}")
        return f"执行命令失败: {str(e)}"


@tool(
    name="interactive_terminal",
    description="Run an interactive terminal application with support for predefined input list for interaction",
)
def interactive_terminal(
    command: str,
    inputs: List[str] = [],
    timeout_seconds: int = 60,
    read_interval: float = 0.1,
) -> str:  # type: ignore
    """Run an interactive terminal application that can read output in real-time and provide input

    This tool can start a terminal process and allows you to interact with it multiple times.
    It will run within the specified timeout period or terminate when the program naturally ends.

    Args:
        command: The command to execute, e.g., python script.py
        inputs: List of inputs to send to the program, sent in order
        timeout_seconds: Maximum runtime in seconds, default 60 seconds
        read_interval: Time interval for reading output in seconds, default 0.1 seconds

    Returns:
        Complete output log of the program, including all interaction processes
    """

    # 显示交互会话开始信息
    session_table = Table.grid()
    session_table.add_column(style="cyan", justify="right")
    session_table.add_column()
    session_table.add_row("Command:", f"[bold white]{command}[/bold white]")
    session_table.add_row("Timeout:", f"{timeout_seconds}s")
    session_table.add_row("Inputs queued:", str(len(inputs)))
    session_table.add_row("Started at:", time.strftime("%H:%M:%S"))

    print_tool_output("🚀 SYSTEM 启动交互命令", "启动交互会话")

    # Create a list to record complete interaction
    interaction_log: List[str] = []

    try:
        # Use popen to create an interactive process
        process = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffering
            universal_newlines=True,
        )

        # Set non-blocking mode
        if process.stdout:
            os.set_blocking(process.stdout.fileno(), False)
        if process.stderr:
            os.set_blocking(process.stderr.fileno(), False)

        start_time = time.time()
        input_index = 0
        last_output = ""

        # Main interaction loop
        while process.poll() is None:
            # Check for timeout
            if time.time() - start_time > timeout_seconds:
                interaction_log.append("\n[SYSTEM] Process timeout, force termination")
                process.kill()
                break

            # Read output
            readable, _, _ = select.select(
                [process.stdout, process.stderr], [], [], read_interval
            )

            output = ""
            if process.stdout in readable and process.stdout:
                chunk = process.stdout.read()
                if chunk:
                    output += chunk

            if process.stderr in readable and process.stderr:
                chunk = process.stderr.read()
                if chunk:
                    output += "[ERROR] " + chunk

            # If there's new output, record it and check if input is needed
            if output:
                last_output = output
                interaction_log.append(f"[OUTPUT] {output}")
                print_tool_output("程序输出", output, style="cyan")
                # Check if there are pending inputs to send
                if input_index < len(inputs):
                    user_input = inputs[input_index]
                    input_index += 1

                    # Give the program some time to process output
                    time.sleep(0.5)

                    # Send input to the program
                    if process.stdin:
                        process.stdin.write(user_input + "\n")
                        process.stdin.flush()

                    interaction_log.append(f"[INPUT] {user_input}")
                    print_tool_output(
                        "已发送输入", user_input if user_input else "", style="magenta"
                    )
            # Brief sleep to reduce CPU usage
            time.sleep(read_interval)

        # After process ends, read remaining output
        remaining_output = ""
        if process.stdout:
            remaining_output = process.stdout.read()
        if remaining_output:
            interaction_log.append(f"[OUTPUT] {remaining_output}")
            print_tool_output("程序输出", remaining_output, style="cyan")
        remaining_error = ""
        if process.stderr:
            remaining_error = process.stderr.read()
        if remaining_error:
            interaction_log.append(f"[ERROR] {remaining_error}")
            print_tool_output("程序错误", remaining_error, style="red")
        # Get return code
        return_code = process.wait()
        interaction_log.append(f"[SYSTEM] Process ended, return code: {return_code}")

        # If process terminated abnormally, record last output
        if return_code != 0:
            interaction_log.append(
                f"[SYSTEM] Process terminated abnormally, last output: {last_output}"
            )

        print_tool_output(
            "SYSTEM 交互命令执行完成",
            "Interactive command execution completed",
            style="green",
        )

        # Return complete interaction log
        return "\n".join(interaction_log)

    except Exception as e:
        error_message = f"Failed to execute interactive command: {str(e)}"
        print_tool_output("SYSTEM 错误", error_message, style="red")


@tool(
    name="file_operations",
    description="Perform line-level file operations: read (all or specific lines), modify, insert, append, or overwrite. 1-based line indexing.",
)
def file_operations(
    file_path: str,
    operation: str,
    content: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    include_line_numbers: bool = False,
) -> str:  # type: ignore
    """
    File operations with line-level granularity.
    Also prints detailed console instructions with content boundaries.

    Args:
        file_path: Path to file.
        operation: One of "read", "modify", "insert", "append", "overwrite".
        content: Content for write/modify. Optional for read.
        start_line: Start line (1-based). Required for modify/insert/read.
        end_line: End line (1-based, inclusive). Required for modify/read.
        include_line_numbers: Whether to include line numbers in "read" output.

    Returns:
        str: Result of the operation or file content.
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
    if content:
        op_table.add_row("Content length:", f"{len(content)} chars")

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
            if include_line_numbers:
                return "".join([f"{i+1}: {line}" for i, line in enumerate(selected, s)])
            else:
                return "".join(selected)

        elif operation == "overwrite":
            print_action(f"Overwriting entire file: {file_path}", content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content or "")
            return "File overwritten successfully."

        elif operation == "append":
            print_action(f"Appending content to file: {file_path}", content)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content or "")
            return "Content appended to file."

        elif operation == "insert":
            if content is None:
                return print_error("You must provide content to insert.")
            if start_line is None or not (1 <= start_line <= total_lines + 1):
                return print_error(
                    f"Invalid start_line for insert. Must be in [1, {total_lines+1}]."
                )
            print_action(
                f"Inserting at line {start_line} in file: {file_path}", content
            )
            new_lines = content.splitlines(keepends=True)
            idx = start_line - 1
            lines = lines[:idx] + new_lines + lines[idx:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return f"Inserted at line {start_line}."

        elif operation == "modify":
            if content is None:
                return print_error("You must provide content to modify.")
            if start_line is None or end_line is None:
                return print_error("start_line and end_line are required for modify.")
            if not (1 <= start_line <= end_line <= total_lines):
                return print_error(f"Modify range must be within [1, {total_lines}].")
            print_action(
                f"Modifying lines {start_line}-{end_line} in file: {file_path}", content
            )
            new_lines = content.splitlines(keepends=True)
            lines = lines[: start_line - 1] + new_lines + lines[end_line:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return f"Lines {start_line}-{end_line} modified successfully."

    except Exception as e:
        return print_error(str(e))
