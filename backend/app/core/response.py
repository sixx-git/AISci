"""
统一响应格式（与 schemas/common.py 中 ResponseModel 保持一致，code=200 表示成功）
"""
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应"""
    code: int = Field(..., description="响应码，200 表示成功")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    
    class Config:
        from_attributes = True


def success(data: Optional[T] = None, message: str = "操作成功") -> ApiResponse[T]:
    """成功响应"""
    return ApiResponse[T](
        code=200,
        message=message,
        data=data
    )


def error(message: str = "操作失败", code: int = 400) -> ApiResponse:
    """错误响应"""
    return ApiResponse(
        code=code,
        message=message,
        data=None
    )
