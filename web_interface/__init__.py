"""
Web Interface module for SimpleAgent
提供符合OpenAI API规范的Web服务接口
"""

from .server import app
from .models import *

__all__ = [
    'app',
    'ChatCompletionRequest',
    'ChatCompletionResponse',
    'ChatMessage',
    'ChatChoice',
    'Usage',
    'DeltaMessage',
    'ChatCompletionChunk',
    'ModelInfo',
    'ModelListResponse',
    'ErrorResponse'
]
