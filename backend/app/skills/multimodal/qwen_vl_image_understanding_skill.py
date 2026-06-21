"""Qwen-VL 图像理解 — 论文图表 / 实验截图 / 模型结构图"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()

IMAGE_SCHEMA = {
    "modality": "image",
    "summary": "",
    "detected_elements": [],
    "chart_type": "",
    "axis_labels": [],
    "key_trends": [],
    "possible_research_evidence": [],
    "warnings": [],
}


class QwenVlImageUnderstandingSkill(BaseSkill):
    name = "QwenVlImageUnderstanding"
    description = "使用 Qwen-VL 理解科研图像（图表、截图、结构图）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        image_path = input_data.get("image_path") or ""
        research_question = input_data.get("research_question") or ""
        ctx_text = input_data.get("context") or ""

        if not image_path or not os.path.exists(image_path):
            result.data = {
                **IMAGE_SCHEMA,
                "warnings": ["图像路径无效或文件不存在"],
            }
            result.add_error("image_path 无效")
            return result

        ext = Path(image_path).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".tiff", ".webp", ".gif"}:
            result.data = {**IMAGE_SCHEMA, "warnings": [f"不支持的图像格式: {ext}"]}
            result.add_warning(f"不支持的图像格式: {ext}")
            return result

        try:
            image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        except Exception as exc:
            result.data = {**IMAGE_SCHEMA, "warnings": [f"读取图像失败: {exc}"]}
            result.add_error(str(exc))
            return result

        if settings.QWEN_API_KEY and not settings.USE_MOCK_LLM:
            vlm_data = self._vlm_understand(image_b64, research_question, ctx_text, Path(image_path).name)
            if vlm_data:
                result.data = vlm_data
                return result
            result.add_warning("VLM 调用失败，已降级为规则摘要")

        result.data = self._rule_fallback(image_path, research_question)
        return result

    @staticmethod
    def _vlm_understand(
        image_b64: str,
        research_question: str,
        context: str,
        filename: str,
    ) -> Dict[str, Any] | None:
        from app.services.qwen_client import qwen_vision_structured_chat

        prompt = f"""你是科研图像分析助手。分析此图像（文件: {filename}），服务研究问题：
{research_question[:500]}

上下文: {context[:300] if context else '无'}

请识别：图表类型、轴标签、关键趋势、可见数值/结论、可作为科研证据的陈述。
若是论文图表/实验截图/模型结构图，请尽量提取可引用的事实。
输出 JSON 字段：modality(固定image)、summary、detected_elements[]、chart_type、axis_labels[]、
key_trends[]、possible_research_evidence[]、warnings[]。"""

        try:
            data = qwen_vision_structured_chat(
                prompt=prompt,
                image_base64=image_b64,
                schema_example=IMAGE_SCHEMA,
                prompt_version="qwen_vl_image_understanding",
            )
            if isinstance(data, dict):
                data.setdefault("modality", "image")
                data.setdefault("warnings", [])
                return data
        except Exception as exc:
            logger.warning(f"Qwen-VL 图像理解失败 ({filename}): {exc}")
        return None

    @staticmethod
    def _rule_fallback(image_path: str, research_question: str) -> Dict[str, Any]:
        """无 VLM 时的保守摘要 — 不编造图表内容。"""
        warnings: List[str] = []
        if not settings.QWEN_API_KEY:
            warnings.append("未配置 QWEN_API_KEY，无法执行 VLM 图像理解")
        elif settings.USE_MOCK_LLM:
            warnings.append("Mock LLM 模式，已跳过 VLM 图像理解")

        meta: Dict[str, Any] = {"filename": Path(image_path).name}
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                meta["width"] = img.width
                meta["height"] = img.height
                meta["mode"] = img.mode
        except Exception as exc:
            warnings.append(f"PIL 元数据读取失败: {exc}")

        return {
            "modality": "image",
            "summary": (
                f"图像 {meta.get('filename', '')} "
                f"({meta.get('width', '?')}×{meta.get('height', '?')})；"
                f"需配置 VLM 才能提取图表语义。"
            ),
            "detected_elements": [f"file:{meta.get('filename', '')}"],
            "chart_type": "unknown",
            "axis_labels": [],
            "key_trends": [],
            "possible_research_evidence": [],
            "warnings": warnings,
            "metadata_only": True,
            "research_question": research_question[:200],
        }
