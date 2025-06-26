from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import threading
import json
import uuid
import hashlib
from pathlib import Path
from SimpleLLMFunc import llm_function, OpenAICompatible
from config.config import get_config


@dataclass
class SketchPadItem:
    """SketchPad 存储项的数据结构"""
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    summary: Optional[str] = None
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)
    content_type: str = "text"
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.timestamp
        if self.content_hash is None:
            self.content_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """计算内容哈希"""
        content_str = str(self.value)
        return hashlib.md5(content_str.encode()).hexdigest()[:8]
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return self.expires_at is not None and datetime.now() > self.expires_at
    
    def update_access(self):
        """更新访问信息（用于LRU缓存）"""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'summary': self.summary,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'tags': list(self.tags),
            'content_type': self.content_type,
            'content_hash': self.content_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SketchPadItem':
        """从字典创建实例"""
        # 处理时间字段
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if data.get('last_accessed'):
            data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        
        # 处理tags
        if data.get('tags'):
            data['tags'] = set(data['tags'])
        
        return cls(**data)


class SketchPadInterface(ABC):
    """SketchPad 基础接口"""
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                  summary: Optional[str] = None, tags: Optional[Set[str]] = None,
                  auto_summarize: bool = True) -> str:
        """设置键值对"""
        pass
    
    @abstractmethod
    def get(self, key: str) -> Optional[SketchPadItem]:
        """获取完整的项目信息"""
        pass
    
    @abstractmethod
    def get_value(self, key: str) -> Any:
        """仅获取值"""
        pass
    
    @abstractmethod
    def search_by_tags(self, tags: Set[str], match_all: bool = False) -> List[Tuple[str, SketchPadItem]]:
        """按标签搜索"""
        pass
    
    @abstractmethod
    def search_by_content(self, query: str, limit: int = 5) -> List[Tuple[str, SketchPadItem]]:
        """基于内容的简单搜索"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除键值对"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass
    
    @abstractmethod
    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """获取所有键名"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空所有数据"""
        pass


class InMemorySketchPad(SketchPadInterface):
    """内存实现的 SketchPad，支持 LRU 缓存"""
    
    def __init__(self, 
                 llm_interface: Optional[OpenAICompatible] = None,
                 max_items: int = 1000,
                 auto_cleanup: bool = True, 
                 cleanup_interval: int = 300):
        """
        Args:
            llm_interface: LLM接口，用于摘要生成
            max_items: 最大存储项目数，用于LRU缓存
            auto_cleanup: 是否自动清理过期数据
            cleanup_interval: 清理间隔（秒）
        """
        self._storage: Dict[str, SketchPadItem] = {}
        self._lock = threading.RLock()
        self.llm_interface = llm_interface
        self.max_items = max_items
        self._auto_cleanup = auto_cleanup
        self._cleanup_interval = cleanup_interval
        
        # 初始化摘要生成函数
        self._summarize_func = None
        if self.llm_interface:
            self._summarize_func = self._create_summarize_function()
        
        if auto_cleanup:
            self._start_cleanup_timer()
    
    def _create_summarize_function(self):
        """创建摘要生成函数"""
        if self.llm_interface is None:
            return None
            
        @llm_function(
            llm_interface=self.llm_interface,
            timeout=30
        )
        def generate_summary(content: str) -> str:
            """Generate a concise summary of the content for SketchPad storage.
            
            Args:
                content: The content to summarize (max 2000 chars)
                
            Returns:
                str: A brief summary (max 150 characters)
                
            Rules:
            - Keep summary under 150 characters
            - Focus on key information and purpose
            - Use simple, clear language
            - For code: mention what it does and main components
            - For data: mention what it contains and structure
            - For text: capture main topic and intent
            """
            return ""  # 这个会被llm_function装饰器替换
        
        return generate_summary
    
    def _start_cleanup_timer(self):
        """启动清理定时器"""
        def cleanup():
            self._cleanup_expired()
            self._enforce_lru_limit()
            if self._auto_cleanup:
                timer = threading.Timer(self._cleanup_interval, cleanup)
                timer.daemon = True
                timer.start()
        
        timer = threading.Timer(self._cleanup_interval, cleanup)
        timer.daemon = True
        timer.start()
    
    def _cleanup_expired(self):
        """清理过期数据"""
        with self._lock:
            expired_keys = [key for key, item in self._storage.items() if item.is_expired()]
            for key in expired_keys:
                del self._storage[key]
    
    def _enforce_lru_limit(self):
        """强制执行LRU限制"""
        with self._lock:
            if len(self._storage) <= self.max_items:
                return
            
            # 按最后访问时间排序，删除最旧的项目
            items_by_access = sorted(
                self._storage.items(),
                key=lambda x: x[1].last_accessed or x[1].timestamp
            )
            
            # 删除最旧的项目直到达到限制
            to_delete = len(self._storage) - self.max_items
            for i in range(to_delete):
                key = items_by_access[i][0]
                del self._storage[key]
    
    async def _generate_summary_if_needed(self, value: Any, summary: Optional[str], auto_summarize: bool) -> Optional[str]:
        """生成摘要（如果需要的话）"""
        if summary is not None:
            return summary
        
        if not auto_summarize or not self.llm_interface or not self._summarize_func:
            return None
        
        try:
            content = str(value)
            if len(content) > 100:  # 只对较长内容生成摘要
                # 限制输入长度以控制成本
                truncated_content = content[:2000] + ("..." if len(content) > 2000 else "")
                return self._summarize_func(truncated_content)
        except Exception as e:
            print(f"Warning: Failed to generate summary: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                  summary: Optional[str] = None, tags: Optional[Set[str]] = None,
                  auto_summarize: bool = True) -> str:
        """设置键值对"""
        with self._lock:
            # 生成唯一键名
            original_key = key
            counter = 1
            while key in self._storage:
                key = f"{original_key}_{counter}"
                counter += 1
            
            # 设置过期时间
            expires_at = None
            if ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl)
            
            # 生成摘要
            summary = await self._generate_summary_if_needed(value, summary, auto_summarize)
            
            # 推断内容类型
            content_type = "text"
            if isinstance(value, dict):
                content_type = "json"
            elif isinstance(value, list):
                content_type = "list"
            elif "import" in str(value) and ("def " in str(value) or "class " in str(value)):
                content_type = "code"
            
            # 创建项目
            item = SketchPadItem(
                value=value,
                timestamp=datetime.now(),
                summary=summary,
                expires_at=expires_at,
                tags=tags or set(),
                content_type=content_type
            )
            
            self._storage[key] = item
            
            # 强制执行LRU限制
            self._enforce_lru_limit()
            
            return key
    
    def get(self, key: str) -> Optional[SketchPadItem]:
        """获取完整的项目信息"""
        with self._lock:
            item = self._storage.get(key)
            if item is None:
                return None
            
            if item.is_expired():
                del self._storage[key]
                return None
            
            item.update_access()
            return item
    
    def get_value(self, key: str) -> Any:
        """仅获取值"""
        item = self.get(key)
        return item.value if item else None
    
    def search_by_tags(self, tags: Set[str], match_all: bool = False) -> List[Tuple[str, SketchPadItem]]:
        """按标签搜索"""
        results = []
        with self._lock:
            self._cleanup_expired()
            
            for key, item in self._storage.items():
                if match_all:
                    if tags.issubset(item.tags):
                        results.append((key, item))
                        item.update_access()
                else:
                    if tags.intersection(item.tags):
                        results.append((key, item))
                        item.update_access()
        
        return results
    
    def search_by_content(self, query: str, limit: int = 5) -> List[Tuple[str, SketchPadItem]]:
        """基于内容的简单搜索"""
        results = []
        query_lower = query.lower()
        
        with self._lock:
            self._cleanup_expired()
            
            for key, item in self._storage.items():
                # 搜索key、summary和value的文本内容
                searchable_text = f"{key} {item.summary or ''} {str(item.value)[:500]}".lower()
                
                if query_lower in searchable_text:
                    results.append((key, item))
                    item.update_access()
        
        # 按访问次数和时间排序
        results.sort(key=lambda x: (x[1].access_count, x[1].timestamp), reverse=True)
        return results[:limit]
    
    def delete(self, key: str) -> bool:
        """删除键值对"""
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            item = self._storage.get(key)
            if item is None:
                return False
            
            if item.is_expired():
                del self._storage[key]
                return False
            
            return True
    
    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """获取所有键名"""
        with self._lock:
            self._cleanup_expired()
            
            if pattern is None:
                return list(self._storage.keys())
            
            import fnmatch
            return [key for key in self._storage.keys() if fnmatch.fnmatch(key, pattern)]
    
    def clear(self) -> None:
        """清空所有数据"""
        with self._lock:
            self._storage.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            self._cleanup_expired()
            
            total_items = len(self._storage)
            items_with_summary = sum(1 for item in self._storage.values() if item.summary is not None)
            total_accesses = sum(item.access_count for item in self._storage.values())
            
            # 按标签统计
            tag_counts = {}
            for item in self._storage.values():
                for tag in item.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # 按内容类型统计
            type_counts = {}
            for item in self._storage.values():
                type_counts[item.content_type] = type_counts.get(item.content_type, 0) + 1
            
            return {
                'total_items': total_items,
                'max_items': self.max_items,
                'items_with_summary': items_with_summary,
                'total_accesses': total_accesses,
                'popular_tags': dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
                'content_types': type_counts,
                'avg_access_per_item': total_accesses / total_items if total_items > 0 else 0,
                'memory_usage_percent': (total_items / self.max_items) * 100
            }


class SmartSketchPad:
    """智能 SketchPad 门面类"""
    
    def __init__(self, backend: Optional[SketchPadInterface] = None, 
                 llm_interface: Optional[OpenAICompatible] = None,
                 max_items: int = 500):
        if backend is None:
            backend = InMemorySketchPad(
                llm_interface=llm_interface,
                max_items=max_items
            )
        self.backend = backend
    
    async def store(self, value: Any, key: Optional[str] = None, ttl: Optional[int] = None,
                   summary: Optional[str] = None, tags: Optional[Union[Set[str], List[str]]] = None,
                   auto_summarize: bool = True) -> str:
        """智能存储"""
        if key is None:
            # 自动生成语义化的键名
            content_preview = str(value)[:30].replace('\n', ' ').replace(' ', '_')
            # 清理非法字符
            import re
            content_preview = re.sub(r'[^\w\-_]', '_', content_preview)
            key = f"auto_{content_preview}_{uuid.uuid4().hex[:6]}"
        
        if isinstance(tags, list):
            tags = set(tags)
        
        return await self.backend.set(key, value, ttl, summary, tags, auto_summarize)
    
    def retrieve(self, key: str) -> Any:
        """获取值"""
        return self.backend.get_value(key)
    
    def get_item(self, key: str) -> Optional[SketchPadItem]:
        """获取完整项目信息"""
        return self.backend.get(key)
    
    def find_by_tags(self, tags: Union[Set[str], List[str], str], match_all: bool = False) -> List[Dict[str, Any]]:
        """按标签查找"""
        if isinstance(tags, str):
            tags = {tags}
        elif isinstance(tags, list):
            tags = set(tags)
        
        results = self.backend.search_by_tags(tags, match_all)
        return [
            {
                'key': key,
                'value': item.value,
                'summary': item.summary,
                'timestamp': item.timestamp.isoformat(),
                'tags': list(item.tags),
                'content_type': item.content_type,
                'access_count': item.access_count
            }
            for key, item in results
        ]
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索内容"""
        results = self.backend.search_by_content(query, limit)
        return [
            {
                'key': key,
                'value': item.value,
                'summary': item.summary,
                'timestamp': item.timestamp.isoformat(),
                'tags': list(item.tags),
                'content_type': item.content_type,
                'access_count': item.access_count
            }
            for key, item in results
        ]
    
    def list_all(self, include_details: bool = False) -> List[Dict[str, Any]]:
        """列出所有项目"""
        keys = self.backend.keys()
        if not include_details:
            return [{'key': key} for key in keys]
        
        results = []
        for key in keys:
            item = self.backend.get(key)
            if item:
                results.append({
                    'key': key,
                    'summary': item.summary,
                    'timestamp': item.timestamp.isoformat(),
                    'tags': list(item.tags),
                    'content_type': item.content_type,
                    'access_count': item.access_count,
                    'content_hash': item.content_hash
                })
        
        # 按时间排序（最新的在前）
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        return results
    
    def delete(self, key: str) -> bool:
        """删除项目"""
        return self.backend.delete(key)
    
    def clear_all(self) -> None:
        """清空所有数据"""
        self.backend.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if hasattr(self.backend, 'get_statistics'):
            return self.backend.get_statistics()  # type: ignore
        else:
            return {'total_items': len(self.backend.keys())}


# 全局实例管理
_global_sketch_pad: Optional[SmartSketchPad] = None

def get_global_sketch_pad() -> SmartSketchPad:
    """获取全局 SketchPad 实例"""
    global _global_sketch_pad
    if _global_sketch_pad is None:
        try:
            config = get_config()
            _global_sketch_pad = SmartSketchPad(
                llm_interface=config.BASIC_INTERFACE,
                max_items=500
            )
        except Exception:
            # 如果配置加载失败，使用无LLM的版本
            _global_sketch_pad = SmartSketchPad(max_items=500)
    return _global_sketch_pad

def initialize_sketch_pad(llm_interface: Optional[OpenAICompatible] = None,
                         max_items: int = 500) -> SmartSketchPad:
    """初始化全局 SketchPad 实例"""
    global _global_sketch_pad
    if llm_interface is None:
        try:
            llm_interface = get_config().BASIC_INTERFACE
        except Exception:
            pass  # 如果配置失败，使用None
    
    _global_sketch_pad = SmartSketchPad(
        llm_interface=llm_interface,
        max_items=max_items
    )
    return _global_sketch_pad
