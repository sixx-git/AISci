"""
通用响应格式定义
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List, Any
from datetime import datetime

# 泛型类型
T = TypeVar('T')


class ResponseModel(BaseModel, Generic[T]):
    """统一响应格式"""
    code: int = Field(200, description="响应状态码")
    message: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": None,
                "timestamp": "2024-01-01T00:00:00"
            }
        }


class PageInfo(BaseModel):
    """分页信息"""
    page: int = Field(1, ge=1, description="当前页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    total: int = Field(0, ge=0, description="总数量")
    total_pages: int = Field(0, ge=0, description="总页数")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    list: List[T] = Field(default_factory=list, description="数据列表")
    pagination: PageInfo = Field(..., description="分页信息")


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应格式"""
    code: int
    message: str
    details: Optional[List[ErrorDetail]] = None


# 快捷响应方法
def success_response(data: Any = None, message: str = "success", code: int = 200) -> ResponseModel:
    """成功响应"""
    return ResponseModel(
        code=code,
        message=message,
        data=data
    )


def error_response(message: str = "error", code: int = 400, details: Optional[List[ErrorDetail]] = None) -> ErrorResponse:
    """错误响应"""
    return ErrorResponse(
        code=code,
        message=message,
        details=details
    )
