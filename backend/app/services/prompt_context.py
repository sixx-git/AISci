"""Pipeline 执行期间的 Prompt 上下文（项目级 override）"""
from contextvars import ContextVar
from typing import Optional

_current_project_id: ContextVar[Optional[str]] = ContextVar("pipeline_project_id", default=None)


def set_project_id(project_id: Optional[str]) -> None:
    _current_project_id.set(project_id)


def get_project_id() -> Optional[str]:
    return _current_project_id.get()
