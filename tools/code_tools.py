"""
CAD代码生成工具模块
"""

from typing import Optional
from SimpleLLMFunc import llm_function, tool
from .common import (
    get_config,
    print_tool_output,
    safe_asyncio_run,
)
from context.conversation_manager import get_current_sketch_pad


@tool(
    name="cad_code_generator",
    description="Generate high-quality SimpleCADAPI code based on user requirements and context information. Supports SketchPad key input and auto-storage.",
)
def cad_code_generator(query: str, ref_code_path: Optional[str] = None) -> str:
    """
    Args:
        query: 用户的原始请求，或者SketchPad的key用于引用已存储的需求;你也可以使用SketchPad的key来引用之前的需求内容，如果这样你需要使用`key:`前缀来标识,例如：`key:1234567890abcdef`
        code: 一个可选参数，如果你需要修改一个已有的代码建议结合query在这个ref_code的基础上做出小幅度的修改，可以将已有的代码传递到这个参数。支持传递一个SketchPad的key来引用之前的代码内容，如果这样你需要使用`key:`前缀来标识,例如：`key:1234567890abcdef`
        ref_code_path: 一个可选参数，代表参考代码的路径，如果传递请务必参考ref code来进行新的代码生成。

    Returns:
        str: 生成的SimpleCADAPI代码和SketchPad key信息
    """

    store_result: bool = True

    sketch_pad = get_current_sketch_pad()
    if sketch_pad is None:
        return "错误：无活动conversation上下文，无法访问SketchPad"

    # 检查query是否为SketchPad key
    if query.startswith("key:"):
        key_to_retrieve = query[4:]  # 去掉 "key:" 前缀
        sketch_content = sketch_pad.get_value(key_to_retrieve)
        if sketch_content is not None:
            actual_query = str(sketch_content)
            print_tool_output(
                title="📋 SimpleCADAPI Code Gen：从SketchPad获取需求",
                content=f"Key: {key_to_retrieve}\n需求内容: {actual_query[:100]}...",
            )
        else:
            actual_query = query.strip()
            print_tool_output(
                title="📋 SimpleCADAPI Code Gen：SketchPad key未找到，使用原始query",
                content=f"处理请求： {actual_query[:100]}...",
            )
    else:
        actual_query = query.strip()
        print_tool_output(
            title="📋 SimpleCADAPI Code Gen： 使用用户提供的需求生成代码",
            content=f"处理请求： {actual_query[:100]}...",
        )

    ref_code = None
    if (
        ref_code_path is not None
        and ref_code_path != "null"
        and ref_code_path != "None"
    ):

        with open(ref_code_path, "r", encoding="utf-8") as f:
            ref_code = f.read().strip()

        print_tool_output(
            title="📋 SimpleCADAPI Code Gen： 使用参考代码生成代码",
            content=f"处理参考代码： {ref_code[:100]}...",
        )

    result = cad_code_generator_impl(
        actual_query,
        ref_code if ref_code is not None else None,
    )

    # 去掉开头可能存在的think部分
    if result.startswith("<think>"):

        result = result.split("<think>")[1].split("</think>")[1].strip()

    if "```python" in result:
        # 提取代码块内容
        result = result.split("```python")[1].split("```")[0].strip()

    else:
        result = result.strip()

    print_tool_output(
        title="生成的SimpleCADAPI代码",
        content=result[:100] + ("..." if len(result) > 100 else ""),
    )

    # 自动存储生成的代码到SketchPad
    if store_result:
        import uuid

        sketch_pad = get_current_sketch_pad()
        if sketch_pad is None:
            print_tool_output(
                "⚠️ 警告", "无活动conversation上下文，无法存储代码到SketchPad"
            )
            return result.strip()

        code_key = f"code_{uuid.uuid4().hex[:8]}"

        async def _store_code():
            return await sketch_pad.set_item(
                key=code_key,  # 使用自定义key
                value=result.strip(),
                ttl=None,
                summary=None,
                tags={"simplecadapi", "generated_code", "modeling"},
            )

        try:
            _ = safe_asyncio_run(_store_code)

            print_tool_output(
                title="💾 代码已存储到SketchPad",
                content=f"Key: {code_key}\n代码长度: {len(result)} 字符",
            )

            return (
                "📄 代码内容:\n"
                f"```python\n"
                f"{result.strip()}\n"
                "```\n\n"
                "CAD代码生成完成并存储到SketchPad:\n\n"
                f"🔑 SketchPad Key: {code_key}\n"
                "# Tag: simplecadapi, generated_code, modeling\n"
                f'💡 提示: 您现在可以使用key "{code_key}" 进行后续操作:\n'
                "- 使用 file_operations 工具将代码保存到文件\n"
                "- 使用 execute_command 工具运行代码\n"
                "- 使用 sketch_pad_operations 工具管理和引用此代码\n\n"
                "建议充分利用SketchPad的key机制！"
            )

        except Exception as e:
            print_tool_output("❌ 存储失败", f"Failed to store code: {e}")
            return result.strip()

    return result.strip()


@llm_function(
    llm_interface=get_config().REASONING_INTERFACE,
    timeout=600,
)
def cad_code_generator_impl(query: str, ref_code: Optional[str]) -> str:  # type: ignore
    """
    Args:
        query: The original request from the user.
        ref_code: An optional parameter providing reference code which may include relevant APIs or example usage. If provided, you **must** refer to it when generating new code.

    Returns:
        str: The generated SimpleCADAPI code.

    # Background Info:

    The SimpleCAD API offers a complete set of geometric modeling classes, ranging from basic points, lines, and faces to complex solids and compounds. Each class comes with a rich set of functionalities and a flexible tagging system.

    ### Basic Classes
    #### [CoordinateSystem]
    #### [SimpleWorkplane]
    The working plane is used as a context manager via `with`, providing a local coordinate environment and supporting nested usage.

    ### Geometry Classes

    ##### [Vertex]
    ##### [Edge]
    ```python
    get_end_vertex(self) -> simplecadapi.core.Vertex
        Returns the end vertex.

    get_length(self) -> float
        Returns the length of the edge.

    get_start_vertex(self) -> simplecadapi.core.Vertex
        Returns the start vertex.
    ````

    ##### [Wire]

    ```python
    get_edges(self) -> List[simplecadapi.core.Edge]
        Returns the list of edges forming the wire.

    is_closed(self) -> bool
        Checks whether the wire is closed.
    ```

    ##### [Face]

    ```python
    get_area(self) -> float
        Returns the area.

    get_inner_wires(self) -> List[simplecadapi.core.Wire]
        Returns a list of inner boundary wires.

    get_normal_at(self, u: float = 0.5, v: float = 0.5) -> cadquery.occ_impl.geom.Vector
        Returns the face normal at the specified UV coordinates.

    get_outer_wire(self) -> simplecadapi.core.Wire
        Returns the outer boundary wire.
    ```

    ##### [Shell]

    ##### [Solid]

    ```python
    auto_tag_faces(self, geometry_type: str = 'unknown') -> None
        Automatically tags the faces of the solid based on geometry type.
        Args:
            geometry_type: 'box', 'cylinder', 'sphere', or 'unknown'.

    get_edges(self) -> List[simplecadapi.core.Edge]
        Returns the list of edges in the solid.

    get_faces(self) -> List[simplecadapi.core.Face]
        Returns the list of faces in the solid.

    get_volume(self) -> float
        Returns the volume.
    ```

    ##### [Compound]

    ## Inheritance

    All geometry classes inherit from `TaggedMixin`, providing a unified tagging and metadata system:

    * **Tag System**: Add string tags to geometries for classification and filtering.
    * **Metadata System**: Store key-value data for managing rich attributes.
    * **Query Support**: Efficient filtering and querying based on tags and metadata.

    ```python
    add_tag(self, tag: str) -> None
        Adds a tag to the object.

    get_metadata(self, key: str, default: Any = None) -> Any
        Retrieves metadata.

    get_tags(self) -> list[str]
        Returns all tags.

    has_tag(self, tag: str) -> bool
        Checks if the object has a specific tag.

    remove_tag(self, tag: str) -> None
        Removes a specific tag.

    set_metadata(self, key: str, value: Any) -> None
        Sets metadata.
    ```

    ## Coordinate System

    SimpleCAD uses a unified coordinate system:

    * **Global Coordinate System**: Right-handed with Z-up.
    * **Local Coordinate Systems**: Defined via `CoordinateSystem` and `SimpleWorkplane`.
    * **CADQuery Compatible**: Automatically handles conversions between SimpleCAD and CADQuery coordinate systems.

    ## Design Principles

    ### Consistency

    All classes follow a consistent design pattern and naming convention (Verb + Noun + ReturnType) to ensure a unified experience.

    ## Usage Guide

    1. **Create Geometry**: Use `make_*` functions to generate base geometry.
    2. **Combine Shapes**: Use Boolean operations, transforms, etc., to build complex geometry.
    3. **Query & Filter**: Use tags and metadata to find and manipulate geometry components.

    ### Best Practices

    1. **Tag Naming**: Use structured tags like `category.subcategory.detail`.
    2. **Metadata Organization**: Use structured data to store meaningful properties.
    3. **Coordinate Management**: Use workplanes to simplify construction.
    4. **Translation Awareness**: Be aware of where solids are created and translated—often the base face is used as the anchor, not the geometric center. Apply translations accordingly to enable valid Boolean operations.

    # Role & Task:

    * You are a professional CAD code generation expert skilled in using the **SimpleCADAPI** Python framework for CAD model design.

    * Your task is: understand the user’s design intent, analyze spatial and geometric constraints, and write **high-quality SimpleCADAPI Python code** that accurately fulfills the user’s design goals.

    # Task Instructions:

    * Input: The input will contain two parts: 1) relevant API reference documentation and 2) a specific modeling requirement.

    * Strategy: You must strictly follow the API specifications. In theory, the provided APIs are sufficient for all modeling tasks. It's **critical** to fully understand the spatial geometry and constraints described in the modeling requirement.

    # Code Style Guide:

    * The code must consist of two parts:

      1. A function that builds and returns the target `Solid`.
      2. A `__main__` block that calls this function and uses `export_stl` and `export_step` to export the result.

    * Code must contain **fine-grained exception handling**. When raising an exception, **explicitly** mention the line that might have failed, **describe the probable cause**, and **suggest possible fixes**.

    * Print logs at appropriate modeling stages to assist debugging. All geometric primitives can be printed in structured format—**printing geometry is encouraged** for debugging.

    * Include detailed comments explaining spatial reasoning and geometric logic.

    * When printing logs, also print the entire `Solid` object—it contains hints like auto-generated tags that may guide future operations (e.g., fillets or chamfers).

    # Important Notes:

    * **Always** start with the following for better error tracking:

    ```python
    from rich import traceback
    traceback.install(show_locals=True, width=200, code_width=120, indent_guides=True)
    from simplecadapi import *
    ```

    * The docstring for the modeling function **must** follow this format:

    ```python
    '''
        Description of what this function does.

        Args:
            arg1 (type): Description of arg1
            ...

        Returns:
            return_type: Description of return value

        Raises:
            ExceptionType1: Description
            ExceptionType2: Description
            ...

        Usage:
            Detailed usage instructions and examples.

        Example:
            Brief example code.
    '''

    * **Do NOT** wrap the `main()` block in a `try/except`; this will disable the rich traceback.

    * All code must be enclosed within a single `python` code block using triple backticks:

    ```python
    # code here
    ```
    - Print logs must include the `Solid` object itself, as its structure reveals taggable features that help with refinement.

    - Use `get_edges()` / `get_faces()` + `has_tag()` to filter features within a `Solid` for further operations.

    - When creating solids, **the origin is always the center of the base face**, not the centroid! This matters when aligning or transforming objects.

    - Use **English** for all comments and printed logs.

    - Use inline comments to explain spatial calculations during geometry creation.

    - If `ref_code` is provided, you must refer to it when generating new code.
    """
