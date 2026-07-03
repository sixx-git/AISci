"""Skill 管理 API"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.skill_registry_service import (
    discover_skills,
    get_summary,
    list_agents,
    list_skills,
    set_skill_enabled,
    SkillToggleError,
)

router = APIRouter()


class SkillToggleRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用该 Skill")


@router.get("")
async def get_skills(
    category: Optional[str] = Query(None, description="按分类筛选"),
    agent: Optional[str] = Query(None, description="按智能体筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    refresh: bool = Query(False, description="重新扫描 Skill 模块"),
):
    if refresh:
        discover_skills(refresh=True)
    data = list_skills(category=category, agent=agent, keyword=keyword)
    return {"code": 200, "data": data, "message": "success"}


@router.get("/summary")
async def skills_summary(
    refresh: bool = Query(False, description="重新扫描 Skill 模块后再统计"),
):
    if refresh:
        discover_skills(refresh=True)
    return {"code": 200, "data": get_summary(), "message": "success"}


@router.get("/agents")
async def skills_by_agent():
    return {"code": 200, "data": list_agents(), "message": "success"}


@router.patch("/{skill_id}")
async def toggle_skill(skill_id: str, body: SkillToggleRequest):
    try:
        updated = set_skill_enabled(skill_id, body.enabled)
    except SkillToggleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_id}")
    return {
        "code": 200,
        "data": updated,
        "message": "已启用" if body.enabled else "已禁用",
    }
