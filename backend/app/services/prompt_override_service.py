"""项目级 Prompt Override 管理"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineStage, ProjectPromptOverride
from app.services.prompt_loader import get_prompt_loader

CHINA_TZ = timezone(timedelta(hours=8))

STAGE_TEMPLATE_MAP = {
    PipelineStage.PROBLEM_UNDERSTANDING: "problem_understanding",
    PipelineStage.LITERATURE_MINING: "literature_mining",
    PipelineStage.KNOWLEDGE_GAP: "knowledge_gap",
    PipelineStage.HYPOTHESIS_GENERATION: "hypothesis_generation",
    PipelineStage.HYPOTHESIS_REVIEW: "hypothesis_review",
    PipelineStage.EXPERIMENT_DESIGN: "experiment_design",
    PipelineStage.SMALL_VALIDATION: "small_validation",
    PipelineStage.REPORT_GENERATION: "report_generation",
}


def _parse_stage(stage: str) -> PipelineStage:
    try:
        return PipelineStage(stage)
    except ValueError as exc:
        raise ValueError(f"无效 stage: {stage}") from exc


class PromptOverrideService:
    def __init__(self, db: Session):
        self.db = db
        self.loader = get_prompt_loader()

    def get_prompt_info(self, project_id: str, stage: str) -> Dict[str, Any]:
        stage_enum = _parse_stage(stage)
        template_name = STAGE_TEMPLATE_MAP[stage_enum]
        default_template = self.loader.load_template(template_name)
        override = self._get_override(project_id, stage_enum)
        return {
            "project_id": project_id,
            "stage": stage,
            "template_name": template_name,
            "default_template": default_template,
            "override_template": override.prompt_template if override else None,
            "effective_template": override.prompt_template if override else default_template,
            "has_override": override is not None,
            "updated_at": override.updated_at.isoformat() if override and override.updated_at else None,
        }

    def save_override(self, project_id: str, stage: str, prompt_template: str, editor: str = "user") -> Dict[str, Any]:
        stage_enum = _parse_stage(stage)
        override = self._get_override(project_id, stage_enum)
        now = datetime.now(CHINA_TZ)
        if override:
            override.prompt_template = prompt_template
            override.updated_at = now
            override.editor = editor
        else:
            override = ProjectPromptOverride(
                id=str(uuid.uuid4()),
                project_id=project_id,
                stage=stage_enum,
                prompt_template=prompt_template,
                editor=editor,
                created_at=now,
                updated_at=now,
            )
            self.db.add(override)
        self.db.commit()
        self.db.refresh(override)
        return self.get_prompt_info(project_id, stage)

    def delete_override(self, project_id: str, stage: str) -> Dict[str, Any]:
        stage_enum = _parse_stage(stage)
        override = self._get_override(project_id, stage_enum)
        if override:
            self.db.delete(override)
            self.db.commit()
        return self.get_prompt_info(project_id, stage)

    def get_effective_template(self, project_id: Optional[str], template_name: str) -> str:
        if not project_id:
            return self.loader.load_template(template_name)
        stage_enum = None
        for st, name in STAGE_TEMPLATE_MAP.items():
            if name == template_name.replace(".md", ""):
                stage_enum = st
                break
        if stage_enum is None:
            return self.loader.load_template(template_name)
        override = self._get_override(project_id, stage_enum)
        if override:
            return override.prompt_template
        return self.loader.load_template(template_name)

    def _get_override(self, project_id: str, stage: PipelineStage) -> Optional[ProjectPromptOverride]:
        return (
            self.db.query(ProjectPromptOverride)
            .filter(
                ProjectPromptOverride.project_id == project_id,
                ProjectPromptOverride.stage == stage,
            )
            .first()
        )


def get_prompt_override_service(db: Session) -> PromptOverrideService:
    return PromptOverrideService(db)
