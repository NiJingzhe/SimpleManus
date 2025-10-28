"""
MongoDB初始化脚本
用于初始化MongoDB连接、创建索引和迁移现有数据
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from SimpleLLMFunc.logger import app_log, push_error, push_warning

from context.mongo_connection import init_mongo_connection, get_mongo_manager
from context.mongo_schemas import (
    ContextDocument, SketchPadDocument, ConversationDocument,
    MessageDocument, SketchPadItemDocument,
    serialize_for_mongo, deserialize_from_mongo
)
from context.schemas import Message, SketchPadItem
from config.config import get_config


class MongoInitializer:
    """MongoDB初始化器"""
    
    def __init__(self):
        self.config = get_config()
        self.context_dir = getattr(self.config, 'CONTEXT_DIR', 'data/contexts')
        self.sketch_dir = getattr(self.config, 'SKETCH_DIR', 'data/sketches')
    
    def init_mongodb(self) -> bool:
        """初始化MongoDB连接和索引"""
        app_log("开始初始化MongoDB...")
        
        # 初始化连接
        if not init_mongo_connection():
            push_error("MongoDB连接初始化失败")
            return False
        
        app_log("✅ MongoDB连接初始化成功")
        return True
    
    def migrate_file_data_to_mongo(self) -> Dict[str, int]:
        """将文件系统中的数据迁移到MongoDB"""
        app_log("开始迁移文件系统数据到MongoDB...")
        
        stats = {
            "contexts_migrated": 0,
            "sketches_migrated": 0,
            "conversations_created": 0,
            "errors": 0
        }
        
        # 迁移Context数据
        stats["contexts_migrated"] = self._migrate_contexts()
        
        # 迁移SketchPad数据
        stats["sketches_migrated"] = self._migrate_sketches()
        
        # 创建Conversation记录
        stats["conversations_created"] = self._create_conversation_records()
        
        app_log(f"数据迁移完成: {stats}")
        return stats
    
    def _migrate_contexts(self) -> int:
        """迁移Context数据"""
        migrated = 0
        
        if not os.path.exists(self.context_dir):
            app_log(f"Context目录不存在: {self.context_dir}")
            return 0
        
        try:
            for filename in os.listdir(self.context_dir):
                if filename.startswith("ctx_") and filename.endswith(".json"):
                    context_id = filename[4:-5]  # 移除前缀和后缀
                    file_path = os.path.join(self.context_dir, filename)
                    
                    if self._migrate_single_context(context_id, file_path):
                        migrated += 1
                    
        except Exception as e:
            push_error(f"迁移Context数据时出错: {e}")
        
        app_log(f"成功迁移 {migrated} 个Context")
        return migrated
    
    def _migrate_single_context(self, context_id: str, file_path: str) -> bool:
        """迁移单个Context文件"""
        try:
            # 检查是否已存在
            if ContextDocument.objects(context_id=context_id).first():
                app_log(f"Context {context_id} 已存在于MongoDB，跳过")
                return False
            
            # 读取文件数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 创建Context文档
            context_doc = ContextDocument(context_id=context_id)
            
            # 迁移元数据
            metadata = data.get("metadata", {})
            context_doc.metadata = metadata
            context_doc.total_messages = metadata.get("total_messages", 0)
            context_doc.max_history_length = metadata.get("max_history_length", 5)
            
            # 解析时间字段
            if metadata.get("start_time"):
                try:
                    context_doc.start_time = datetime.fromisoformat(metadata["start_time"])
                except:
                    context_doc.start_time = datetime.now()
            
            if metadata.get("last_activity"):
                try:
                    context_doc.last_activity = datetime.fromisoformat(metadata["last_activity"])
                except:
                    context_doc.last_activity = datetime.now()
            
            # 迁移消息
            messages_data = data.get("messages", [])
            context_doc.messages = []
            
            for msg_data in messages_data:
                try:
                    message = Message(**msg_data)
                    msg_doc = MessageDocument(
                        role=message.role,
                        content=serialize_for_mongo(message.content),
                        name=message.name,
                        tool_calls=message.tool_calls or [],
                        tool_call_id=message.tool_call_id,
                        timestamp=datetime.fromisoformat(message.timestamp) if message.timestamp else datetime.now()
                    )
                    context_doc.messages.append(msg_doc)
                except Exception as e:
                    push_warning(f"迁移消息失败: {e}")
            
            # 迁移摘要
            if data.get("summary"):
                context_doc.summary = data["summary"]
            
            # 保存到MongoDB
            context_doc.save()
            app_log(f"✅ 成功迁移Context: {context_id}")
            return True
            
        except Exception as e:
            push_error(f"迁移Context {context_id} 失败: {e}")
            return False
    
    def _migrate_sketches(self) -> int:
        """迁移SketchPad数据"""
        migrated = 0
        
        if not os.path.exists(self.sketch_dir):
            app_log(f"Sketch目录不存在: {self.sketch_dir}")
            return 0
        
        try:
            for filename in os.listdir(self.sketch_dir):
                if filename.startswith("skt_") and filename.endswith(".json"):
                    sketch_id = filename[4:-5]  # 移除前缀和后缀
                    file_path = os.path.join(self.sketch_dir, filename)
                    
                    if self._migrate_single_sketch(sketch_id, file_path):
                        migrated += 1
                    
        except Exception as e:
            push_error(f"迁移SketchPad数据时出错: {e}")
        
        app_log(f"成功迁移 {migrated} 个SketchPad")
        return migrated
    
    def _migrate_single_sketch(self, sketch_id: str, file_path: str) -> bool:
        """迁移单个SketchPad文件"""
        try:
            # 检查是否已存在
            if SketchPadDocument.objects(sketch_pad_id=sketch_id).first():
                app_log(f"SketchPad {sketch_id} 已存在于MongoDB，跳过")
                return False
            
            # 读取文件数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 创建SketchPad文档
            sketch_doc = SketchPadDocument(sketch_pad_id=sketch_id)
            
            # 迁移项目
            items_data = data.get("items", {})
            sketch_doc.items = []
            
            for key, item_data in items_data.items():
                try:
                    item = SketchPadItem(**item_data)
                    item_doc = SketchPadItemDocument(
                        key=key,
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
                    push_warning(f"迁移SketchPad项目 {key} 失败: {e}")
            
            # 更新统计信息
            sketch_doc.total_items = len(sketch_doc.items)
            sketch_doc.total_accesses = sum(item.access_count for item in sketch_doc.items)
            
            # 保存到MongoDB
            sketch_doc.save()
            app_log(f"✅ 成功迁移SketchPad: {sketch_id}")
            return True
            
        except Exception as e:
            push_error(f"迁移SketchPad {sketch_id} 失败: {e}")
            return False
    
    def _create_conversation_records(self) -> int:
        """为现有的Context和SketchPad创建Conversation记录"""
        created = 0
        
        try:
            # 获取所有Context
            contexts = ContextDocument.objects().all()
            context_ids = {ctx.context_id for ctx in contexts}
            
            # 获取所有SketchPad
            sketches = SketchPadDocument.objects().all()
            sketch_ids = {sketch.sketch_pad_id for sketch in sketches}
            
            # 找到匹配的ID（Context和SketchPad使用相同的ID）
            common_ids = context_ids.intersection(sketch_ids)
            
            for conversation_id in common_ids:
                try:
                    # 检查是否已存在Conversation记录
                    if ConversationDocument.objects(conversation_id=conversation_id).first():
                        continue
                    
                    # 获取Context信息用于设置时间
                    context_doc = ContextDocument.objects(context_id=conversation_id).first()
                    
                    # 创建Conversation记录
                    conversation_doc = ConversationDocument(
                        conversation_id=conversation_id,
                        context_id=conversation_id,
                        sketch_pad_id=conversation_id,
                        created_at=context_doc.start_time if context_doc and context_doc.start_time else datetime.now(),
                        last_accessed=context_doc.last_activity if context_doc and context_doc.last_activity else datetime.now(),
                        is_active=True,
                        metadata={}
                    )
                    conversation_doc.save()
                    created += 1
                    app_log(f"✅ 创建Conversation记录: {conversation_id}")
                    
                except Exception as e:
                    push_warning(f"创建Conversation记录 {conversation_id} 失败: {e}")
        
        except Exception as e:
            push_error(f"创建Conversation记录时出错: {e}")
        
        app_log(f"成功创建 {created} 个Conversation记录")
        return created
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            manager = get_mongo_manager()
            return manager.health_check()
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Health check failed: {str(e)}',
                'error': str(e)
            }
    
    def get_migration_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        try:
            # 统计MongoDB中的数据
            context_count = ContextDocument.objects().count()
            sketch_count = SketchPadDocument.objects().count()
            conversation_count = ConversationDocument.objects().count()
            
            # 统计文件系统中的数据
            file_contexts = 0
            file_sketches = 0
            
            if os.path.exists(self.context_dir):
                file_contexts = len([f for f in os.listdir(self.context_dir) 
                                   if f.startswith("ctx_") and f.endswith(".json")])
            
            if os.path.exists(self.sketch_dir):
                file_sketches = len([f for f in os.listdir(self.sketch_dir) 
                                   if f.startswith("skt_") and f.endswith(".json")])
            
            return {
                "mongodb": {
                    "contexts": context_count,
                    "sketches": sketch_count,
                    "conversations": conversation_count
                },
                "filesystem": {
                    "contexts": file_contexts,
                    "sketches": file_sketches
                },
                "migration_needed": file_contexts > context_count or file_sketches > sketch_count
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }


def main():
    """主函数"""
    print("🚀 SimpleAgent MongoDB 初始化工具")
    print("=" * 50)
    
    initializer = MongoInitializer()
    
    # 初始化MongoDB
    if not initializer.init_mongodb():
        print("❌ MongoDB初始化失败")
        return
    
    # 检查迁移状态
    status = initializer.get_migration_status()
    print(f"📊 当前状态:")
    print(f"  MongoDB: {status.get('mongodb', {})}")
    print(f"  文件系统: {status.get('filesystem', {})}")
    
    if status.get('migration_needed', False):
        print("\n🔄 检测到需要数据迁移")
        confirm = input("是否开始迁移? (y/N): ")
        if confirm.lower() == 'y':
            migration_stats = initializer.migrate_file_data_to_mongo()
            print(f"\n✅ 迁移完成: {migration_stats}")
        else:
            print("跳过数据迁移")
    else:
        print("\n✅ 无需数据迁移")
    
    # 健康检查
    health = initializer.health_check()
    print(f"\n🏥 健康检查: {health.get('status', 'unknown')}")
    if health.get('message'):
        print(f"  信息: {health['message']}")
    
    print("\n🎉 MongoDB初始化完成!")


if __name__ == "__main__":
    main()
