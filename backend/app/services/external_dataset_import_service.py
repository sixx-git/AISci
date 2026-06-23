"""外部数据集自动入库 — HuggingFace + 开放仓库"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20
MAX_ROWS = 2000


def _safe_dataset_id(name: str) -> Optional[str]:
    if not name:
        return None
    text = name.strip()
    if "/" in text:
        return text
    return None


def _fetch_hf_first_rows(dataset_id: str, max_rows: int = 500) -> Dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "dataset": dataset_id,
            "config": "default",
            "split": "train",
        }
    )
    url = f"https://datasets-server.huggingface.co/first-rows?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _rows_to_csv(rows_payload: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    features = rows_payload.get("features") or []
    row_items = rows_payload.get("rows") or []
    if not row_items:
        raise ValueError("HF 数据集无可用行")

    col_names = [f.get("name") for f in features if f.get("name")]
    if not col_names and row_items:
        first_row = row_items[0].get("row") or {}
        col_names = list(first_row.keys())

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    written = 0
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=col_names + ["_provenance_source_type"])
        writer.writeheader()
        for item in row_items[:MAX_ROWS]:
            row = dict(item.get("row") or {})
            row["_provenance_source_type"] = "hf_dataset"
            writer.writerow({k: row.get(k, "") for k in col_names + ["_provenance_source_type"]})
            written += 1

    return {
        "row_count": written,
        "columns": col_names + ["_provenance_source_type"],
        "csv_path": output_path,
    }


def import_huggingface_candidate(
    candidate: Dict[str, Any],
    output_dir: str,
    *,
    max_rows: int = 500,
) -> Dict[str, Any]:
    dataset_id = _safe_dataset_id(candidate.get("dataset_name") or candidate.get("url") or "")
    if not dataset_id:
        url = candidate.get("url") or ""
        m = re.search(r"huggingface\.co/datasets/([^/\s?#]+/[^/\s?#]+)", url)
        if m:
            dataset_id = m.group(1)

    if not dataset_id:
        raise ValueError("无法解析 HuggingFace dataset id")

    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", dataset_id.replace("/", "_"))
    output_path = os.path.join(output_dir, f"hf_{safe_name}.csv")

    try:
        payload = _fetch_hf_first_rows(dataset_id, max_rows=max_rows)
        meta = _rows_to_csv(payload, output_path)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning("HF 导入失败 %s: %s", dataset_id, exc)
        raise ValueError(f"HuggingFace 数据集下载失败: {exc}") from exc

    return {
        "source_platform": "HuggingFace Datasets",
        "dataset_name": dataset_id,
        "dataset_id": dataset_id,
        "csv_path": meta["csv_path"],
        "row_count": meta["row_count"],
        "columns": meta["columns"],
        "import_method": "datasets_server_api",
        "provenance_source_type": "hf_dataset",
    }


def auto_import_external_candidates(
    candidates: List[Dict[str, Any]],
    output_dir: str,
    *,
    max_imports: int = 2,
) -> Dict[str, Any]:
    """同步入口：HF + Zenodo/Figshare（通过 registry）。"""
    import asyncio

    return asyncio.run(auto_import_external_candidates_async(candidates, output_dir, max_imports=max_imports))


async def auto_import_external_candidates_async(
    candidates: List[Dict[str, Any]],
    output_dir: str,
    *,
    max_imports: int = 2,
) -> Dict[str, Any]:
    imported: List[Dict[str, Any]] = []
    errors: List[str] = []

    ranked = _rank_import_candidates(candidates)
    for cand in ranked[:max_imports]:
        platform = (cand.get("source_platform") or "").lower()
        try:
            if "huggingface" in platform or "huggingface.co" in (cand.get("url") or "").lower():
                item = import_huggingface_candidate(cand, output_dir)
                item["candidate_url"] = cand.get("url")
                imported.append(item)
                cand["imported"] = True
                cand["imported_csv_path"] = item["csv_path"]
            elif any(x in platform for x in ("zenodo", "figshare", "dryad")) or "zenodo.org" in (cand.get("url") or "").lower():
                from app.services.data_sources.registry import fetch_candidate
                from app.skills.data_finder._utils import new_id

                assets = await fetch_candidate(cand, output_dir)
                for asset in assets:
                    item = {
                        "source_platform": cand.get("source_platform", "Repository"),
                        "dataset_name": cand.get("dataset_name", asset.source_title),
                        "csv_path": asset.local_path,
                        "row_count": asset.row_count,
                        "columns": asset.columns,
                        "import_method": asset.extraction_method,
                        "table_id": new_id("ext"),
                    }
                    imported.append(item)
                    cand["imported"] = True
                    cand["imported_csv_path"] = asset.local_path
            else:
                errors.append(f"暂不支持自动导入: {platform or cand.get('url', '')[:40]}")
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(str(exc))

    return {
        "imported": imported,
        "imported_count": len(imported),
        "errors": errors,
    }


def _rank_import_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from app.services.data_sources.base import normalize_legacy_candidate

    ranked: List[Dict[str, Any]] = []
    for c in candidates or []:
        nc = normalize_legacy_candidate(c)
        if nc.get("import_supported") is False:
            continue
        platform = (nc.get("source_platform") or "").lower()
        score = float(nc.get("confidence") or 0.5)
        if "huggingface" in platform:
            score += 0.15
        if "zenodo" in platform:
            score += 0.12
        if nc.get("imported"):
            continue
        ranked.append({**nc, "_rank": score})
    ranked.sort(key=lambda x: x.get("_rank", 0), reverse=True)
    return [{k: v for k, v in c.items() if k != "_rank"} for c in ranked]
