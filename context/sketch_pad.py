from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Set, Tuple, override, cast
from datetime import datetime, timedelta
import threading
import json
import os
import hashlib
from context.schemas import (
    SketchPadItem,
    SketchPadStatistics,
    SketchPadListItem,
)
from redis import Redis

class SketchPadBackend(ABC):
    """
    SketchPad 基础接口
    定义了任何一种SketchPad后端实现都需要支持的操作

    任何一个sketch item都有如下的属性：

    value: Any = Field(..., description="存储的值")
    timestamp: datetime = Field(default_factory=datetime.now, description="创建时间")
    summary: Optional[str] = Field(default=None, description="内容摘要")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")
    access_count: int = Field(default=0, description="访问次数")
    last_accessed: Optional[datetime] = Field(default=None, description="最后访问时间")
    tags: Set[str] = Field(default_factory=set, description="标签集合")
    content_type: str = Field(default="text", description="内容类型")
    content_hash: Optional[str] = Field(default=None, description="内容哈希值")
    """

    @abstractmethod
    def __init__(
        self, 
        sketch_pad_id: str,
        file_path: Optional[str] = None,
    ):
        """
        初始化SketchPad后端

        Args:
            sketch_pad_id: 唯一标识符，用于标识SketchPad后端
            file_path: 文件路径，用于持久化数据
        """
        pass

    @abstractmethod
    async def set_item(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        summary: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> str:
        """设置键值对"""
        pass

    @abstractmethod
    def get_item(self, key: str) -> Optional[SketchPadItem]:
        """获取完整的项目信息"""
        pass

    @abstractmethod
    def get_value(self, key: str) -> Any:
        """仅获取值"""
        pass

    @abstractmethod
    def search_by_tags(
        self, tags: Set[str], match_all: bool = False
    ) -> List[Tuple[str, SketchPadItem]]:
        """按标签搜索"""
        pass

    @abstractmethod
    def search_by_content(
        self, query: str, limit: int = 5
    ) -> List[Tuple[str, SketchPadItem]]:
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

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """序列化为字典（用于保存到文件）"""
        pass

    @abstractmethod
    def deserialize(self, data: Dict[str, Any]) -> None:
        """从字典反序列化（用于从文件加载）"""
        pass

    @abstractmethod
    def persist(self) -> None:
        """持久化数据"""
        pass

    @abstractmethod
    def restore(self) -> None:
        """从持久化数据中恢复"""
        pass

    @abstractmethod
    def get_statistics(self) -> SketchPadStatistics:
        """获取统计信息"""
        pass

    @abstractmethod
    def list_items(self, include_value: bool = False) -> List[SketchPadListItem]:
        """列出所有项目"""
        pass


class RedisFileSketchPadBackend(SketchPadBackend):
    """
    RedisFileSketchPadBackend 结合Redis即时存储和文件系统持久化的SketchPad后端实现。

    特点：
    1. Redis提供高性能的即时访问
    2. 文件系统提供可靠的持久化
    3. 支持自动同步和恢复
    4. 利用Redis AOF + RDB机制
    """

    @override
    def __init__(
        self,
        sketch_pad_id: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        file_path: Optional[str] = None,
    ):
        """
        初始化RedisFileSketchPadBackend

        Args:
            sketch_pad_id: SketchPad唯一标识符
            redis_host: Redis主机
            redis_port: Redis端口
            redis_db: Redis数据库
            file_path: 文件路径，用于持久化数据
        """

        self.sketch_pad_id = sketch_pad_id
        self.file_path = file_path or f"sketch_pads/sketch_{sketch_pad_id}.json"
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis: Redis = Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db)

        self._lock = threading.RLock()
        self._restore_from_storage()

    # ---- Redis typed helpers (to avoid Awaitable union types in stubs) ----
    def _redis_get(self, key: str) -> Optional[bytes]:
        raw = cast(Any, self.redis.get(key))
        return cast(Optional[bytes], raw)

    def _redis_keys(self, pattern: str) -> List[bytes]:
        raw = cast(Any, self.redis.keys(pattern))
        return cast(List[bytes], raw)

    def _redis_smembers(self, key: str) -> Set[bytes]:
        raw = cast(Any, self.redis.smembers(key))
        return cast(Set[bytes], raw)

    def _redis_delete(self, *keys: Union[str, bytes]) -> int:
        raw = cast(Any, self.redis.delete(*keys))
        return cast(int, raw)

    def _redis_exists(self, key: str) -> int:
        raw = cast(Any, self.redis.exists(key))
        return cast(int, raw)

    def _restore_from_storage(self) -> None:
        """从存储中恢复"""
        with self._lock:
            if self.file_path is None:
                return
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.deserialize(data)
                except Exception as e:
                    print(f"Warning: Failed to restore from file: {e}")

    def _get_redis_key(self, key: str) -> str:
        """获取Redis键名"""
        return f"sketch_pad:{self.sketch_pad_id}:{key}"

    def _get_content_hash(self, value: Any) -> str:
        """计算内容的哈希值"""
        content_str = json.dumps(value, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()

    @override
    async def set_item(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        summary: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> str:
        """
        设置键值对

        Args:
            key: 键
            value: 值
            ttl: 过期时间（秒）
            summary: 摘要
            tags: 标签
        """
        with self._lock:
            # 创建SketchPadItem
            item = SketchPadItem(
                value=value,
                timestamp=datetime.now(),
                summary=summary,
                tags=tags or set(),
                expires_at=datetime.now() + timedelta(seconds=ttl) if ttl else None,
                content_hash=self._get_content_hash(value),
            )

            # 存储到Redis
            item_json = item.model_dump_json()
            redis_key = self._get_redis_key(key)
            self.redis.set(redis_key, item_json)
            
            # 设置过期时间
            if ttl:
                self.redis.expire(redis_key, ttl)

            # 更新标签索引
            if tags:
                for tag in tags:
                    tag_key = self._get_redis_key(f"tag:{tag}")
                    self.redis.sadd(tag_key, key)

            return key

    @override
    def get_item(self, key: str) -> Optional[SketchPadItem]:
        """获取完整的项目信息"""
        with self._lock:
            item_json_opt = self._redis_get(self._get_redis_key(key))
            if item_json_opt is None:
                return None
            
            try:
                item_bytes = cast(bytes, item_json_opt)
                item = SketchPadItem.model_validate_json(item_bytes)
                # 更新访问信息
                item.access_count += 1
                item.last_accessed = datetime.now()
                
                # 更新Redis中的访问信息
                item_json_str: str = item.model_dump_json()
                self.redis.set(self._get_redis_key(key), item_json_str)
                
                return item
            except Exception as e:
                print(f"Warning: Failed to deserialize item: {e}")
                return None

    @override
    def get_value(self, key: str) -> Any:
        """仅获取值"""
        item = self.get_item(key)
        return item.value if item else None

    @override
    def search_by_tags(
        self, tags: Set[str], match_all: bool = False
    ) -> List[Tuple[str, SketchPadItem]]:
        """按标签搜索"""
        with self._lock:
            results: List[Tuple[str, SketchPadItem]] = []
            
            if match_all:
                # 必须匹配所有标签
                if not tags:
                    return results
                
                # 获取第一个标签的所有键
                first_tag = list(tags)[0]
                tag_key = self._get_redis_key(f"tag:{first_tag}")
                candidate_keys = self._redis_smembers(tag_key)
                
                # 检查每个候选键是否包含所有标签
                for cand_key in candidate_keys:
                    cand_key_str: str = cand_key.decode('utf-8')
                    item = self.get_item(cand_key_str)
                    if item and tags.issubset(item.tags):
                        results.append((cand_key_str, item))
            else:
                # 匹配任意标签
                for tag in tags:
                    tag_key = self._get_redis_key(f"tag:{tag}")
                    keys = self._redis_smembers(tag_key)
                    
                    for member_key in keys:
                        member_key_str: str = member_key.decode('utf-8')
                        item = self.get_item(member_key_str)
                        if item and (member_key_str, item) not in results:
                            results.append((member_key_str, item))
            
            return results

    @override
    def search_by_content(
        self, query: str, limit: int = 5
    ) -> List[Tuple[str, SketchPadItem]]:
        """基于内容的简单搜索"""
        with self._lock:
            results: List[Tuple[str, SketchPadItem]] = []
            query_lower = query.lower()
            
            # 获取所有键，但过滤掉标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            
            for key in all_keys:
                redis_key_string: str = key.decode('utf-8')
                # 过滤掉标签索引键
                if ":tag:" in redis_key_string:
                    continue
                
                # 提取原始键名
                original_key = redis_key_string.split(":", 2)[-1]
                
                item = self.get_item(original_key)
                if item:
                    # 搜索值、摘要和标签
                    searchable_text = ""
                    if isinstance(item.value, str):
                        searchable_text += item.value + " "
                    if item.summary:
                        searchable_text += item.summary + " "
                    if item.tags:
                        searchable_text += " ".join(item.tags) + " "
                    
                    if query_lower in searchable_text.lower():
                        results.append((original_key, item))
                        if len(results) >= limit:
                            break
            
            return results

    @override
    def delete(self, key: str) -> bool:
        """删除键值对"""
        with self._lock:
            # 获取项目以删除标签索引
            item = self.get_item(key)
            if item and item.tags:
                for tag in item.tags:
                    tag_key = self._get_redis_key(f"tag:{tag}")
                    self.redis.srem(tag_key, key)
            
            # 删除主键
            redis_key = self._get_redis_key(key)
            result = self._redis_delete(redis_key)
            return result > 0

    @override
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            exists_count = self._redis_exists(self._get_redis_key(key))
            return exists_count > 0

    @override
    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """获取所有键名"""
        with self._lock:
            redis_pattern = self._get_redis_key(pattern or "*")
            keys = self._redis_keys(redis_pattern)
            
            # 提取原始键名
            result: List[str] = []
            for key in keys:
                redis_key_str_list: str = key.decode('utf-8')
                original_key = redis_key_str_list.split(":", 2)[-1]
                result.append(original_key)
            
            return result

    @override
    def clear(self) -> None:
        """清空所有数据"""
        with self._lock:
            # 获取所有键
            pattern = self._get_redis_key("*")
            keys = self._redis_keys(pattern)
            
            # 删除所有键
            if keys:
                self._redis_delete(*keys)

    @override
    def serialize(self) -> Dict[str, Any]:
        """序列化为字典（用于保存到文件）"""
        with self._lock:
            data: Dict[str, Any] = {
                "sketch_pad_id": self.sketch_pad_id,
                "items": {},
                "serialization_timestamp": datetime.now().isoformat(),
            }
            
            # 序列化所有项目，但过滤掉标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            
            for key in all_keys:
                redis_key_str_ser: str = key.decode('utf-8')
                # 过滤掉标签索引键
                if ":tag:" in redis_key_str_ser:
                    continue
                
                # 提取原始键名
                original_key = redis_key_str_ser.split(":", 2)[-1]
                
                item = self.get_item(original_key)
                if item:
                    data["items"][original_key] = item.model_dump()
            
            return data

    @override
    def deserialize(self, data: Dict[str, Any]) -> None:
        """从字典反序列化（用于从文件加载）"""
        with self._lock:
            if "items" in data:
                for key, item_data in data["items"].items():
                    try:
                        item = SketchPadItem(**item_data)
                        item_json = item.model_dump_json()
                        self.redis.set(self._get_redis_key(key), item_json)
                        
                        # 恢复标签索引
                        if item.tags:
                            for tag in item.tags:
                                tag_key = self._get_redis_key(f"tag:{tag}")
                                self.redis.sadd(tag_key, key)
                    except Exception as e:
                        print(f"Warning: Failed to deserialize item {key}: {e}")

    @override
    def persist(self) -> None:
        """持久化数据"""
        try:
            # 确保目录存在
            dir_path = os.path.dirname(self.file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # 序列化数据
            data = self.serialize()
            
            # 写入文件
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Failed to persist sketch pad: {e}")

    @override
    def restore(self) -> None:
        """从持久化数据中恢复"""
        if not os.path.exists(self.file_path):
            return
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.deserialize(data)
        except Exception as e:
            print(f"Warning: Failed to restore sketch pad: {e}")

    def get_statistics(self) -> SketchPadStatistics:
        """获取统计信息"""
        with self._lock:
            # 只获取实际的数据键，不包括标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            data_keys: List[str] = []
            
            for key in all_keys:
                redis_key_str_stats: str = key.decode('utf-8')
                # 过滤掉标签索引键
                if not redis_key_str_stats.endswith(":tag:") and ":tag:" not in redis_key_str_stats:
                    original_key = redis_key_str_stats.split(":", 2)[-1]
                    data_keys.append(original_key)
            
            total_items = len(data_keys)
            total_accesses = 0
            items_with_summary = 0
            popular_tags: Dict[str, int] = {}
            content_types: Dict[str, int] = {}
            
            for data_key in data_keys:
                item = self.get_item(data_key)
                if item:
                    total_accesses += item.access_count
                    if item.summary:
                        items_with_summary += 1
                    
                    # 统计标签
                    for tag in item.tags:
                        popular_tags[tag] = popular_tags.get(tag, 0) + 1
                    
                    # 统计内容类型
                    content_types[item.content_type] = content_types.get(item.content_type, 0) + 1
            
            avg_access_per_item = total_accesses / total_items if total_items > 0 else 0
            memory_usage_percent = (total_items / 1000) * 100  # 假设最大1000项
            
            return SketchPadStatistics(
                total_items=total_items,
                max_items=1000,
                items_with_summary=items_with_summary,
                total_accesses=total_accesses,
                popular_tags=popular_tags,
                content_types=content_types,
                avg_access_per_item=avg_access_per_item,
                memory_usage_percent=memory_usage_percent,
            )

    def list_items(self, include_value: bool = False) -> List[SketchPadListItem]:
        """列出所有项目"""
        with self._lock:
            items: List[SketchPadListItem] = []
            # 获取所有键，但过滤掉标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            
            for key in all_keys:
                redis_key_str_list_items: str = key.decode('utf-8')
                # 过滤掉标签索引键
                if ":tag:" in redis_key_str_list_items:
                    continue
                
                # 提取原始键名
                original_key = redis_key_str_list_items.split(":", 2)[-1]
                
                item = self.get_item(original_key)
                if item:
                    list_item = SketchPadListItem(
                        key=original_key,
                        summary=item.summary,
                        timestamp=item.timestamp.isoformat(),
                        tags=list(item.tags),
                        content_type=item.content_type,
                        access_count=item.access_count,
                        content_hash=item.content_hash,
                        value=item.value if include_value else None,
                    )
                    items.append(list_item)
            
            return items

