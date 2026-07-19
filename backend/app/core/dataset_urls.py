"""将数据集 download_url 规范为可点击的绝对地址。"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import quote


_HF_ID_RE = re.compile(r"^(?:datasets/)?([\w.-]+/[\w.-]+)(?:/.*)?$")


def _hf_datasets_base() -> str:
    try:
        from app.core.config import get_settings

        endpoint = (getattr(get_settings(), "HF_ENDPOINT", "") or "").strip().rstrip("/")
        if endpoint:
            return f"{endpoint}/datasets"
    except Exception:
        pass
    return "https://huggingface.co/datasets"


def normalize_dataset_download_url(
    url: Optional[str],
    *,
    name: str = "",
    source_type: str = "",
) -> str:
    """把 HF ID / 相对路径转为绝对 https URL；已是 http(s) 则原样返回。"""
    raw = (url or "").strip()
    st = (source_type or "").strip().lower()

    if not raw and st in ("huggingface", "hf") and "/" in (name or ""):
        raw = name.strip()

    if not raw:
        return ""

    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("//"):
        return f"https:{raw}"

    # 站点内 API 相对路径（少见）：保留，由前端拼 origin
    if raw.startswith("/"):
        return raw

    # HuggingFace dataset id: org/name
    m = _HF_ID_RE.match(raw.replace(" ", ""))
    if m or st in ("huggingface", "hf"):
        ds_id = m.group(1) if m else raw.strip().lstrip("/")
        if ds_id.startswith("datasets/"):
            ds_id = ds_id[len("datasets/") :]
        return f"{_hf_datasets_base()}/{quote(ds_id, safe='/-._')}"

    # 裸域名
    if "." in raw and " " not in raw and "/" in raw:
        return f"https://{raw.lstrip('/')}"

    return raw


def normalize_dataset_rec_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    out = dict(item)
    url = normalize_dataset_download_url(
        out.get("download_url") or out.get("url") or "",
        name=str(out.get("name") or out.get("dataset_name") or ""),
        source_type=str(out.get("source_type") or out.get("source_platform") or ""),
    )
    if url:
        out["download_url"] = url
        if "url" in out or out.get("url"):
            out["url"] = url
    return out
