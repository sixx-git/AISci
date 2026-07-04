"""学术影响力预测 Skill"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult


class PaperFeatureExtractionSkill(BaseSkill):
    name = "PaperFeatureExtraction"
    description = "提取标题、摘要、全文结构、作者、机构、关键词"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        paper = input_data.get("paper") or input_data
        features = {
            "title": paper.get("title", ""),
            "abstract": (paper.get("abstract") or "")[:800],
            "authors": paper.get("authors") or paper.get("author_list", []),
            "year": paper.get("year"),
            "venue": paper.get("venue") or paper.get("journal", ""),
            "keywords": paper.get("keywords") or [],
            "doi": paper.get("doi", ""),
            "citation_count": paper.get("citation_count") or paper.get("citationCount"),
            "title_length": len(paper.get("title") or ""),
            "abstract_length": len(paper.get("abstract") or ""),
        }
        result.data = {"features": features}
        return result


class CitationGraphFeatureSkill(BaseSkill):
    name = "CitationGraphFeature"
    description = "提取引用网络、入度、出度、PageRank 近似"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        papers = input_data.get("papers") or input_data.get("citation_map") or []
        n = len(papers)
        in_deg = sum(1 for p in papers if (p.get("citation_count") or 0) > 0)
        avg_cites = sum((p.get("citation_count") or p.get("citationCount") or 0) for p in papers) / max(n, 1)
        pagerank_proxy = round(min(1.0, math.log1p(avg_cites) / 10), 4)
        result.data = {
            "graph_size": n,
            "in_degree_proxy": in_deg,
            "out_degree_proxy": n,
            "avg_citations": round(avg_cites, 2),
            "pagerank_proxy": pagerank_proxy,
        }
        return result


class EarlyImpactPredictionSkill(BaseSkill):
    name = "EarlyImpactPrediction"
    description = "预测 1/3/5 年引用量或高影响概率"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        features = input_data.get("features") or {}
        cites = float(features.get("citation_count") or 0)
        base = max(1.0, math.log1p(cites))
        result.data = {
            "predicted_citations_1y": round(base * 2.5, 1),
            "predicted_citations_3y": round(base * 6.0, 1),
            "predicted_citations_5y": round(base * 10.0, 1),
            "high_impact_probability": round(min(0.95, base / 15), 3),
            "model_note": "启发式基线，需历史数据校准",
        }
        return result


class BiasExplanationSkill(BaseSkill):
    name = "BiasExplanation"
    description = "解释领域、期刊、作者声誉、机构等偏差"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        features = input_data.get("features") or {}
        try:
            llm = qwen_structured_chat(
                prompt=f"分析以下论文特征中的潜在偏差来源:\n{features}",
                schema_example={
                    "bias_factors": [{"factor": "领域热度", "impact": "medium", "explanation": "..."}],
                    "summary": "...",
                },
                prompt_version="bias_explanation",
            )
            result.data = llm
        except Exception as exc:
            result.add_error(str(exc))
        return result


class ImpactCalibrationSkill(BaseSkill):
    name = "ImpactCalibration"
    description = "区分文本质量影响与已有声誉影响"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        text_score = float(input_data.get("text_quality_score", 7.0))
        rep_score = float(input_data.get("reputation_score", 5.0))
        calibrated = round(text_score * 0.6 + rep_score * 0.4, 2)
        result.data = {
            "text_quality_component": text_score,
            "reputation_component": rep_score,
            "calibrated_impact_score": calibrated,
            "interpretation": "calibrated 更接近可复现的文本贡献估计",
        }
        return result


class ReportInfluencePredictionSkill(BaseSkill):
    name = "ReportInfluencePrediction"
    description = "预测 AI 生成报告未来学术影响潜力"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        report = input_data.get("report_data") or {}
        compliance = input_data.get("compliance_metrics") or {}
        refs = int(compliance.get("references_verified") or 0)
        evidence = int(compliance.get("evidence_fact_count") or 0)
        score = min(10.0, 3.0 + refs * 0.3 + evidence * 0.2)
        try:
            llm = qwen_structured_chat(
                prompt=(
                    f"报告标题: {report.get('paper_title', '')[:200]}\n"
                    f"verified_refs={refs}, evidence_facts={evidence}\n"
                    "评估该 AI 科研报告的未来学术影响潜力（0-10）。"
                ),
                schema_example={
                    "influence_score": score,
                    "strengths": ["..."],
                    "risks": ["..."],
                    "recommendation": "...",
                },
                prompt_version="report_influence_prediction",
            )
            result.data = llm
        except Exception as exc:
            result.data = {"influence_score": score, "heuristic_only": True}
            result.add_warning(str(exc))
        return result
