"""
基于MongoDB持久化和Redis缓存的SketchPad后端实现
"""

import json
import threading
from typing import Any, Dict, List, Optional, Union, Set, Tuple, override, cast
from datetime import datetime, timedelta
import hashlib
from redis import Redis
from mongoengine.errors import DoesNotExist, ValidationError  # type: ignore

from context.schemas import SketchPadItem, SketchPadStatistics, SketchPadListItem
from context.sketch_pad import SketchPadBackend
from context.mongo_schemas import (
    SketchPadDocument, SketchPadItemDocument, 
    serialize_for_mongo, deserialize_from_mongo
)
from context.mongo_connection import ensure_mongo_connection
from SimpleLLMFunc.logger import push_warning, push_error, app_log


class RedisMongoSketchPadBackend(SketchPadBackend):
    """
    基于Redis缓存和MongoDB持久化的SketchPad后端实现
    
    特点：
    1. Redis提供高性能的即时访问和缓存
    2. MongoDB提供可靠的持久化存储和复杂查询能力
    3. 支持自动同步和故障恢复
    4. 提供丰富的搜索和分析功能
    """

    @override
    def __init__(
        self,
        sketch_pad_id: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        file_path: Optional[str] = None,  # 保持兼容性，但不使用
    ):
        """
        初始化Redis MongoDB SketchPad后端

        Args:
            sketch_pad_id: SketchPad唯一标识符
            redis_host: Redis主机
            redis_port: Redis端口
            redis_db: Redis数据库
            file_path: 文件路径（保持兼容性，实际不使用）
        """
        self.sketch_pad_id = sketch_pad_id
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_password = redis_password
        
        # Redis连接
        self.redis: Redis = Redis(
            host=self.redis_host, 
            port=self.redis_port, 
            db=self.redis_db,
            decode_responses=True,
            password=self.redis_password
        )

        self._lock = threading.RLock()
        
        # 确保MongoDB连接
        if not ensure_mongo_connection():
            push_error("无法连接到MongoDB")
            raise ConnectionError("MongoDB connection failed")
        
        # 初始化或加载SketchPad
        self._init_sketch_pad()

    def _init_sketch_pad(self) -> None:
        """初始化或加载SketchPad"""
        try:
            # 尝试从MongoDB加载现有SketchPad
            sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
            
            if sketch_doc:
                app_log(f"从MongoDB加载现有SketchPad: {self.sketch_pad_id}")
                # 同步到Redis缓存
                self._sync_from_mongo_to_redis(sketch_doc)
            else:
                app_log(f"创建新的SketchPad: {self.sketch_pad_id}")
                # 创建新的SketchPad文档
                sketch_doc = SketchPadDocument(
                    sketch_pad_id=self.sketch_pad_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    items=[],
                    total_items=0,
                    max_items=1000,
                    total_accesses=0,
                    metadata={}
                )
                sketch_doc.save()
                
        except Exception as e:
            push_error(f"初始化SketchPad失败: {e}")
            raise

    def _get_redis_key(self, key: str) -> str:
        """获取Redis键名"""
        return f"sketch_pad:{self.sketch_pad_id}:{key}"

    def _get_content_hash(self, value: Any) -> str:
        """计算内容的哈希值"""
        content_str = json.dumps(value, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()[:8]

    def _sync_from_mongo_to_redis(self, sketch_doc: SketchPadDocument) -> None:
        """从MongoDB同步数据到Redis缓存"""
        try:
            with self._lock:
                # 清空现有Redis数据
                pattern = self._get_redis_key("*")
                keys = self.redis.keys(pattern)
                if keys:
                    # 确保keys是可迭代的
                    try:
                        # 强制类型转换避免类型检查器警告
                        key_list = list(keys) if keys else []  # type: ignore
                        if key_list:
                            self.redis.delete(*key_list)
                    except (TypeError, AttributeError):
                        # 如果keys不可迭代，跳过
                        pass
                
                # 同步所有项目
                items_list = sketch_doc.items if sketch_doc.items else []
                for item_doc in items_list:
                    # 创建SketchPadItem
                    item = SketchPadItem(
                        value=deserialize_from_mongo(item_doc.value),
                        timestamp=item_doc.timestamp,
                        summary=item_doc.summary,
                        expires_at=item_doc.expires_at,
                        access_count=item_doc.access_count,
                        last_accessed=item_doc.last_accessed,
                        tags=set(item_doc.tags) if item_doc.tags else set(),
                        content_type=item_doc.content_type,
                        content_hash=item_doc.content_hash
                    )
                    
                    # 存储到Redis
                    item_json = item.model_dump_json()
                    redis_key = self._get_redis_key(item_doc.key)
                    self.redis.set(redis_key, item_json)
                    
                    # 设置过期时间
                    if item_doc.expires_at:
                        ttl = int((item_doc.expires_at - datetime.now()).total_seconds())
                        if ttl > 0:
                            self.redis.expire(redis_key, ttl)
                    
                    # 更新标签索引
                    if item_doc.tags:
                        for tag in item_doc.tags:
                            tag_key = self._get_redis_key(f"tag:{tag}")
                            self.redis.sadd(tag_key, item_doc.key)
                
        except Exception as e:
            push_warning(f"从MongoDB同步到Redis失败: {e}")

    def _sync_from_redis_to_mongo(self) -> bool:
        """从Redis同步数据到MongoDB"""
        try:
            with self._lock:
                # 获取或创建SketchPad文档
                sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
                if not sketch_doc:
                    sketch_doc = SketchPadDocument(sketch_pad_id=self.sketch_pad_id)
                
                # 获取所有数据键（排除标签索引键）
                pattern = self._get_redis_key("*")
                all_keys = self.redis.keys(pattern)
                
                # 确保all_keys是可迭代的
                try:
                    key_list = list(all_keys) if all_keys else []  # type: ignore
                except (TypeError, AttributeError):
                    key_list = []
                
                sketch_doc.items = []
                
                for redis_key in key_list:
                    # 过滤掉标签索引键
                    redis_key_str = str(redis_key)
                    if ":tag:" in redis_key_str:
                        continue
                    
                    # 提取原始键名
                    original_key = redis_key_str.split(":", 2)[-1]
                    
                    # 获取项目数据
                    item_json = self.redis.get(str(redis_key))
                    if item_json:
                        try:
                            item_data = json.loads(str(item_json))
                            item = SketchPadItem(**item_data)
                            
                            # 创建MongoDB文档
                            item_doc = SketchPadItemDocument(
                                key=original_key,
                                value=serialize_for_mongo(item.value),
                                timestamp=item.timestamp,
                                summary=item.summary,
                                expires_at=item.expires_at,
                                access_count=item.access_count,
                                last_accessed=item.last_accessed,
                                tags=list(item.tags),
                                content_type=item.content_type,
                                content_hash=item.content_hash
                            )
                            sketch_doc.items.append(item_doc)
                            
                        except Exception as e:
                            push_warning(f"同步项目 {original_key} 失败: {e}")
                
                # 更新统计信息
                items_list = sketch_doc.items if sketch_doc.items else []
                sketch_doc.total_items = len(items_list)
                sketch_doc.total_accesses = sum(item.access_count for item in items_list)
                sketch_doc.updated_at = datetime.now()
                
                # 保存到MongoDB
                sketch_doc.save()
                return True
                
        except Exception as e:
            push_error(f"从Redis同步到MongoDB失败: {e}")
            return False

    # ---- Redis typed helpers ----
    def _redis_get(self, key: str) -> Optional[str]:
        raw = self.redis.get(key)
        return str(raw) if raw is not None else None

    def _redis_keys(self, pattern: str) -> List[str]:
        raw = self.redis.keys(pattern)
        if raw and hasattr(raw, '__iter__'):
            return [str(key) for key in raw]
        return []

    def _redis_smembers(self, key: str) -> Set[str]:
        raw = self.redis.smembers(key)
        if raw and hasattr(raw, '__iter__'):
            return {str(member) for member in raw}
        return set()

    def _redis_delete(self, *keys: str) -> int:
        if not keys:
            return 0
        result = self.redis.delete(*keys)
        return int(result) if isinstance(result, (int, float)) else 0

    def _redis_exists(self, key: str) -> bool:
        return bool(self.redis.exists(key))

    @override
    async def set_item(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        summary: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> str:
        """设置键值对"""
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
            item_json = self._redis_get(self._get_redis_key(key))
            if item_json is None:
                return None
            
            try:
                item = SketchPadItem.model_validate_json(item_json)
                # 更新访问信息
                item.access_count += 1
                item.last_accessed = datetime.now()
                
                # 更新Redis中的访问信息
                item_json_str = item.model_dump_json()
                self.redis.set(self._get_redis_key(key), item_json_str)
                
                return item
            except Exception as e:
                push_warning(f"反序列化项目失败: {e}")
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
                candidate_keys_set = self._redis_smembers(tag_key)
                
                # 确保candidate_keys是可迭代的
                if hasattr(candidate_keys_set, '__iter__'):
                    candidate_keys_list = list(candidate_keys_set)
                else:
                    candidate_keys_list = []
                for cand_key in candidate_keys_list:
                    item = self.get_item(str(cand_key))
                    if item and tags.issubset(item.tags):
                        results.append((str(cand_key), item))
            else:
                # 匹配任意标签
                seen_keys = set()
                for tag in tags:
                    tag_key = self._get_redis_key(f"tag:{tag}")
                    keys_set = self._redis_smembers(tag_key)
                    
                    # 确保keys_set是可迭代的
                    if hasattr(keys_set, '__iter__'):
                        keys_list = list(keys_set)
                    else:
                        keys_list = []
                    for member_key in keys_list:
                        member_key_str = str(member_key)
                        if member_key_str not in seen_keys:
                            item = self.get_item(member_key_str)
                            if item:
                                results.append((member_key_str, item))
                                seen_keys.add(member_key_str)
            
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
                # 过滤掉标签索引键
                if ":tag:" in key:
                    continue
                
                # 提取原始键名
                original_key = key.split(":", 2)[-1]
                
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
            return self._redis_exists(self._get_redis_key(key))

    @override
    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """获取所有键名"""
        with self._lock:
            redis_pattern = self._get_redis_key(pattern or "*")
            keys = self._redis_keys(redis_pattern)
            
            # 提取原始键名，过滤标签索引键
            result: List[str] = []
            for key in keys:
                if ":tag:" not in key:
                    original_key = key.split(":", 2)[-1]
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
                self.redis.delete(*keys)

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
                # 过滤掉标签索引键
                if ":tag:" in key:
                    continue
                
                # 提取原始键名
                original_key = key.split(":", 2)[-1]
                
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
                        push_warning(f"反序列化项目 {key} 失败: {e}")

    @override
    def persist(self) -> None:
        """持久化数据"""
        self._sync_from_redis_to_mongo()

    @override
    def restore(self) -> None:
        """从持久化数据中恢复"""
        try:
            sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
            if sketch_doc:
                self._sync_from_mongo_to_redis(sketch_doc)
        except Exception as e:
            push_error(f"从MongoDB恢复失败: {e}")

    @override
    def get_statistics(self) -> SketchPadStatistics:
        """获取统计信息"""
        with self._lock:
            # 只获取实际的数据键，不包括标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            data_keys: List[str] = []
            
            for key in all_keys:
                # 过滤掉标签索引键
                if ":tag:" not in key:
                    original_key = key.split(":", 2)[-1]
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

    @override
    def list_items(self, include_value: bool = False) -> List[SketchPadListItem]:
        """列出所有项目"""
        with self._lock:
            items: List[SketchPadListItem] = []
            # 获取所有键，但过滤掉标签索引键
            pattern = self._get_redis_key("*")
            all_keys = self._redis_keys(pattern)
            
            for key in all_keys:
                # 过滤掉标签索引键
                if ":tag:" in key:
                    continue
                
                # 提取原始键名
                original_key = key.split(":", 2)[-1]
                
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

    # ==================== MongoDB专有功能 ====================
    
    def query_items_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Tuple[str, SketchPadItem]]:
        """按时间范围查询项目"""
        try:
            sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
            if not sketch_doc:
                return []
            
            results = []
            for item_doc in sketch_doc.items:
                if item_doc.timestamp and start_time <= item_doc.timestamp <= end_time:
                    item = SketchPadItem(
                        value=deserialize_from_mongo(item_doc.value),
                        timestamp=item_doc.timestamp,
                        summary=item_doc.summary,
                        expires_at=item_doc.expires_at,
                        access_count=item_doc.access_count,
                        last_accessed=item_doc.last_accessed,
                        tags=set(item_doc.tags) if item_doc.tags else set(),
                        content_type=item_doc.content_type,
                        content_hash=item_doc.content_hash
                    )
                    results.append((item_doc.key, item))
            
            return results
        except Exception as e:
            push_error(f"按时间范围查询项目失败: {e}")
            return []
    
    def get_sketch_pad_statistics(self) -> Dict[str, Any]:
        """获取SketchPad统计信息"""
        try:
            sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
            if not sketch_doc:
                return {}
            
            # 统计各种内容类型
            content_type_counts: Dict[str, int] = {}
            tag_counts: Dict[str, int] = {}
            
            items_list = sketch_doc.items if sketch_doc.items else []
            for item_doc in items_list:
                # 统计内容类型
                content_type = item_doc.content_type
                content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1
                
                # 统计标签
                for tag in item_doc.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            return {
                "sketch_pad_id": self.sketch_pad_id,
                "total_items": len(sketch_doc.items),
                "total_accesses": sketch_doc.total_accesses,
                "content_type_distribution": content_type_counts,
                "tag_distribution": tag_counts,
                "created_at": sketch_doc.created_at.isoformat() if sketch_doc.created_at else None,
                "updated_at": sketch_doc.updated_at.isoformat() if sketch_doc.updated_at else None,
            }
        except Exception as e:
            push_error(f"获取SketchPad统计信息失败: {e}")
            return {}
    
    def search_items_in_mongo(self, query: str, limit: int = 10) -> List[Tuple[str, SketchPadItem]]:
        """在MongoDB中进行全文搜索"""
        try:
            sketch_doc = SketchPadDocument.objects(sketch_pad_id=self.sketch_pad_id).first()
            if not sketch_doc:
                return []
            
            results: List[Tuple[str, SketchPadItem]] = []
            query_lower = query.lower()
            
            items_list = sketch_doc.items if sketch_doc.items else []
            for item_doc in items_list:
                if len(results) >= limit:
                    break
                
                # 搜索summary和tags
                searchable_text = ""
                if item_doc.summary:
                    searchable_text += item_doc.summary + " "
                if item_doc.tags:
                    searchable_text += " ".join(item_doc.tags) + " "
                
                # 搜索value（如果是字符串）
                if isinstance(item_doc.value, dict) and 'text' in item_doc.value:
                    searchable_text += str(item_doc.value['text']) + " "
                elif isinstance(item_doc.value, str):
                    searchable_text += item_doc.value + " "
                
                if query_lower in searchable_text.lower():
                    item = SketchPadItem(
                        value=deserialize_from_mongo(item_doc.value),
                        timestamp=item_doc.timestamp,
                        summary=item_doc.summary,
                        expires_at=item_doc.expires_at,
                        access_count=item_doc.access_count,
                        last_accessed=item_doc.last_accessed,
                        tags=set(item_doc.tags) if item_doc.tags else set(),
                        content_type=item_doc.content_type,
                        content_hash=item_doc.content_hash
                    )
                    results.append((item_doc.key, item))
            
            return results
        except Exception as e:
            push_error(f"在MongoDB中搜索失败: {e}")
            return []
