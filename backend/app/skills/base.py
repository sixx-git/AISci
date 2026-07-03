"""
科研外部 Skill 适配层 —— 基础抽象
参考 Hermes / OpenScholar / AI Scientist 等科研智能体的公开能力思想，
实现为本项目内部模块，不直接复制第三方代码。
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.success = False


class BaseSkill(ABC):
    """可插拔科研 Skill 基类

    所有 Skill 输出结构化 JSON（通过 SkillResult.data 承载），
    不破坏现有 Pipeline。
    """

    name: str = ""
    description: str = ""
    source_reference: Optional[str] = None
    _skill_run_guarded: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is BaseSkill or getattr(cls, "_skill_run_guarded", False):
            return

        original_run = cls.__dict__.get("run")
        if original_run is None:
            return

        async def guarded_run(
            self,
            input_data: Dict[str, Any],
            context: Dict[str, Any],
        ) -> SkillResult:
            from app.services.skill_registry_service import is_skill_enabled, is_skill_locked

            skill_name = getattr(self, "name", "") or self.__class__.__name__
            if skill_name and not is_skill_locked(skill_name) and not is_skill_enabled(skill_name):
                result = SkillResult(success=True)
                result.data = {
                    "skipped": True,
                    "skill": skill_name,
                    "reason": "disabled_in_registry",
                }
                result.add_warning(f"Skill「{skill_name}」已在技能管理中禁用，跳过执行")
                return result
            return await original_run(self, input_data, context)

        cls.run = guarded_run  # type: ignore[method-assign, assignment]
        cls._skill_run_guarded = True

    @abstractmethod
    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        """执行 Skill

        Args:
            input_data: Skill 输入参数
            context: Pipeline 上下文（project_id, research_question, upstream 输出等）

        Returns:
            SkillResult: 包含 data / warnings / errors / metadata
        """
        ...