"""
现代化MongoDB索引管理器
解决MongoEngine与MongoDB 7.0+的兼容性问题，提供优雅的索引创建方案
"""

from typing import Dict, List, Any, Optional, Type, Union
from mongoengine import Document, get_db  # type: ignore
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from SimpleLLMFunc.logger import app_log, push_warning, push_error


class ModernIndexManager:
    """现代化的MongoDB索引管理器
    
    特点：
    1. 兼容MongoDB 7.0+
    2. 不使用已弃用的background参数
    3. 智能处理_id索引
    4. 支持复合索引和文本索引
    """
    
    def __init__(self):
        self.db = None
        self._initialized = False
    
    def initialize(self):
        """初始化索引管理器"""
        if self._initialized:
            return
            
        try:
            self.db = get_db()
            self._initialized = True
            app_log("✅ ModernIndexManager initialized successfully")
        except Exception as e:
            push_error(f"Failed to initialize ModernIndexManager: {e}")
            raise
    
    def create_indexes_for_document(self, document_class: Type[Document]) -> bool:
        """为指定的文档类创建索引
        
        Args:
            document_class: MongoEngine文档类
            
        Returns:
            bool: 是否成功创建所有索引
        """
        if not self._initialized:
            self.initialize()
            
        collection_name = document_class._get_collection_name()
        collection = self.db[collection_name]
        
        try:
            # 获取文档类的meta信息
            meta = getattr(document_class, '_meta', {})
            indexes = meta.get('indexes', [])
            
            if not indexes:
                app_log(f"📝 No custom indexes defined for {document_class.__name__}")
                return True
            
            # 转换MongoEngine索引定义为PyMongo IndexModel
            index_models = self._convert_mongoengine_indexes(indexes, document_class.__name__)
            
            if index_models:
                # 使用PyMongo直接创建索引，避免MongoEngine的兼容性问题
                result = collection.create_indexes(index_models)
                app_log(f"✅ Created {len(result)} indexes for {document_class.__name__}")
                return True
            else:
                app_log(f"📝 No valid indexes to create for {document_class.__name__}")
                return True
                
        except OperationFailure as e:
            # 处理MongoDB操作失败
            if "already exists" in str(e):
                app_log(f"📝 Indexes already exist for {document_class.__name__}")
                return True
            else:
                push_warning(f"MongoDB operation failed for {document_class.__name__}: {e}")
                return False
        except Exception as e:
            push_error(f"Failed to create indexes for {document_class.__name__}: {e}")
            return False
    
    def _convert_mongoengine_indexes(self, indexes: List[Union[str, tuple, dict]], 
                                   class_name: str) -> List[IndexModel]:
        """将MongoEngine索引定义转换为PyMongo IndexModel
        
        Args:
            indexes: MongoEngine格式的索引定义
            class_name: 文档类名称（用于日志）
            
        Returns:
            List[IndexModel]: PyMongo索引模型列表
        """
        index_models = []
        
        for index_def in indexes:
            try:
                index_model = self._convert_single_index(index_def)
                if index_model:
                    index_models.append(index_model)
            except Exception as e:
                push_warning(f"Failed to convert index {index_def} for {class_name}: {e}")
                continue
        
        return index_models
    
    def _convert_single_index(self, index_def: Union[str, tuple, dict]) -> Optional[IndexModel]:
        """转换单个索引定义
        
        Args:
            index_def: 单个索引定义
            
        Returns:
            Optional[IndexModel]: 转换后的索引模型，如果无效则返回None
        """
        if isinstance(index_def, str):
            # 简单字段索引: 'field_name' 或 '-field_name'
            if index_def.startswith('-'):
                # 降序索引
                field_name = index_def[1:]
                return IndexModel([(field_name, DESCENDING)])
            else:
                # 升序索引
                return IndexModel([(index_def, ASCENDING)])
                
        elif isinstance(index_def, tuple):
            # 复合索引: ('field1', 'field2') 或 ('field1', '-field2')
            fields = []
            for field in index_def:
                if isinstance(field, str):
                    if field.startswith('-'):
                        fields.append((field[1:], DESCENDING))
                    else:
                        fields.append((field, ASCENDING))
                else:
                    push_warning(f"Invalid field type in tuple index: {field}")
                    return None
            
            if fields:
                return IndexModel(fields)
                
        elif isinstance(index_def, dict):
            # 复杂索引定义: {'fields': [('field1', 1), ('field2', -1)], 'unique': True}
            fields = index_def.get('fields', [])
            options = {k: v for k, v in index_def.items() if k != 'fields'}
            
            # 移除已弃用的background参数
            if 'background' in options:
                del options['background']
                
            if fields:
                return IndexModel(fields, **options)
        
        return None
    
    def ensure_all_indexes(self, document_classes: List[Type[Document]]) -> Dict[str, bool]:
        """确保所有文档类的索引都已创建
        
        Args:
            document_classes: 文档类列表
            
        Returns:
            Dict[str, bool]: 每个文档类的索引创建结果
        """
        results = {}
        
        app_log("🚀 Starting modern index creation process...")
        
        for doc_class in document_classes:
            class_name = doc_class.__name__
            try:
                success = self.create_indexes_for_document(doc_class)
                results[class_name] = success
                
                if success:
                    app_log(f"✅ {class_name}: Index creation successful")
                else:
                    push_warning(f"⚠️ {class_name}: Index creation failed")
                    
            except Exception as e:
                push_error(f"❌ {class_name}: Index creation error: {e}")
                results[class_name] = False
        
        successful_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        app_log(f"🎯 Index creation completed: {successful_count}/{total_count} successful")
        
        return results
    
    def list_existing_indexes(self, document_class: Type[Document]) -> Dict[str, Any]:
        """列出现有的索引
        
        Args:
            document_class: 文档类
            
        Returns:
            Dict[str, Any]: 现有索引的信息
        """
        if not self._initialized:
            self.initialize()
            
        collection_name = document_class._get_collection_name()
        collection = self.db[collection_name]
        
        try:
            indexes = collection.list_indexes()
            index_info = {}
            
            for index in indexes:
                index_name = index.get('name', 'unknown')
                index_info[index_name] = {
                    'key': index.get('key', {}),
                    'unique': index.get('unique', False),
                    'sparse': index.get('sparse', False),
                    'background': index.get('background', None),  # 可能为None
                }
            
            return index_info
            
        except Exception as e:
            push_error(f"Failed to list indexes for {document_class.__name__}: {e}")
            return {}
    
    def drop_all_indexes(self, document_class: Type[Document], 
                        exclude_id: bool = True) -> bool:
        """删除所有索引（通常用于重建）
        
        Args:
            document_class: 文档类
            exclude_id: 是否排除_id索引（通常应该保留）
            
        Returns:
            bool: 是否成功
        """
        if not self._initialized:
            self.initialize()
            
        collection_name = document_class._get_collection_name()
        collection = self.db[collection_name]
        
        try:
            if exclude_id:
                # 获取所有索引名称，排除_id_
                indexes = collection.list_indexes()
                index_names = [idx['name'] for idx in indexes if idx['name'] != '_id_']
                
                for index_name in index_names:
                    collection.drop_index(index_name)
                    app_log(f"🗑️ Dropped index '{index_name}' for {document_class.__name__}")
            else:
                collection.drop_indexes()
                app_log(f"🗑️ Dropped all indexes for {document_class.__name__}")
            
            return True
            
        except Exception as e:
            push_error(f"Failed to drop indexes for {document_class.__name__}: {e}")
            return False


# 全局索引管理器实例
_index_manager: Optional[ModernIndexManager] = None


def get_index_manager() -> ModernIndexManager:
    """获取全局索引管理器实例"""
    global _index_manager
    if _index_manager is None:
        _index_manager = ModernIndexManager()
    return _index_manager


def create_modern_indexes(document_classes: List[Type[Document]]) -> Dict[str, bool]:
    """使用现代化方式创建索引的便捷函数
    
    Args:
        document_classes: 文档类列表
        
    Returns:
        Dict[str, bool]: 创建结果
    """
    manager = get_index_manager()
    return manager.ensure_all_indexes(document_classes)


def list_document_indexes(document_class: Type[Document]) -> Dict[str, Any]:
    """列出文档类的现有索引的便捷函数
    
    Args:
        document_class: 文档类
        
    Returns:
        Dict[str, Any]: 索引信息
    """
    manager = get_index_manager()
    return manager.list_existing_indexes(document_class)