"""
MongoEngine补丁模块
为MongoDB 7.0+兼容性提供优雅的解决方案，通过猴子补丁修复MongoEngine的索引创建问题
"""

import logging
from typing import Any, Dict, List
from mongoengine import Document  # type: ignore
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from SimpleLLMFunc.logger import app_log, push_warning, push_error


def modern_ensure_indexes(cls):
    """现代化的ensure_indexes方法，替换MongoEngine的原始实现
    
    这个方法：
    1. 不使用已弃用的background参数
    2. 正确处理_id索引
    3. 兼容MongoDB 7.0+
    """
    try:
        collection = cls._get_collection()
        
        # 获取索引定义
        meta = getattr(cls, '_meta', {})
        indexes = meta.get('indexes', [])
        
        if not indexes:
            # 没有自定义索引需要创建
            return
        
        # 转换索引定义
        index_models = []
        for index_def in indexes:
            try:
                index_model = _convert_index_definition(index_def)
                if index_model:
                    index_models.append(index_model)
            except Exception as e:
                push_warning(f"跳过无效索引定义 {index_def} in {cls.__name__}: {e}")
                continue
        
        if index_models:
            # 创建索引
            try:
                result = collection.create_indexes(index_models)
                app_log(f"🎯 为 {cls.__name__} 创建了 {len(result)} 个现代化索引")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    # 索引已存在，这是正常的
                    pass
                else:
                    push_warning(f"创建索引时出现操作错误 {cls.__name__}: {e}")
        
    except Exception as e:
        push_warning(f"现代化索引创建失败 {cls.__name__}: {e}")


def _convert_index_definition(index_def):
    """转换索引定义为PyMongo IndexModel"""
    if isinstance(index_def, str):
        # 简单字段索引
        if index_def.startswith('-'):
            return IndexModel([(index_def[1:], DESCENDING)])
        else:
            return IndexModel([(index_def, ASCENDING)])
            
    elif isinstance(index_def, (list, tuple)):
        # 复合索引
        fields = []
        for field in index_def:
            if isinstance(field, str):
                if field.startswith('-'):
                    fields.append((field[1:], DESCENDING))
                else:
                    fields.append((field, ASCENDING))
        if fields:
            return IndexModel(fields)
            
    elif isinstance(index_def, dict):
        # 复杂索引定义
        fields = index_def.get('fields', [])
        options = {k: v for k, v in index_def.items() if k != 'fields'}
        
        # 关键：移除已弃用的background参数
        if 'background' in options:
            del options['background']
            
        if fields:
            return IndexModel(fields, **options)
    
    return None


def patch_mongoengine():
    """应用MongoEngine补丁以支持现代化MongoDB"""
    
    # 保存原始方法（如果需要回退）
    if not hasattr(Document, '_original_ensure_indexes'):
        Document._original_ensure_indexes = Document.ensure_indexes
    
    # 替换为现代化实现
    Document.ensure_indexes = classmethod(modern_ensure_indexes)
    
    app_log("🔧 已应用MongoEngine现代化补丁")


def unpatch_mongoengine():
    """移除MongoEngine补丁，恢复原始行为"""
    
    if hasattr(Document, '_original_ensure_indexes'):
        Document.ensure_indexes = Document._original_ensure_indexes
        delattr(Document, '_original_ensure_indexes')
        app_log("🔧 已移除MongoEngine现代化补丁")


def is_patched():
    """检查是否已应用补丁"""
    return hasattr(Document, '_original_ensure_indexes')


# 自动应用补丁的上下文管理器
class ModernMongoEngine:
    """现代化MongoEngine上下文管理器
    
    使用方式:
    with ModernMongoEngine():
        # 在这个上下文中，MongoEngine使用现代化的索引创建
        document.save()
    """
    
    def __enter__(self):
        if not is_patched():
            patch_mongoengine()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 通常我们保持补丁活跃，但如果需要可以取消
        pass


# 全局应用补丁的便捷函数
def apply_modern_mongoengine():
    """全局应用现代化MongoEngine补丁"""
    if not is_patched():
        patch_mongoengine()
        app_log("✅ 全局应用了现代化MongoEngine补丁")
    else:
        app_log("📝 现代化MongoEngine补丁已经应用")


# 自动应用补丁（当模块被导入时）
try:
    apply_modern_mongoengine()
except Exception as e:
    push_error(f"应用MongoEngine补丁失败: {e}")
