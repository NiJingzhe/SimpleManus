import os
import json
import uuid
import threading
from typing import Dict, Optional, List, Type, Any
from datetime import datetime
from SimpleLLMFunc import OpenAICompatible

from context.sketch_pad import SketchPadBackend, RedisFileSketchPadBackend
from config.config import get_config


class SketchManager:
    """
    通用的SketchPad管理器，支持不同的后端实现。

    主要职责：
    1. 管理SketchPadBackend实例的创建和生命周期
    2. 提供高级的便捷接口
    3. 处理批量操作和清理任务
    4. 支持可插拔的后端实现
    """

    _instance = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, backend_class: Type[SketchPadBackend] = RedisFileSketchPadBackend):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SketchManager, cls).__new__(cls)
                    cls._instance.backend_class = backend_class
        return cls._instance

    def __init__(self, backend_class: Type[SketchPadBackend]):
        """
        初始化SketchPad管理器

        Args:
            backend_class: 后端实现类，默认为RedisFileSketchPadBackend
        """
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return

        self.backend_class = backend_class
        self.config = get_config()
        self.sketch_dir = self.config.SKETCH_DIR
        self._active_sketches: Dict[str, SketchPadBackend] = {}

        # 确保目录存在
        os.makedirs(self.sketch_dir, exist_ok=True)

        self._initialized = True

    def create_sketch_pad(
        self,
        sketch_id: Optional[str] = None,
        **backend_kwargs,
    ) -> SketchPadBackend:
        """
        创建新的SketchPad对象

        Args:
            sketch_id: SketchPad ID，如果为None则自动生成
            **backend_kwargs: 传递给后端的额外参数

        Returns:
            SketchPadBackend: 创建的SketchPad对象
        """
        with self._lock:
            if sketch_id is None:
                sketch_id = str(uuid.uuid4())

            # 检查是否已存在
            if sketch_id in self._active_sketches:
                return self._active_sketches[sketch_id]

            # 生成文件路径（如果后端需要）
            if "file_path" not in backend_kwargs:
                sketch_file = os.path.join(self.sketch_dir, f"skt_{sketch_id}.json")
                backend_kwargs["file_path"] = sketch_file

            # 创建SketchPad对象
            sketch_pad = self.backend_class(
                sketch_pad_id=sketch_id,
                **backend_kwargs,
            )

            # 加入活动SketchPad列表
            self._active_sketches[sketch_id] = sketch_pad

            return sketch_pad

    def get_sketch_pad(self, sketch_id: str) -> Optional[SketchPadBackend]:
        """
        获取指定ID的SketchPad对象

        Args:
            sketch_id: SketchPad ID

        Returns:
            SketchPadBackend: SketchPad对象，如果不存在则返回None
        """
        with self._lock:
            # 先检查活动SketchPad
            if sketch_id in self._active_sketches:
                return self._active_sketches[sketch_id]

            # 尝试从文件加载（如果后端支持）
            sketch_file = os.path.join(self.sketch_dir, f"skt_{sketch_id}.json")
            if os.path.exists(sketch_file):
                try:
                    sketch_pad = self.backend_class(
                        sketch_pad_id=sketch_id,
                        file_path=sketch_file,
                    )
                    self._active_sketches[sketch_id] = sketch_pad
                    return sketch_pad
                except Exception as e:
                    print(f"Warning: Failed to load sketch {sketch_id}: {e}")

            return None

    def delete_sketch_pad(self, sketch_id: str) -> bool:
        """
        删除指定ID的SketchPad对象

        Args:
            sketch_id: SketchPad ID

        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            success = False

            # 从活动SketchPad中移除
            if sketch_id in self._active_sketches:
                del self._active_sketches[sketch_id]
                success = True

            # 删除文件（如果存在）
            sketch_file = os.path.join(self.sketch_dir, f"skt_{sketch_id}.json")
            if os.path.exists(sketch_file):
                try:
                    os.remove(sketch_file)
                    success = True
                except Exception as e:
                    print(f"Warning: Failed to delete sketch file {sketch_file}: {e}")

            return success

    def list_sketch_pads(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的SketchPad

        Returns:
            List[Dict]: SketchPad信息列表
        """
        sketches = []

        # 扫描文件系统中的SketchPad文件
        try:
            for filename in os.listdir(self.sketch_dir):
                if filename.startswith("skt_") and filename.endswith(".json"):
                    sketch_id = filename[4:-5]  # 移除 "skt_" 前缀和 ".json" 后缀

                    sketch_info = {
                        "sketch_id": sketch_id,
                        "file_path": os.path.join(self.sketch_dir, filename),
                        "is_active": sketch_id in self._active_sketches,
                    }

                    # 尝试读取基本信息
                    try:
                        file_path = sketch_info["file_path"]
                        if isinstance(file_path, str):
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                sketch_info.update({
                                    "total_items": len(data.get("items", {})),
                                    "last_saved": data.get("serialization_timestamp"),
                                    "sketch_pad_id": data.get("sketch_pad_id"),
                                })
                    except Exception:
                        pass  # 忽略读取错误

                    sketches.append(sketch_info)

        except Exception as e:
            print(f"Warning: Failed to list sketches: {e}")

        return sketches

    def save_sketch_pad(self, sketch_id: str) -> bool:
        """
        手动保存指定SketchPad到文件

        Args:
            sketch_id: SketchPad ID

        Returns:
            bool: 是否成功保存
        """
        with self._lock:
            if sketch_id in self._active_sketches:
                try:
                    sketch_pad = self._active_sketches[sketch_id]
                    sketch_pad.persist()
                    return True
                except Exception as e:
                    print(f"Warning: Failed to save sketch {sketch_id}: {e}")

            return False

    async def save_all_sketch_pads(self) -> int:
        """
        保存所有活动SketchPad到文件

        Returns:
            int: 成功保存的SketchPad数量
        """
        saved_count = 0
        with self._lock:
            for sketch_id in list(self._active_sketches.keys()):
                if self.save_sketch_pad(sketch_id):
                    saved_count += 1

        return saved_count

    async def cleanup_inactive_sketches(self, max_inactive_count: int = 10) -> int:
        """
        清理非活动的SketchPad（基于使用频率）

        Args:
            max_inactive_count: 最大保持活动的SketchPad数量

        Returns:
            int: 清理的SketchPad数量
        """
        cleaned_count = 0

        with self._lock:
            if len(self._active_sketches) <= max_inactive_count:
                return 0

            # 按访问统计排序，保留最常用的
            sketches_by_usage = []
            for sketch_id, sketch_pad in self._active_sketches.items():
                try:
                    stats = sketch_pad.get_statistics()
                    total_accesses = stats.total_accesses
                    sketches_by_usage.append((sketch_id, sketch_pad, total_accesses))
                except Exception:
                    sketches_by_usage.append((sketch_id, sketch_pad, 0))

            # 按访问次数排序
            sketches_by_usage.sort(key=lambda x: x[2], reverse=True)

            # 保存并移除低使用率的SketchPad
            sketches_to_remove = sketches_by_usage[max_inactive_count:]
            for sketch_id, sketch_pad, _ in sketches_to_remove:
                try:
                    # 保存到文件
                    sketch_pad.persist()
                    
                    # 从活动列表移除
                    del self._active_sketches[sketch_id]
                    cleaned_count += 1
                except Exception as e:
                    print(f"Warning: Error cleaning sketch {sketch_id}: {e}")

        return cleaned_count

    # ===== 便捷接口 =====

    async def set_item(
        self,
        sketch_id: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        summary: Optional[str] = None,
        tags: Optional[set] = None,
    ) -> Optional[str]:
        """
        便捷设置项目

        Args:
            sketch_id: SketchPad ID
            key: 键名
            value: 值
            ttl: 过期时间（秒）
            summary: 摘要
            tags: 标签

        Returns:
            Optional[str]: 设置的键名，失败则返回None
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return None

        try:
            return await sketch_pad.set_item(key, value, ttl, summary, tags)
        except Exception as e:
            print(f"Warning: Failed to set item: {e}")
            return None

    def get_item(self, sketch_id: str, key: str) -> Optional[Any]:
        """
        获取项目

        Args:
            sketch_id: SketchPad ID
            key: 键名

        Returns:
            Optional[Any]: 项目值
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return None

        return sketch_pad.get_item(key)

    def get_value(self, sketch_id: str, key: str) -> Optional[Any]:
        """
        获取值

        Args:
            sketch_id: SketchPad ID
            key: 键名

        Returns:
            Optional[Any]: 值
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return None

        return sketch_pad.get_value(key)

    def search_by_tags(
        self, sketch_id: str, tags: set, match_all: bool = False
    ) -> List[tuple]:
        """
        按标签搜索

        Args:
            sketch_id: SketchPad ID
            tags: 标签集合
            match_all: 是否匹配所有标签

        Returns:
            List[tuple]: 搜索结果
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return []

        return sketch_pad.search_by_tags(tags, match_all)

    def search_by_content(self, sketch_id: str, query: str, limit: int = 5) -> List[tuple]:
        """
        按内容搜索

        Args:
            sketch_id: SketchPad ID
            query: 搜索查询
            limit: 结果数量限制

        Returns:
            List[tuple]: 搜索结果
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return []

        return sketch_pad.search_by_content(query, limit)

    def delete_item(self, sketch_id: str, key: str) -> bool:
        """
        删除项目

        Args:
            sketch_id: SketchPad ID
            key: 键名

        Returns:
            bool: 是否成功删除
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return False

        return sketch_pad.delete(key)

    def get_statistics(self, sketch_id: str) -> Optional[Any]:
        """
        获取统计信息

        Args:
            sketch_id: SketchPad ID

        Returns:
            Optional[Any]: 统计信息
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return None

        try:
            return sketch_pad.get_statistics()
        except Exception as e:
            print(f"Warning: Failed to get statistics: {e}")
            return None

    def list_items(self, sketch_id: str, include_value: bool = False) -> List[Any]:
        """
        列出所有项目

        Args:
            sketch_id: SketchPad ID
            include_value: 是否包含值

        Returns:
            List[Any]: 项目列表
        """
        sketch_pad = self.get_sketch_pad(sketch_id)
        if not sketch_pad:
            return []

        try:
            return sketch_pad.list_items(include_value)
        except Exception as e:
            print(f"Warning: Failed to list items: {e}")
            return []


# 全局实例
_global_sketch_manager: Optional[SketchManager] = None


def get_sketch_manager() -> SketchManager:
    """获取全局SketchManager实例"""
    global _global_sketch_manager
    if _global_sketch_manager is None:
        # 从config获取Redis配置
        config = get_config()

        # redis config
        redis_host = config.REDIS_HOST
        redis_port = int(config.REDIS_PORT)
        redis_db = int(config.REDIS_DB)

        # 创建自定义backend类，预配置Redis参数
        class ConfiguredRedisFileSketchPadBackend(RedisFileSketchPadBackend):
            def __init__(
                self,
                sketch_pad_id: str,
                redis_host: str = redis_host,
                redis_port: int = redis_port,
                redis_db: int = redis_db,
                file_path: Optional[str] = None,
            ):
                super().__init__(
                    sketch_pad_id=sketch_pad_id,
                    redis_host=redis_host,
                    redis_port=redis_port,
                    redis_db=redis_db,
                    file_path=file_path,
                )

        # 使用配置好的backend类创建SketchManager
        _global_sketch_manager = SketchManager(
            backend_class=ConfiguredRedisFileSketchPadBackend
        )
    return _global_sketch_manager