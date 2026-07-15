from pydantic import BaseModel, Field
from typing import Any


class DataPoint(BaseModel):
    """单条实验数据"""
    key: str
    value: Any
    metadata: dict = Field(default_factory=dict)


class IterationResult(BaseModel):
    """单轮迭代执行结果"""
    iteration_number: int
    plan_used: dict = Field(default_factory=dict)
    start_time: str = ""
    end_time: str = ""
    status: str = "pending"  # pending, success, partial, failed
    data_points: list[DataPoint] = Field(default_factory=list)
    raw_output: Any = None
    summary: str = ""
    error_message: str = ""
