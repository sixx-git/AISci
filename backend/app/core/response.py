"""
统一响应格式
"""
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应"""
    code: int = Field(..., description="响应码，0 表示成功")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    
    class Config:
        from_attributes = True


def success(data: Optional[T] = None, message: str = "操作成功") -> ApiResponse[T]:
    """成功响应"""
    return ApiResponse[T](
        code=0,
        message=message,
        data=data
    )


def error(message: str = "操作失败", code: int = 1) -> ApiResponse:
    """错误响应"""
    return ApiResponse(
        code=code,
        message=message,
        data=None
    )
