"""数据集下载链接规范化（避免 HF ID 被浏览器当成相对路径）。"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

_HF_ID_RE = re.compile(r"^(?:datasets/)?([\w.-]+/[\w.-]+)(?:/.*)?$")


def normalize_dataset_download_url(
    url: Optional[str],
    *,
    name: str = "",
    source_type: str = "",
) -> str:
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
    if raw.startswith("/"):
        return raw
    m = _HF_ID_RE.match(raw.replace(" ", ""))
    if m or st in ("huggingface", "hf"):
        ds_id = m.group(1) if m else raw.strip().lstrip("/")
        if ds_id.startswith("datasets/"):
            ds_id = ds_id[len("datasets/") :]
        return f"https://huggingface.co/datasets/{quote(ds_id, safe='/-._')}"
    if "." in raw and " " not in raw and "/" in raw:
        return f"https://{raw.lstrip('/')}"
    return raw
