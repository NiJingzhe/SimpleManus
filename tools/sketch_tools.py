"""
SketchPad操作工具模块
"""
from SimpleLLMFunc import tool
from typing import Optional
from .common import (
    print_tool_output, safe_asyncio_run, get_global_sketch_pad
)


@tool(
    name="sketch_pad_operations",
    description="Store, retrieve, search and manage data in SketchPad. Supports key-value storage with automatic summarization.",
)
def sketch_pad_operations(
    operation: str,
    key: Optional[str] = None,
    value: Optional[str] = None,
    tags: Optional[str] = None,
    search_query: Optional[str] = None,
    ttl: Optional[int] = None
) -> str:
    """
    Perform operations on SketchPad storage.
    
    Args:
        operation: One of "store", "retrieve", "delete", "list", "search_tags", "search", "clear", "stats"
        key: Key for store/retrieve/delete operations
        value: Value to store (required for store operation)
        tags: Comma-separated tags for store operation, marking the item with specific labels
        search_query: Query for search operations
        ttl: Time to live in seconds (optional for store)
    
    Returns:
        str: Result of the operation
    """
    
    sketch_pad = get_global_sketch_pad()
    
    try:
        if operation == "store":
            if not value:
                return "Error: value is required for store operation"
            
            # 处理标签
            tag_set = set()
            if tags:
                tag_set = set(tag.strip() for tag in tags.split(","))
            
            # 异步调用需要在同步函数中处理
            async def _store():
                return await sketch_pad.store(
                    value=value,
                    key=key,
                    ttl=ttl,
                    tags=tag_set,
                    auto_summarize=True
                )
            
            actual_key = safe_asyncio_run(_store)
            
            print_tool_output(
                title="✅ SketchPad 存储成功",
                content=f"Key: {actual_key}\nValue length: {len(value)} chars\nTags: {tags or 'None'}"
            )
            return f"Stored successfully with key: {actual_key}"
        
        elif operation == "retrieve":
            if not key:
                return "Error: key is required for retrieve operation"
            
            value = sketch_pad.retrieve(key)
            if value is None:
                print_tool_output("❌ SketchPad 检索失败", f"Key '{key}' not found")
                return f"Key '{key}' not found"
            
            print_tool_output(
                title="✅ SketchPad 检索成功",
                content=f"Key: {key}\nValue: {str(value)[:200]}..." if len(str(value)) > 200 else f"Key: {key}\nValue: {value}"
            )
            return str(value)
        
        elif operation == "delete":
            if not key:
                return "Error: key is required for delete operation"
            
            success = sketch_pad.delete(key)
            if success:
                print_tool_output("✅ SketchPad 删除成功", f"Key '{key}' deleted")
                return f"Key '{key}' deleted successfully"
            else:
                print_tool_output("❌ SketchPad 删除失败", f"Key '{key}' not found")
                return f"Key '{key}' not found"
        
        elif operation == "list":
            items = sketch_pad.list_all(include_details=True)
            if not items:
                return "SketchPad is empty"
            
            result = "SketchPad Contents:\n"
            for item in items[:10]:  # 限制显示前10个
                summary = item.get('summary') or 'No summary'
                result += f"- {item['key']}: {summary[:50]}...\n"
            
            if len(items) > 10:
                result += f"... and {len(items) - 10} more items"
            
            print_tool_output("📋 SketchPad 内容列表", result)
            return result
        
        elif operation == "search_tags":
            if not search_query:
                return "Error: search_query is required for search_tags operation"
            
            # 解析标签查询
            tag_set = set(tag.strip() for tag in search_query.split(","))
            results = sketch_pad.find_by_tags(tag_set)
            
            if not results:
                return f"No items found with tags: {search_query}"
            
            result = f"Found {len(results)} items with tags '{search_query}':\n"
            for item in results[:5]:  # 限制显示前5个
                summary = item.get('summary') or 'No summary'
                result += f"- {item['key']}: {summary[:50]}...\n"
            
            print_tool_output("🔍 SketchPad 标签搜索结果", result)
            return result
        
        elif operation == "search":
            if not search_query:
                return "Error: search_query is required for search operation"
            
            results = sketch_pad.search(search_query)
            
            if not results:
                return f"No items found for query: {search_query}"
            
            result = f"Found {len(results)} items for '{search_query}':\n"
            for item in results[:5]:  # 限制显示前5个
                summary = item.get('summary') or 'No summary'
                result += f"- {item['key']}: {summary[:50]}...\n"
            
            print_tool_output("🔍 SketchPad 内容搜索结果", result)
            return result
        
        elif operation == "clear":
            sketch_pad.clear_all()
            print_tool_output("🗑️ SketchPad 已清空", "All items have been removed")
            return "SketchPad cleared successfully"
        
        elif operation == "stats":
            stats = sketch_pad.get_statistics()
            result = f"SketchPad Statistics:\n"
            result += f"- Total items: {stats['total_items']}\n"
            result += f"- Max items: {stats['max_items']}\n"
            result += f"- Items with summary: {stats['items_with_summary']}\n"
            result += f"- Total accesses: {stats['total_accesses']}\n"
            result += f"- Memory usage: {stats['memory_usage_percent']:.1f}%\n"
            if stats['popular_tags']:
                result += f"- Popular tags: {', '.join(stats['popular_tags'].keys())}\n"
            if stats['content_types']:
                result += f"- Content types: {', '.join(stats['content_types'].keys())}\n"
            
            print_tool_output("📊 SketchPad 统计信息", result)
            return result
        
        else:
            return f"Error: Unknown operation '{operation}'. Supported: store, retrieve, delete, list, search_tags, search, clear, stats"
    
    except Exception as e:
        error_msg = f"SketchPad operation failed: {str(e)}"
        print_tool_output("❌ SketchPad 操作失败", error_msg)
        return error_msg

