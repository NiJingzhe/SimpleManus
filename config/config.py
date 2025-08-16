from SimpleLLMFunc import OpenAICompatible
from functools import lru_cache
import os
from typing import Optional
from dotenv import load_dotenv

# 加载工作目录下的.env文件
load_dotenv()


current_file_dir = (
    __file__.rsplit("/", 1)[0] if "/" in __file__ else __file__.rsplit("\\", 1)[0]
)


class Config:

    JSON_FILE = current_file_dir + "/provider.json"
    INTERFACE_COLLECTION = OpenAICompatible.load_from_json_file(JSON_FILE)

    # BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gpt-4o"]
    # BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-2.5-pro-preview-06-05"]
    # BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-2.5-flash"]
    # BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["anthropic/claude-sonnet-4"]
    # BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["openai/gpt-5-chat"]
    BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["z-ai/glm-4.5"]
    CODE_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["google/gemini-2.5-pro"]
    # CODE_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["qwen/qwen3-coder:free"]


    REASONING_INTERFACE = INTERFACE_COLLECTION["chatanywhere"][
        "anthropic/claude-sonnet-4"
    ]

    QUICK_INTERFACE = INTERFACE_COLLECTION["chatanywhere"][
        "google/gemini-2.5-flash"
    ]

    MULTIMODALITY_INTERFACE = INTERFACE_COLLECTION["chatanywhere"][
        "google/gemini-2.5-flash"
    ]

    CONTEXT_SUMMARY_INTERFACE = INTERFACE_COLLECTION["chatanywhere"][
        "google/gemini-2.5-flash"
    ]

    # ==================== RAGFlow 配置参数 ====================

    # 服务器配置
    RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost")
    RAGFLOW_API_KEY = os.getenv(
        "RAGFLOW_API_KEY", "ragflow-c3YzI1YTk0NTY0ODExZjBiNDZjYmExNm"
    )

    # 检索配置
    RAGFLOW_DEFAULT_PAGE_SIZE = 40
    RAGFLOW_DEFAULT_SIMILARITY_THRESHOLD = 0.35
    RAGFLOW_DEFAULT_VECTOR_SIMILARITY_WEIGHT = 0.6
    RAGFLOW_DEFAULT_TOP_K = 10
    RAGFLOW_DEFAULT_ENABLE_KEYWORD_MATCH = True
    RAGFLOW_DEFAULT_ENABLE_HIGHLIGHT = True
    RAGFLOW_DEFAULT_STORE_RESULT = True

    # 数据集列表配置
    RAGFLOW_DATASET_LIST_PAGE_SIZE = 30
    RAGFLOW_DATASET_LIST_INCLUDE_STATS = True

    # 数据集详情配置
    RAGFLOW_DATASET_INFO_INCLUDE_DOCUMENTS = True
    RAGFLOW_DATASET_INFO_DOC_PAGE_SIZE = 10

    # ==================== Context & Sketch 配置参数 ====================

    # redis url
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 9736))

    # 上下文存储目录配置
    CONTEXT_DIR: str = os.getenv("CONTEXT_DIR", "data/contexts")
    CONTEXT_MAX_HISTORY_LENGTH: int = int(os.getenv("CONTEXT_MAX_HISTORY_LENGTH", 10))
    
    # SketchPad存储目录配置  
    SKETCH_DIR: str = os.getenv("SKETCH_DIR", "data/sketches")


@lru_cache()
def get_config() -> Config:
    """Get the configuration instance."""
    return Config()
