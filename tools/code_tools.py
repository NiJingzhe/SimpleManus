"""
CAD代码生成工具模块
"""
from SimpleLLMFunc import llm_function, tool
from typing import Optional
import json
from .common import (
    get_config, global_context, print_tool_output, 
    safe_asyncio_run, get_global_sketch_pad
)


@tool(
    name="cad_query_code_generator",
    description="Generate high-quality CAD Query code based on user requirements and context information. Supports SketchPad key input and auto-storage.",
)
def cad_query_code_generator(query: str, store_result: bool = True) -> str:
    """
    Args:
        query: 用户的原始请求，或者SketchPad的key用于引用已存储的需求;你也可以使用SketchPad的key来引用之前的需求内容，如果这样你需要使用`key:`前缀来标识,例如：`key:1234567890abcdef`
        store_result: 是否自动将生成的代码存储到SketchPad
        
    Returns:
        str: 生成的CAD Query代码和SketchPad key信息
    """
    
    sketch_pad = get_global_sketch_pad()
    
    # 检查query是否为SketchPad key
    if query.startswith("key:"):
        key_to_retrieve = query[4:]  # 去掉 "key:" 前缀
        sketch_content = sketch_pad.retrieve(key_to_retrieve)
        if sketch_content is not None:
            actual_query = str(sketch_content)
            print_tool_output(
                title="📋 CADQuery Code Gen：从SketchPad获取需求",
                content=f"Key: {key_to_retrieve}\n需求内容: {actual_query[:100]}..."
            )
        else:
            actual_query = query.strip()
            print_tool_output(
                title="📋 CADQuery Code Gen：SketchPad key未找到，使用原始query",
                content=f"处理请求： {actual_query[:100]}..."
            )
    else:
        actual_query = query.strip()
        print_tool_output(
            title="📋 CADQuery Code Gen： 使用用户提供的需求生成代码",
            content=f"处理请求： {actual_query[:100]}..."
        )
    
    context = global_context.get_formatted_history()[-3:]
    context = json.dumps(context, ensure_ascii=False, indent=2)
    
    result = cad_query_code_generator_impl(actual_query, context)
    
    print_tool_output(
        title="生成的CAD Query代码",
        content=result[:100] + ("..." if len(result) > 100 else ""),
    )
    
    # 自动存储生成的代码到SketchPad
    if store_result:
        import uuid
        code_key = f"code_{uuid.uuid4().hex[:8]}"
        
        async def _store_code():
            return await sketch_pad.store(
                value=result.strip(),
                key=code_key,  # 使用自定义key
                tags={"cadquery", "generated_code", "modeling"},
                auto_summarize=True
            )
        
        try:
            actual_key = safe_asyncio_run(_store_code)
            
            print_tool_output(
                title="💾 代码已存储到SketchPad",
                content=f"Key: {code_key}\n代码长度: {len(result)} 字符"
            )
            
            return f"""CAD代码生成完成并存储到SketchPad:

🔑 SketchPad Key: {code_key}
# Tag: cadquery, generated_code, modeling 
📄 代码内容:
```python
{result.strip()}
```

💡 提示: 您现在可以使用key "{code_key}" 进行后续操作:
- 使用 file_operations 工具将代码保存到文件
- 使用 execute_command 工具运行代码
- 使用 sketch_pad_operations 工具管理和引用此代码

建议充分利用SketchPad的key机制！"""
        
        except Exception as e:
            print_tool_output("❌ 存储失败", f"Failed to store code: {e}")
            return result.strip()
    
    return result.strip()


@llm_function(
    llm_interface=get_config().CODE_INTERFACE,
    timeout=600,
)
def cad_query_code_generator_impl(
    query: str, context: str
) -> str:  # type: ignore
    """
    Args:
        query: 用户的原始请求
        context: 上下文信息，包含用户的意图、扩展意图和可能的参考代码
        
    Returns:
        str: 生成的CAD Query代码
    
    
    # Task:
    You are an expert CAD engineer with access to the Python library CadQuery .
    Your job is to create Python code that generates a 3 D model based on a given description .
    Make sure to include all relevant parts .
    Pay special attention to the orientation of all parts , e . g . , by choosing appropriate workplanes .
    For instance , pick a workplane perpendicular to the ground for sketching the outline of the wheels
    of a toy car .
    Whenever possible , use the default workplanes , i . e . , XY , XZ , and YZ .
    
    # 例如：
    query: 我想要一个带有盖子的盒子
    
    return:
    ```python
    import cadquery as cq
    from cadquery import exporters
    from cadquery.func import *
    # -------------------------
    # Parameters
    # -------------------------
    p_outerWidth = 100.0
    p_outerLength = 150.0
    p_outerHeight = 50.0

    p_thickness = 3.0
    p_sideRadius = 10.0
    p_topAndBottomRadius = 2.0

    p_screwpostInset = 12.0
    p_screwpostID = 4.0
    p_screwpostOD = 10.0

    p_boreDiameter = 8.0
    p_boreDepth = 1.0
    p_countersinkDiameter = 0.0
    p_countersinkAngle = 90.0
    p_flipLid = True
    p_lipHeight = 1.0

    # -------------------------
    # Outer shell
    # -------------------------
    oshell = (
        cq.Workplane("XY")
        .rect(p_outerWidth, p_outerLength)
        .extrude(p_outerHeight + p_lipHeight)
        .tag("outer_shell_raw")
    )

    if p_sideRadius > p_topAndBottomRadius:
        oshell = oshell.edges("|Z").fillet(p_sideRadius)
        oshell = oshell.edges("#Z").fillet(p_topAndBottomRadius)
    else:
        oshell = oshell.edges("#Z").fillet(p_topAndBottomRadius)
        oshell = oshell.edges("|Z").fillet(p_sideRadius)

    # -------------------------
    # Inner shell
    # -------------------------
    ishell = (
        oshell.faces("<Z")
        .workplane(p_thickness, True)
        .rect(p_outerWidth - 2 * p_thickness, p_outerLength - 2 * p_thickness)
        .extrude(p_outerHeight - 2 * p_thickness, combine=False)
        .edges("|Z")
        .fillet(p_sideRadius - p_thickness)
        .tag("inner_shell")
    )

    box = oshell.cut(ishell).tag("main_box")

    # -------------------------
    # Screw posts
    # -------------------------
    POSTWIDTH = p_outerWidth - 2.0 * p_screwpostInset
    POSTLENGTH = p_outerLength - 2.0 * p_screwpostInset

    box = (
        box.faces(">Z")
        .workplane(-p_thickness)
        .rect(POSTWIDTH, POSTLENGTH, forConstruction=True)
        .vertices()
        .tag("screw_positions")
        .circle(p_screwpostOD / 2.0)
        .circle(p_screwpostID / 2.0)
        .extrude(-1.0 * (p_outerHeight + p_lipHeight - p_thickness), True)
    )

    # -------------------------
    # Split into lid and bottom
    # -------------------------
    (lid, bottom) = (
        box.faces(">Z")
        .workplane(-p_thickness - p_lipHeight)
        .split(keepTop=True, keepBottom=True)
        .all()
    )

    bottom = bottom - lid

    # Create new lid with inset lip
    lowerLid = lid.translate((0, 0, -p_lipHeight))
    cutlip = (
        lowerLid.cut(bottom)
        .translate((p_outerWidth + p_thickness, 0, p_thickness - p_outerHeight + p_lipHeight))
        .tag("lid_with_lip")
    )

    # -------------------------
    # Screw holes
    # -------------------------
    topOfLidCenters = (
        cutlip.faces(">Z")
        .workplane(centerOption="CenterOfMass")
        .rect(POSTWIDTH, POSTLENGTH, forConstruction=True)
        .vertices()
    )

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

    if p_flipLid:
        topOfLid = topOfLid.rotateAboutCenter((1, 0, 0), 180)

    del lowerLid
    del lid
    del box
    del oshell
    del ishell

    # -------------------------
    # Final result
    # -------------------------
    result = topOfLid.union(bottom).union(loft)

    # -------------------------
    # Export
    # -------------------------
    exporters.export(result, "fixed_box_with_lid.step")
    exporters.export(result, "fixed_box_with_lid.stl")
    ``` 
    """

