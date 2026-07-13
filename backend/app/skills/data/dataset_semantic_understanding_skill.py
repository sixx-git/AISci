"""数据集语义理解 Skill — LLM 解释列角色与实验含义，规则 fallback。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()

VALID_COLUMN_ROLES = frozenset({
    "entity_key",
    "target_regression",
    "target_classification_binary",
    "target_classification_multi",
    "feature_numeric",
    "feature_categorical",
    "text_metadata",
    "timestamp",
    "id",
    "ignore",
})

TARGET_COLUMN_KEYWORDS = [
    "label", "target", "class", "y", "accuracy", "score", "result", "outcome",
    "行为", "类别", "标签", "准确率", "评分", "目标", "结果", "分类",
    "diagnosis", "prognosis", "response", "status", "flag",
    "label_col", "target_col", "outcome_col",
]

JOIN_KEY_HINTS = ("id", "key", "uuid", "index", "编号", "标识", "indicator", "sample", "patient", "client")


def llm_csv_parse_diagnostic(file_path: str, *, max_lines: int = 20) -> Optional[Dict[str, Any]]:
    """探查失败时，用 LLM 根据文件头部推断解析参数。"""
    if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
        return None
    if not file_path or not __import__("os").path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            raw_head = "".join(fh.readline() for _ in range(max_lines))
    except OSError:
        return None
    if not raw_head.strip():
        return None

    schema_example = {
        "separator": ";",
        "encoding": "utf-8",
        "has_header": True,
        "skip_rows": 0,
        "notes": "简要说明格式判断依据",
        "confidence": 0.8,
    }
    prompt = (
        "以下是一个表格文件的前若干行原始文本。请判断最合适的解析方式。\n"
        "仅根据可见内容推断，不要编造列名或行数。\n\n"
        f"```\n{raw_head[:4000]}\n```\n"
    )
    try:
        from app.services.qwen_client import qwen_structured_chat

        raw = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema_example,
            system_prompt="你是数据格式诊断助手。仅输出合法 JSON。",
            temperature=0.1,
            prompt_version="csv_parse_diagnostic_v1",
        )
        sep = raw.get("separator")
        if sep is not None:
            sep = str(sep)[:4]
            if sep.lower() in ("tab", "\\t"):
                sep = "\t"
        return {
            "separator": sep,
            "encoding": str(raw.get("encoding") or "utf-8")[:32],
            "has_header": bool(raw.get("has_header", True)),
            "skip_rows": int(raw.get("skip_rows") or 0),
            "notes": str(raw.get("notes") or "")[:500],
            "confidence": float(raw.get("confidence") or 0.5),
        }
    except Exception as exc:
        logger.warning("CSV 解析 LLM 诊断失败: %s", exc)
        return None


class DatasetSemanticUnderstandingSkill(BaseSkill):
    name = "DatasetSemanticUnderstanding"
    description = "基于探查结果与研究问题，用 LLM 理解列语义角色、目标变量与实验建议"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns = input_data.get("columns") or []
        if not isinstance(columns, list) or not columns:
            result.data = rule_fallback_semantic_schema(columns=[], dtypes={})
            result.add_warning("无列信息，跳过 LLM 语义理解")
            return result

        dtypes = input_data.get("dtypes") or {}
        if not isinstance(dtypes, dict):
            dtypes = {}
        preview = input_data.get("preview") or []
        statistics = input_data.get("statistics") or {}
        research_question = str(
            input_data.get("research_question")
            or context.get("research_question")
            or ""
        ).strip()
        project_mode = str(input_data.get("project_mode") or context.get("project_mode") or "general")

        semantic = await self._try_llm_semantic_schema(
            filename=str(input_data.get("filename") or ""),
            columns=[str(c) for c in columns],
            dtypes=dtypes,
            n_rows=int(input_data.get("n_rows") or 0),
            n_columns=int(input_data.get("n_columns") or len(columns)),
            preview=preview if isinstance(preview, list) else [],
            statistics=statistics if isinstance(statistics, dict) else {},
            research_question=research_question,
            project_mode=project_mode,
        )
        if not semantic:
            semantic = rule_fallback_semantic_schema(columns=[str(c) for c in columns], dtypes=dtypes)
            result.add_warning("使用规则 fallback 进行数据集语义理解（LLM 不可用或未返回有效结果）")
        else:
            semantic["source"] = "llm"

        result.data = semantic
        return result

    async def _try_llm_semantic_schema(
        self,
        *,
        filename: str,
        columns: List[str],
        dtypes: Dict[str, Any],
        n_rows: int,
        n_columns: int,
        preview: List[Any],
        statistics: Dict[str, Any],
        research_question: str,
        project_mode: str,
    ) -> Optional[Dict[str, Any]]:
        if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
            return None

        preview_text = json.dumps(preview[:5], ensure_ascii=False, default=str)[:3000]
        stats_text = json.dumps(
            {k: statistics[k] for k in list(statistics.keys())[:15]},
            ensure_ascii=False,
            default=str,
        )[:2500]

        schema_example = {
            "column_roles": {columns[0] if columns else "col_a": "feature_numeric"},
            "recommended_targets": ["col_b"],
            "join_keys": ["id"],
            "feature_columns": ["col_a"],
            "quality_issues": ["示例：某文本列过长不宜直接入模"],
            "experiment_hints": "适合进行的分析类型简述",
            "parsing_notes": "",
            "target_candidates": {
                "regression": ["Final Score"],
                "binary_classification": [],
                "multi_classification": [],
            },
            "numeric_field_candidates": ["score"],
            "categorical_field_candidates": [],
        }

        prompt = (
            "你是科学数据语义理解助手。根据引擎探查得到的客观元数据，推断各列在科研流水线中的角色。\n"
            "要求：\n"
            "1. column_roles 的键必须是下列列名之一，值必须是以下角色之一："
            f"{', '.join(sorted(VALID_COLUMN_ROLES))}\n"
            "2. recommended_targets / join_keys / feature_columns 必须是实际列名的子集\n"
            "3. 不要修改 n_rows/n_columns；不要编造不存在的列\n"
            "4. target_candidates 等字段与 column_roles 保持一致\n\n"
            f"文件名: {filename}\n"
            f"项目模式: {project_mode}\n"
            f"研究问题: {research_question or '（未提供）'}\n"
            f"行数: {n_rows}\n"
            f"列数: {n_columns}\n"
            f"列名: {', '.join(columns[:40])}\n"
            f"类型: {json.dumps(dtypes, ensure_ascii=False)[:2000]}\n"
            f"预览行: {preview_text}\n"
            f"统计摘要: {stats_text}\n"
        )

        try:
            from app.services.qwen_client import qwen_structured_chat

            raw = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                system_prompt="仅输出合法 JSON，不要 markdown。",
                temperature=0.15,
                prompt_version="dataset_semantic_v1",
            )
            return normalize_semantic_schema(raw, columns=columns, dtypes=dtypes)
        except Exception as exc:
            logger.warning("数据集语义 LLM 解析失败: %s", exc)
            return None


def rule_fallback_semantic_schema(
    *,
    columns: List[str],
    dtypes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """关键词规则 fallback，产出与 LLM 相同结构的 semantic_schema。"""
    dtypes = dtypes or {}
    target_candidates: Dict[str, List[str]] = {
        "binary_classification": [],
        "multi_classification": [],
        "regression": [],
        "generic_metric": [],
        "generic_target": [],
    }
    column_roles: Dict[str, str] = {}
    join_keys: List[str] = []
    numeric_fields: List[str] = []
    categorical_fields: List[str] = []

    for col in columns:
        col_lower = col.lower().strip()
        dtype_str = str(dtypes.get(col, "")).lower()

        if any(h in col_lower for h in JOIN_KEY_HINTS):
            column_roles[col] = "entity_key"
            join_keys.append(col)
        elif any(kw.lower() in col_lower for kw in TARGET_COLUMN_KEYWORDS):
            if any(k in col_lower for k in ("label", "class", "category", "类别", "标签", "分类", "diagnosis")):
                if "binary" in col_lower:
                    column_roles[col] = "target_classification_binary"
                    target_candidates["binary_classification"].append(col)
                    categorical_fields.append(col)
                else:
                    column_roles[col] = "target_classification_multi"
                    target_candidates["multi_classification"].append(col)
                    categorical_fields.append(col)
            elif any(k in col_lower for k in ("accuracy", "score", "result", "outcome", "评分", "准确率", "结果")):
                column_roles[col] = "target_regression"
                target_candidates["regression"].append(col)
                numeric_fields.append(col)
            else:
                column_roles[col] = "target_regression"
                target_candidates["generic_target"].append(col)
        elif any(k in dtype_str for k in ("int", "float", "double", "decimal", "numeric", "bigint")):
            column_roles[col] = "feature_numeric"
            numeric_fields.append(col)
        elif any(k in col_lower for k in ("motivation", "description", "comment", "text", "note", "说明", "描述")):
            column_roles[col] = "text_metadata"
        else:
            column_roles[col] = "feature_categorical"
            categorical_fields.append(col)

    recommended = list(dict.fromkeys(
        target_candidates["regression"]
        + target_candidates["binary_classification"]
        + target_candidates["multi_classification"]
        + target_candidates["generic_target"]
    ))[:5]
    feature_columns = [
        c for c, role in column_roles.items()
        if role in ("feature_numeric", "feature_categorical")
    ][:30]

    return {
        "source": "rule_fallback",
        "column_roles": column_roles,
        "recommended_targets": recommended,
        "join_keys": list(dict.fromkeys(join_keys))[:10],
        "feature_columns": feature_columns,
        "quality_issues": [],
        "experiment_hints": "",
        "parsing_notes": "",
        "target_candidates": {k: v for k, v in target_candidates.items() if v},
        "numeric_field_candidates": list(dict.fromkeys(numeric_fields))[:20],
        "categorical_field_candidates": list(dict.fromkeys(categorical_fields))[:20],
        "generic_metric_candidates": list(dict.fromkeys(
            target_candidates["regression"] + target_candidates["generic_target"]
        ))[:20],
    }


def normalize_semantic_schema(
    raw: Dict[str, Any],
    *,
    columns: List[str],
    dtypes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """校验并裁剪 LLM 输出，确保列名合法。"""
    dtypes = dtypes or {}
    col_set = set(columns)

    def _filter_cols(vals: Any, limit: int = 30) -> List[str]:
        if not isinstance(vals, list):
            return []
        out: List[str] = []
        for v in vals:
            s = str(v).strip()
            if s in col_set and s not in out:
                out.append(s)
            if len(out) >= limit:
                break
        return out

    roles_in = raw.get("column_roles") if isinstance(raw.get("column_roles"), dict) else {}
    column_roles: Dict[str, str] = {}
    for col, role in roles_in.items():
        if col not in col_set:
            continue
        role_str = str(role).strip()
        if role_str not in VALID_COLUMN_ROLES:
            role_str = "feature_categorical"
        column_roles[col] = role_str
    for col in columns:
        column_roles.setdefault(col, "feature_categorical")

    recommended_targets = _filter_cols(raw.get("recommended_targets"), 10)
    join_keys = _filter_cols(raw.get("join_keys"), 10)
    feature_columns = _filter_cols(raw.get("feature_columns"), 30)

    tc_in = raw.get("target_candidates") if isinstance(raw.get("target_candidates"), dict) else {}
    target_candidates: Dict[str, List[str]] = {}
    for key in ("regression", "binary_classification", "multi_classification", "generic_metric", "generic_target"):
        target_candidates[key] = _filter_cols(tc_in.get(key), 15)

    if not recommended_targets:
        recommended_targets = list(dict.fromkeys(
            target_candidates.get("regression", [])
            + target_candidates.get("binary_classification", [])
            + target_candidates.get("multi_classification", [])
            + target_candidates.get("generic_target", [])
        ))[:5]

    quality_issues = raw.get("quality_issues")
    if not isinstance(quality_issues, list):
        quality_issues = []
    quality_issues = [str(x)[:300] for x in quality_issues if x][:8]

    fallback = rule_fallback_semantic_schema(columns=columns, dtypes=dtypes)
    numeric_field_candidates = _filter_cols(
        raw.get("numeric_field_candidates") or fallback.get("numeric_field_candidates"),
        20,
    )
    categorical_field_candidates = _filter_cols(
        raw.get("categorical_field_candidates") or fallback.get("categorical_field_candidates"),
        20,
    )
    if not any(target_candidates.values()):
        target_candidates = fallback.get("target_candidates", {})

    return {
        "source": "llm",
        "column_roles": column_roles,
        "recommended_targets": recommended_targets,
        "join_keys": join_keys or fallback.get("join_keys", []),
        "feature_columns": feature_columns or fallback.get("feature_columns", []),
        "quality_issues": quality_issues,
        "experiment_hints": str(raw.get("experiment_hints") or "")[:800],
        "parsing_notes": str(raw.get("parsing_notes") or "")[:500],
        "target_candidates": {k: v for k, v in target_candidates.items() if v},
        "numeric_field_candidates": numeric_field_candidates,
        "categorical_field_candidates": categorical_field_candidates,
        "generic_metric_candidates": _filter_cols(
            raw.get("generic_metric_candidates") or fallback.get("generic_metric_candidates"),
            20,
        ),
    }


def merge_semantic_into_metadata(
    existing_meta: Dict[str, Any],
    semantic_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """将 semantic_schema 与兼容字段写入 extra_metadata。"""
    merged = dict(existing_meta)
    merged["semantic_schema"] = {
        k: semantic_payload.get(k)
        for k in (
            "source", "column_roles", "recommended_targets", "join_keys",
            "feature_columns", "quality_issues", "experiment_hints", "parsing_notes",
        )
        if semantic_payload.get(k) is not None
    }
    for legacy_key in (
        "target_candidates",
        "numeric_field_candidates",
        "categorical_field_candidates",
        "generic_metric_candidates",
    ):
        if semantic_payload.get(legacy_key):
            merged[legacy_key] = semantic_payload[legacy_key]
    return merged
