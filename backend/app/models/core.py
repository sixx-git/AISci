"""
基础模型基类
包含通用字段和方法
"""
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class TimestampMixin:
    """时间戳混入类"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class BaseModel(TimestampMixin, Base):
    """基础模型抽象类"""
    __abstract__ = True
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    def to_dict(self):
        """转换为字典"""
        result = {}
        for key in self.__dict__.keys():
            if not key.startswith('_'):
                value = self.__dict__[key]
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
        return result
    
    def __repr__(self):
        """字符串表示"""
        return f"<{self.__class__.__name__} id={self.id}>"
