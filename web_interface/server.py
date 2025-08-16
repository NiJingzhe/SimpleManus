"""
FastAPI Web Server for SimpleAgent - 模块化版本
符合OpenAI API规范的Web服务器实现
支持多Agent架构，通过model name选择不同的Agent
"""
from contextlib import asynccontextmanager
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .state import server_state
from .routers import (
    health_router,
    agent_router,
    conversation_router,
    chat_router,
)
from .error_handlers import not_found_handler, internal_error_handler
from SimpleLLMFunc.logger import push_error, app_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    app_log("🚀 Initializing SimpleAgent Web Server...")
    try:
        server_state.initialize()
        app_log("✅ SimpleAgent initialized successfully!")
    except Exception as e:
        push_error(f"❌ Failed to initialize SimpleAgent: {e}")
        raise

    yield

    app_log("🔄 Shutting down SimpleAgent Web Server...")


# 创建FastAPI应用
app = FastAPI(
    title="SimpleAgent API",
    description="OpenAI-compatible API for SimpleAgent - A universal agent framework",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health_router)
app.include_router(agent_router)
app.include_router(conversation_router)
app.include_router(chat_router)

# 注册错误处理器
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(500, internal_error_handler)


if __name__ == "__main__":
    uvicorn.run(
        "web_interface.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
