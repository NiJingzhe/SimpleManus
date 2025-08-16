"""
错误处理模块
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from .models import ErrorResponse, ErrorDetail


def create_error_response(
    message: str,
    error_type: str = "invalid_request",
    param: str = None,
    code: str = None,
    status_code: int = 400,
) -> JSONResponse:
    """创建标准错误响应"""
    error_detail = ErrorDetail(message=message, type=error_type, param=param, code=code)
    error_response = ErrorResponse(error=error_detail)
    return JSONResponse(status_code=status_code, content=error_response.model_dump())


async def not_found_handler(request: Request, exc):
    """404错误处理"""
    return create_error_response(
        message=f"Not found: {request.url.path}",
        error_type="not_found",
        status_code=404,
    )


async def internal_error_handler(request: Request, exc):
    """500错误处理"""
    return create_error_response(
        message="Internal server error",
        error_type="server_error",
        status_code=500
    )
