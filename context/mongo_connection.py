"""
MongoDB连接管理
提供MongoDB连接的初始化、配置和管理功能
"""

import os
import threading
import functools
from typing import Optional, Dict, Any, Callable
from mongoengine import connect, disconnect, ConnectionFailure  # type: ignore
from pymongo.errors import ServerSelectionTimeoutError
from SimpleLLMFunc.logger import app_log, push_error, push_warning
from config.config import get_config



class MongoConnectionManager:
    """MongoDB连接管理器"""
    
    _instance: Optional['MongoConnectionManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化连接管理器"""
        if hasattr(self, '_initialized'):
            return
            
        self.config = get_config()
        self._connection = None
        self._is_connected = False
        self._connection_params: Dict[str, Any] = {}
        self._initialized = True
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """获取MongoDB连接参数"""
        return {
            'host': getattr(self.config, 'MONGO_HOST', 'localhost'),
            'port': int(getattr(self.config, 'MONGO_PORT', 27017)),
            'db': getattr(self.config, 'MONGO_DATABASE', 'simpleagent'),
            'username': getattr(self.config, 'MONGO_USERNAME', None),
            'password': getattr(self.config, 'MONGO_PASSWORD', None),
            'authentication_source': getattr(self.config, 'MONGO_AUTH_SOURCE', 'admin'),
            'connect': True,
            'serverSelectionTimeoutMS': 5000,  # 5秒超时
            'socketTimeoutMS': 30000,  # 30秒socket超时
            'maxPoolSize': 50,
            'minPoolSize': 5,
            'retryWrites': True,
            'w': 'majority',  # 写关注级别
        }
    
    def connect_to_mongo(self, force_reconnect: bool = False) -> bool:
        """
        连接到MongoDB
        
        Args:
            force_reconnect: 是否强制重连
            
        Returns:
            bool: 连接是否成功
        """
        if self._is_connected and not force_reconnect:
            return True
        
        try:
            # 如果已连接，先断开
            if self._is_connected:
                self.disconnect_from_mongo()
            
            # 获取连接参数
            params = self._get_connection_params()
            self._connection_params = params.copy()
            
            # 构建连接URI
            if params['username'] and params['password']:
                uri = (
                    f"mongodb://{params['username']}:{params['password']}"
                    f"@{params['host']}:{params['port']}/{params['db']}"
                    f"?authSource={params['authentication_source']}"
                )
            else:
                uri = f"mongodb://{params['host']}:{params['port']}/{params['db']}"
            
            app_log(f"正在连接MongoDB: {params['host']}:{params['port']}/{params['db']}")
            
            # 建立连接
            self._connection = connect(
                db=params['db'],
                host=uri,
                serverSelectionTimeoutMS=params['serverSelectionTimeoutMS'],
                socketTimeoutMS=params['socketTimeoutMS'],
                maxPoolSize=params['maxPoolSize'],
                minPoolSize=params['minPoolSize'],
                retryWrites=params['retryWrites'],
                w=params['w']
            )
            
            # 测试连接
            from mongoengine.connection import get_connection  # type: ignore
            conn = get_connection()
            conn.admin.command('ping')
            
            self._is_connected = True
            app_log("✅ MongoDB连接成功")
            
            # 应用现代化MongoEngine补丁
            try:
                from context.mongo_patch import apply_modern_mongoengine
                apply_modern_mongoengine()
            except Exception as patch_error:
                push_warning(f"应用MongoEngine现代化补丁失败: {patch_error}")
            
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            push_error(f"MongoDB连接失败: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            push_error(f"MongoDB连接异常: {e}")
            self._is_connected = False
            return False
    
    def disconnect_from_mongo(self):
        """断开MongoDB连接"""
        try:
            if self._is_connected:
                disconnect()
                self._is_connected = False
                self._connection = None
                app_log("MongoDB连接已断开")
        except Exception as e:
            push_warning(f"断开MongoDB连接时出错: {e}")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        if not self._is_connected:
            return False
        
        try:
            from mongoengine.connection import get_connection  # type: ignore
            conn = get_connection()
            conn.admin.command('ping')
            return True
        except:
            self._is_connected = False
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return {
            'is_connected': self._is_connected,
            'connection_params': self._connection_params.copy() if self._connection_params else {},
            'database': self._connection_params.get('db') if self._connection_params else None
        }
    
    def ensure_connection(self) -> bool:
        """确保连接可用"""
        if not self.is_connected():
            return self.connect_to_mongo()
        return True
    
    def create_indexes(self):
        """使用现代化方式创建数据库索引"""
        try:
            from context.mongo_schemas import (
                ContextDocument, SketchPadDocument, ConversationDocument,
                ContextStatisticsDocument, SystemLogDocument
            )
            from context.modern_mongo_index import create_modern_indexes
            
            app_log("🚀 正在使用现代化方式创建MongoDB索引...")
            
            # 使用现代化索引管理器创建索引
            document_classes = [
                ContextDocument, SketchPadDocument, ConversationDocument,
                ContextStatisticsDocument, SystemLogDocument
            ]
            
            results = create_modern_indexes(document_classes)
            
            # 统计结果
            successful_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            if successful_count == total_count:
                app_log("✅ 所有MongoDB索引创建成功")
            else:
                push_warning(f"⚠️ 部分索引创建失败: {successful_count}/{total_count} 成功")
                
            # 详细日志
            for class_name, success in results.items():
                if not success:
                    push_warning(f"索引创建失败: {class_name}")
            
        except Exception as e:
            push_error(f"现代化索引创建失败: {e}")
            # 如果现代化方式失败，回退到传统方式（但仍然处理兼容性问题）
            self._fallback_create_indexes()
    
    def _fallback_create_indexes(self):
        """回退的索引创建方法（兼容性处理）"""
        try:
            from context.mongo_schemas import (
                ContextDocument, SketchPadDocument, ConversationDocument,
                ContextStatisticsDocument, SystemLogDocument
            )
            
            app_log("🔄 使用回退方式创建MongoDB索引...")
            
            # 为每个文档类创建索引（传统方式，但处理兼容性问题）
            for doc_class in [
                ContextDocument, SketchPadDocument, ConversationDocument,
                ContextStatisticsDocument, SystemLogDocument
            ]:
                try:
                    doc_class.ensure_indexes()
                    app_log(f"✅ 回退方式成功创建索引: {doc_class.__name__}")
                except Exception as idx_error:
                    error_msg = str(idx_error)
                    # 处理已知的兼容性问题
                    if ("background" in error_msg and "_id" in error_msg) or \
                       ("InvalidIndexSpecificationOption" in error_msg):
                        push_warning(f"⚠️ 忽略兼容性问题 ({doc_class.__name__}): 索引可能已存在")
                        continue
                    else:
                        push_error(f"❌ 回退方式索引创建失败 ({doc_class.__name__}): {error_msg}")
                        # 不抛出异常，继续处理其他文档类
            
            app_log("🔄 回退方式索引创建完成")
            
        except Exception as e:
            push_error(f"回退索引创建也失败了: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.is_connected():
                return {
                    'status': 'unhealthy',
                    'message': 'Not connected to MongoDB',
                    'is_connected': False
                }
            
            from mongoengine.connection import get_connection  # type: ignore
            conn = get_connection()
            
            # 执行ping命令
            ping_result = conn.admin.command('ping')
            
            # 获取服务器状态
            server_status = conn.admin.command('serverStatus')
            
            return {
                'status': 'healthy',
                'message': 'MongoDB connection is healthy',
                'is_connected': True,
                'ping': ping_result,
                'server_info': {
                    'version': server_status.get('version'),
                    'uptime': server_status.get('uptime'),
                    'connections': server_status.get('connections', {}),
                },
                'database': self._connection_params.get('db')
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Health check failed: {str(e)}',
                'is_connected': False,
                'error': str(e)
            }


# 全局连接管理器实例
_mongo_manager: Optional[MongoConnectionManager] = None
_manager_lock = threading.Lock()


def get_mongo_manager() -> MongoConnectionManager:
    """获取全局MongoDB连接管理器实例"""
    global _mongo_manager
    if _mongo_manager is None:
        with _manager_lock:
            if _mongo_manager is None:
                _mongo_manager = MongoConnectionManager()
    return _mongo_manager


def init_mongo_connection() -> bool:
    """初始化MongoDB连接"""
    manager = get_mongo_manager()
    success = manager.connect_to_mongo()
    if success:
        manager.create_indexes()
    return success


def ensure_mongo_connection() -> bool:
    """确保MongoDB连接可用"""
    manager = get_mongo_manager()
    return manager.ensure_connection()


def close_mongo_connection():
    """关闭MongoDB连接"""
    manager = get_mongo_manager()
    manager.disconnect_from_mongo()


def mongo_health_check() -> Dict[str, Any]:
    """MongoDB健康检查"""
    manager = get_mongo_manager()
    return manager.health_check()


# 上下文管理器支持
class MongoConnection:
    """MongoDB连接上下文管理器"""
    
    def __init__(self, auto_connect: bool = True):
        self.auto_connect = auto_connect
        self.manager = get_mongo_manager()
    
    def __enter__(self):
        if self.auto_connect:
            if not self.manager.ensure_connection():
                raise ConnectionError("无法连接到MongoDB")
        return self.manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 不自动断开连接，保持连接池
        pass
