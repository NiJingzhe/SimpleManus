"""
细化需求工具模块
"""
from SimpleLLMFunc import llm_function, tool
from typing import Optional
import json
from .common import (
    get_config, global_context, print_tool_output, 
    safe_asyncio_run, get_global_sketch_pad
)


@tool(
    name="make_user_query_more_detailed",
    description="You can use this tool to refine and expand the user's requirements. Automatically stores expanded requirements in SketchPad.",
)
def make_user_query_more_detailed(query: str, store_in_sketch_pad: bool = True) -> str:
    """
        Args:
            query: The user's original request, combined with expanding requirements.
            store_in_sketch_pad: Whether to automatically store the expanded query in SketchPad

        Returns:
            str: Detailed user request with SketchPad key information
    """
    
    print_tool_output(
        title="使用工具细化用户需求",
        content=f"细化要求： {query}",
    )

    context = global_context.get_formatted_history()[-3:]
    context = json.dumps(context, ensure_ascii=False, indent=2)
    
    result = make_user_query_more_detailed_impl(query, context)  # type: ignore[call-arg]

    # 去掉头部的<think></think>标签
    if result.startswith("<think>"):
        result = result[len("<think></think>") :]

    print_tool_output(
        title="细化后的用户需求",
        content=result,
    )

    # 自动存储到 SketchPad
    if store_in_sketch_pad:
        import uuid
        sketch_pad = get_global_sketch_pad()
        sketch_key = f"req_{uuid.uuid4().hex[:8]}"
        
        async def _store_detailed_query():
            return await sketch_pad.store(
                value=result.strip(),
                key=sketch_key,  # 使用自定义key
                tags={"detailed_query", "requirements", "expanded"},
                auto_summarize=True
            )
        
        try:
            actual_key = safe_asyncio_run(_store_detailed_query)
            
            print_tool_output(
                title="💾 已存储到 SketchPad",
                content=f"Key: {sketch_key}\n详细需求已保存，您可以使用此key在后续工具中引用"
            )
            
            # 返回包含key信息的结果
            return f"""详细需求已生成并存储到SketchPad:

🔑 SketchPad Key: {sketch_key}
# Tags: detailed_query, requirements, expanded
📋 详细需求内容:
{result.strip()}

💡 提示: 您现在可以使用key "{sketch_key}" 在后续的工具操作中引用此详细需求，例如:
- 使用 cad_query_code_generator 工具时，可以直接传入此key作为query参数
- 使用 file_operations 工具将需求保存到文件
- 使用 sketch_pad_operations 工具进行进一步的内容管理

建议您充分利用SketchPad的key机制来提高工作效率！"""
        
        except Exception as e:
            print_tool_output("❌ 存储失败", f"Failed to store in SketchPad: {e}")
            return result.strip()  # 返回原始结果
    
    return result.strip()


@llm_function(
    llm_interface=get_config().QUICK_INTERFACE,
    timeout=600
)
def make_user_query_more_detailed_impl(query: str, context: str) -> str:  # type: ignore
    """       
        ### Task:
        - You need to refine and expand the user's requirements.

        - user requirements will be contained in the `query` parameter.

        - Pay Attention that we are going to write CADQuery Code, so the requirements should be detailed with CADQuery API

        ### Example:
        - query: I want a gear
        - You can refine it to:
        '''
        # 🛠️ 齿轮建模规

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
        2. **Boolean 操作顺序**：
           * 先 union 所有齿 → 再 subtract center hole → 再 subtract slot（顺序会影响拓扑正确性）
        3. **闭合 Wire 检查**：
           * 齿形必须为完整封闭区域，才能拉伸为 Face 和 Solid
        4. **厚度统一**：
           * 所有 extrusion 都用同一厚度 `t` 保证布尔操作不会失败

        请务必使用正确的CADQuery API和几何概念来实现以上步骤，确保生成的齿轮符合设计要求。
        '''
    """
