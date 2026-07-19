"""小样验证数据不匹配时的数据集需求与下载指引。"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

from app.services.experiment_spec_service import collect_available_columns

logger = logging.getLogger(__name__)

UPLOAD_REQUIRED = "required"
UPLOAD_OPTIONAL = "optional"
UPLOAD_SKIP_OK = "skip_ok"

UPLOAD_REQUIREMENT_LABELS: Dict[str, str] = {
    UPLOAD_REQUIRED: "必须上传",
    UPLOAD_OPTIONAL: "可选（增强验证）",
    UPLOAD_SKIP_OK: "可不上传（当前数据可保留作探索）",
}

_DOMAIN_DATASET_HINTS: Dict[str, List[Dict[str, str]]] = {
    "federated": [
        {
            "dataset_name": "LEAF (Federated Learning Benchmark)",
            "source_platform": "GitHub",
            "download_url": "https://github.com/TalwalkarLab/leaf",
            "description": "联邦学习经典 benchmark（FEMNIST、Shakespeare 等），适合 FedAvg/Non-IID 小样验证",
        },
        {
            "dataset_name": "HuggingFace 联邦学习数据集检索",
            "source_platform": "HuggingFace",
            "download_url": "https://huggingface.co/datasets?search=federated+learning+benchmark",
            "description": "按「federated learning benchmark」检索可下载表格/分区数据",
        },
    ],
    "classification": [
        {
            "dataset_name": "UCI Hepatitis（含 carcinoma 等字段）",
            "source_platform": "UCI",
            "download_url": "https://archive.ics.uci.edu/dataset/46/hepatitis",
            "description": "经典医学分类表格，含 carcinoma、jaundice 等列，适合 accuracy/F1 小样验证",
        },
        {
            "dataset_name": "HuggingFace 表格分类数据集",
            "source_platform": "HuggingFace",
            "download_url": "https://huggingface.co/datasets?search=tabular+classification+medical",
            "description": "医学/表格分类公开数据检索入口",
        },
    ],
}


def _detect_hypothesis_domains(text: str) -> set[str]:
    blob = (text or "").lower()
    domains: set[str] = set()
    if any(k in blob for k in ("federated", "fedavg", "fedprox", "联邦", "non-iid", "client")):
        domains.add("federated")
    if any(k in blob for k in ("carcinoma", "classification", "分类", "f1", "accuracy", "auc")):
        domains.add("classification")
    return domains


def _domain_hint_datasets(hypothesis: str, methods: str, metrics: str) -> List[Dict[str, Any]]:
    domains = _detect_hypothesis_domains(f"{hypothesis} {methods} {metrics}")
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for domain in ("federated", "classification"):
        if domain not in domains:
            continue
        for item in _DOMAIN_DATASET_HINTS.get(domain, []):
            key = (item.get("dataset_name") or "").lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({**item, "role": "domain_hint"})
    return out


def _build_search_portal_links(query: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote((query or "machine learning dataset").strip()[:200])
    return [
        {
            "dataset_name": "HuggingFace Datasets 搜索",
            "download_url": f"https://huggingface.co/datasets?search={q}",
            "source_platform": "HuggingFace",
            "description": "开放 API 未命中时的检索入口（网页大模型常推荐此来源）",
            "role": "search_portal",
        },
        {
            "dataset_name": "Zenodo 搜索",
            "download_url": f"https://zenodo.org/search?q={q}",
            "source_platform": "Zenodo",
            "description": "科研数据仓库全文检索",
            "role": "search_portal",
        },
        {
            "dataset_name": "Google Dataset Search",
            "download_url": f"https://datasetsearch.research.google.com/search?query={q}",
            "source_platform": "Google",
            "description": "跨平台数据集聚合搜索",
            "role": "search_portal",
        },
    ]


def _llm_suggest_public_datasets_sync(
    *,
    hypothesis: str,
    methods: str,
    metrics: str,
    required_data: str,
    uploaded_columns: List[str],
) -> List[Dict[str, Any]]:
    from app.core.config import get_settings
    from app.services.qwen_client import qwen_structured_chat

    settings = get_settings()
    if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
        return []

    col_hint = "、".join(uploaded_columns[:8]) if uploaded_columns else "（无）"
    schema = {
        "datasets": [{
            "dataset_name": "LEAF FEMNIST",
            "source_platform": "HuggingFace",
            "search_url": "https://huggingface.co/datasets?search=LEAF+FEMNIST",
            "description": "为何与假设相关",
            "upload_requirement": "required",
        }],
    }
    prompt = (
        "推荐 3–5 个真实存在、可公开检索的数据集，帮助用户完成小样验证。\n"
        "不要编造 Zenodo record ID；使用 search_url（官方页或搜索页）。\n"
        "若假设是联邦学习而用户上传的是 FHIR/合规表，应推荐联邦 benchmark，不要只推荐 carcinoma 医学集。\n"
        f"已上传字段：{col_hint}\n"
        f"假设：{hypothesis[:800]}\n方法：{(methods or '')[:400]}\n指标：{(metrics or '')[:200]}\n"
        f"所需数据：{(required_data or '')[:400]}\n"
    )
    try:
        raw = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            prompt_version="validation_dataset_suggest_v1",
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("LLM 数据集推荐失败: %s", exc)
        return []

    out: List[Dict[str, Any]] = []
    for item in raw.get("datasets") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("search_url") or item.get("download_url") or "").strip()
        name = str(item.get("dataset_name") or "").strip()
        if not name:
            continue
        req = str(item.get("upload_requirement") or "optional").lower()
        out.append({
            "dataset_name": name,
            "source_platform": str(item.get("source_platform") or "Web"),
            "download_url": url,
            "description": str(item.get("description") or "")[:500],
            "upload_requirement": UPLOAD_REQUIRED if req == "required" else UPLOAD_OPTIONAL,
            "role": "llm_suggestion",
        })
    return out


def normalize_download_item(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, str) and item.strip():
        return {
            "dataset_name": item.strip(),
            "source_platform": "",
            "url": "",
            "download_url": "",
            "description": "",
        }
    if not isinstance(item, dict):
        return None
    url = str(
        item.get("download_url")
        or item.get("url")
        or item.get("source_url")
        or item.get("landing_page_url")
        or ""
    ).strip()
    name = str(item.get("dataset_name") or item.get("name") or "").strip()
    if not name and not url:
        return None
    return {
        "dataset_name": name or "未命名数据集",
        "source_platform": str(item.get("source_platform") or item.get("source") or ""),
        "url": url,
        "download_url": url,
        "description": str(item.get("description") or "")[:500],
        "license": str(item.get("license") or ""),
        "task_type": str(item.get("task_type") or ""),
        "availability": str(item.get("availability") or "catalog_only"),
        "import_supported": bool(item.get("import_supported", False)),
    }


def fetch_recommended_downloads_sync(query_input: Dict[str, Any], *, max_results: int = 8) -> List[Dict[str, Any]]:
    """按假设/实验设计动态检索开放数据集下载链接。"""
    if not isinstance(query_input, dict):
        return []
    try:
        from app.skills.data.dataset_discovery_skill import DatasetDiscoverySkill

        skill = DatasetDiscoverySkill()
        result = asyncio.run(
            skill.run(
                input_data={**query_input, "max_results": max_results},
                context={"stage": "small_validation_guidance"},
            )
        )
        data = result.data if isinstance(result.data, dict) else {}
        raw = data.get("datasets") or []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw:
            norm = normalize_download_item(item)
            if not norm:
                continue
            key = (norm.get("dataset_name") or "").lower() + "|" + (norm.get("download_url") or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(norm)
        return out
    except Exception as exc:
        logger.warning("小样验证数据集检索失败: %s", exc)
        return []


def _dedupe_dataset_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        key = (
            str(item.get("name") or "").lower()
            + "|"
            + str(item.get("download_url") or "").lower()
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def build_validation_data_guidance(
    experiment_design: Optional[Dict[str, Any]],
    project_datasets: Optional[List[Dict[str, Any]]] = None,
    *,
    hypothesis: str = "",
    blockers: Optional[List[str]] = None,
    fetch_downloads: bool = True,
) -> Dict[str, Any]:
    """构建小样验证阻塞时的数据需求、下载地址与上传优先级说明。"""
    ed = experiment_design or {}
    dr = ed.get("data_requirements") if isinstance(ed.get("data_requirements"), dict) else {}
    adequacy = dr.get("adequacy") if isinstance(dr.get("adequacy"), dict) else ed.get("data_adequacy") or {}
    if not isinstance(adequacy, dict):
        adequacy = {}

    status = str(adequacy.get("status") or dr.get("upload_status") or "").lower()
    mismatch = [
        str(x) for x in (
            adequacy.get("mismatch_reasons")
            or dr.get("gaps")
            or ed.get("data_gap")
            or blockers
            or []
        )
        if x
    ]
    what_needs = [str(x) for x in (adequacy.get("what_hypothesis_needs") or []) if x]
    what_can = [str(x) for x in (adequacy.get("what_uploaded_can_do") or []) if x]
    uploaded = [d for d in (project_datasets or []) if isinstance(d, dict)]
    required_specs = [
        x for x in (dr.get("required_datasets") or adequacy.get("required_datasets") or [])
        if isinstance(x, dict)
    ]

    recommended: List[Dict[str, Any]] = []
    for src in (
        dr.get("recommended_public_datasets"),
        ed.get("recommended_public_datasets"),
    ):
        if isinstance(src, list):
            for item in src:
                norm = normalize_download_item(item)
                if norm:
                    recommended.append(norm)

    seen_rec: set[str] = set()
    deduped_rec: List[Dict[str, Any]] = []
    for rec in recommended:
        key = (rec.get("dataset_name") or "").lower() + "|" + (rec.get("download_url") or "")
        if key in seen_rec:
            continue
        seen_rec.add(key)
        deduped_rec.append(rec)
    recommended = deduped_rec

    keywords: List[str] = []
    for spec in required_specs:
        keywords.extend(str(k) for k in (spec.get("search_keywords") or []) if k)
    search_blob = " ".join([
        hypothesis or ed.get("hypothesis") or "",
        dr.get("required_data_description") or "",
        ed.get("methods") or "",
        ed.get("metrics") or "",
        " ".join(what_needs[:5]),
    ]).strip()
    if search_blob:
        keywords = list(dict.fromkeys(keywords + search_blob.split()[:20]))[:20]

    discovery_notes: List[str] = []
    api_search_query = search_blob or " ".join(keywords[:12])

    if fetch_downloads and len(recommended) < 2:
        query = {
            "hypothesis": hypothesis or ed.get("hypothesis") or "",
            "required_data": dr.get("required_data_description") or "",
            "research_question": adequacy.get("recommended_search_query") or api_search_query,
            "datasets": ed.get("datasets") or "",
            "methods": ed.get("methods") or "",
            "metrics": ed.get("metrics") or "",
            "keywords": keywords[:12],
        }
        api_results = fetch_recommended_downloads_sync(query)
        if not api_results:
            discovery_notes.append(
                "自动检索（Zenodo/HuggingFace/Figshare）未返回高相关结果；"
                "已补充领域常用数据集与搜索入口（与网页大模型推荐来源类似）"
            )
        for item in api_results:
            key = (item.get("dataset_name") or "").lower() + "|" + (item.get("download_url") or "")
            if key not in seen_rec:
                seen_rec.add(key)
                recommended.append(item)

    uploaded_cols = sorted(collect_available_columns(uploaded))
    if len(recommended) < 2:
        for hint in _domain_hint_datasets(
            hypothesis or ed.get("hypothesis") or "",
            ed.get("methods") or "",
            ed.get("metrics") or "",
        ):
            key = (hint.get("dataset_name") or "").lower()
            if key not in seen_rec:
                seen_rec.add(key)
                recommended.append(hint)

    if len(recommended) < 2:
        for item in _llm_suggest_public_datasets_sync(
            hypothesis=hypothesis or ed.get("hypothesis") or "",
            methods=ed.get("methods") or "",
            metrics=ed.get("metrics") or "",
            required_data=dr.get("required_data_description") or "",
            uploaded_columns=uploaded_cols,
        ):
            key = (item.get("dataset_name") or "").lower() + "|" + (item.get("download_url") or "")
            if key not in seen_rec:
                seen_rec.add(key)
                recommended.append(item)
                discovery_notes.append("含大模型辅助推荐（外部 API 未命中时）")

    search_portals = _build_search_portal_links(api_search_query)

    dataset_items: List[Dict[str, Any]] = []

    for spec in required_specs[:6]:
        dataset_items.append({
            "name": str(spec.get("name") or "假设验证所需主数据集"),
            "description": str(spec.get("description") or ""),
            "modality": str(spec.get("modality") or "tabular"),
            "required_columns": [str(c) for c in (spec.get("required_columns") or []) if c][:20],
            "upload_requirement": UPLOAD_REQUIRED,
            "upload_requirement_label": UPLOAD_REQUIREMENT_LABELS[UPLOAD_REQUIRED],
            "download_url": "",
            "source_platform": "",
            "role": "hypothesis_validation",
        })

    required_with_url = 0
    from app.core.dataset_urls import normalize_dataset_download_url

    for idx, rec in enumerate(recommended[:8]):
        url = normalize_dataset_download_url(
            str(rec.get("download_url") or rec.get("url") or "").strip(),
            name=str(rec.get("dataset_name") or rec.get("name") or ""),
            source_type=str(rec.get("source_platform") or rec.get("source") or ""),
        )
        preset_req = rec.get("upload_requirement")
        if preset_req in (UPLOAD_REQUIRED, UPLOAD_OPTIONAL):
            upload_req = preset_req
        elif status == "partial" and idx == 0:
            upload_req = UPLOAD_OPTIONAL
        elif idx < 2 and (status == "inadequate" or not required_specs):
            upload_req = UPLOAD_REQUIRED
            if url:
                required_with_url += 1
        else:
            upload_req = UPLOAD_OPTIONAL
        dataset_items.append({
            "name": rec.get("dataset_name") or f"推荐数据集 {idx + 1}",
            "description": rec.get("description") or "",
            "modality": "tabular",
            "required_columns": [],
            "upload_requirement": upload_req,
            "upload_requirement_label": UPLOAD_REQUIREMENT_LABELS.get(
                upload_req, UPLOAD_REQUIREMENT_LABELS[UPLOAD_OPTIONAL]
            ),
            "download_url": url,
            "source_platform": rec.get("source_platform") or "",
            "license": rec.get("license") or "",
            "availability": rec.get("availability") or "",
            "import_supported": rec.get("import_supported"),
            "role": rec.get("role") or "public_download",
        })

    for portal in search_portals:
        dataset_items.append({
            "name": portal.get("dataset_name") or "数据集搜索",
            "description": portal.get("description") or "",
            "modality": "tabular",
            "required_columns": [],
            "upload_requirement": UPLOAD_OPTIONAL,
            "upload_requirement_label": UPLOAD_REQUIREMENT_LABELS[UPLOAD_OPTIONAL],
            "download_url": portal.get("download_url") or "",
            "source_platform": portal.get("source_platform") or "",
            "role": "search_portal",
        })

    for ds in uploaded[:5]:
        cols = ds.get("columns") or []
        dataset_items.append({
            "name": str(ds.get("filename") or "已上传数据集"),
            "description": "已上传但与当前假设验证目标不匹配；可保留用于探索性分析，不能替代主验证数据",
            "modality": str(ds.get("data_type") or "tabular"),
            "required_columns": [str(c) for c in cols[:12]],
            "upload_requirement": UPLOAD_SKIP_OK,
            "upload_requirement_label": UPLOAD_REQUIREMENT_LABELS[UPLOAD_SKIP_OK],
            "download_url": "",
            "source_platform": "user_upload",
            "role": "uploaded_insufficient",
        })

    dataset_items = _dedupe_dataset_items(dataset_items)

    required_columns = [str(c) for c in (dr.get("required_columns") or []) if c][:24]
    if not required_columns:
        spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}
        if spec.get("target_column"):
            required_columns.append(str(spec["target_column"]))
        for col in spec.get("feature_columns") or []:
            if col and col not in required_columns:
                required_columns.append(str(col))

    must_upload = [d for d in dataset_items if d.get("upload_requirement") == UPLOAD_REQUIRED]
    optional_upload = [d for d in dataset_items if d.get("upload_requirement") == UPLOAD_OPTIONAL]
    skip_ok = [d for d in dataset_items if d.get("upload_requirement") == UPLOAD_SKIP_OK]

    if mismatch:
        summary = mismatch[0]
    elif uploaded and status == "inadequate":
        summary = (
            "已上传数据与假设验证目标不匹配（例如 FHIR 合规表无法验证联邦学习/F1）。"
            "请下载下方「必须上传」的数据集，或调整假设。"
        )
    elif not uploaded:
        summary = "尚未上传数据集；请下载推荐数据并上传，或上传与假设匹配的 CSV。"
    elif status == "inadequate":
        summary = "已上传数据与假设验证目标不匹配，请按下方指引补充数据集。"
    elif status == "partial":
        summary = "当前数据仅部分支持假设验证，建议补充推荐数据集以完成完整小样验证。"
    else:
        summary = "数据字段与实验方案未完全对齐，请补充所需数据集后重跑小样验证。"

    next_steps = [
        "下载并上传标记为「必须上传」的数据集（见下表下载地址）",
        "在「数据集」页完成上传后，重跑实验设计与小样验证",
    ]
    if optional_upload:
        next_steps.append("标记为「可选」的数据集可提升验证完整性，但非阻塞项")
    if skip_ok:
        next_steps.append("已上传的不匹配数据可不上传或删除，不影响补充新数据")

    return {
        "summary": summary,
        "adequacy_status": status or None,
        "mismatch_reasons": mismatch,
        "what_hypothesis_needs": what_needs,
        "what_uploaded_can_do": what_can,
        "required_columns": required_columns,
        "dataset_requirements": dataset_items,
        "must_upload_count": len(must_upload),
        "optional_upload_count": len(optional_upload),
        "skip_ok_count": len(skip_ok),
        "downloads_available_count": sum(
            1 for d in dataset_items if str(d.get("download_url") or "").strip()
        ),
        "next_steps": next_steps,
        "upload_requirement_legend": UPLOAD_REQUIREMENT_LABELS,
        "discovery_notes": discovery_notes,
        "search_query_used": api_search_query[:300],
    }
