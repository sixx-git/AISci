"""补充材料下载 Skill"""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from app.services.data_sources.repository_connector import MAX_DOWNLOAD_BYTES, _download_file
from app.skills.base import BaseSkill, SkillResult

ALLOWED_SUPP_EXT = {".pdf", ".csv", ".tsv", ".xlsx", ".xls", ".zip", ".json", ".txt"}


class SupplementaryFetchSkill(BaseSkill):
    name = "SupplementaryFetch"
    description = "下载论文补充材料链接到本地"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        links = input_data.get("supplementary_links", []) or []
        paper_id = input_data.get("paper_id", "")
        output_dir = input_data.get("output_dir", "")

        if not links:
            result.data = {"files": [], "paper_id": paper_id}
            return result

        os.makedirs(output_dir, exist_ok=True)
        fetched: List[Dict[str, Any]] = []

        for url in links[:5]:
            if not url or not url.startswith("http"):
                continue
            try:
                parsed = urllib.parse.urlparse(url)
                fname = os.path.basename(parsed.path) or "supplementary.dat"
                if "." not in fname:
                    fname += ".bin"
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ALLOWED_SUPP_EXT and ext != ".bin":
                    result.add_warning(f"跳过不支持的补充材料类型: {url}")
                    continue
                safe = re.sub(r"[^\w.\-]", "_", f"{paper_id}_{fname}")[:100]
                local = _download_file(url, output_dir, safe)
                fetched.append({
                    "paper_id": paper_id,
                    "url": url,
                    "local_path": local,
                    "file_ext": ext,
                    "source_type": "supplementary",
                })
            except Exception as exc:
                result.add_warning(f"补充材料下载失败 {url[:60]}: {exc}")

        result.data = {"files": fetched, "paper_id": paper_id, "count": len(fetched)}
        if links and not fetched:
            result.add_warning("补充材料链接均未成功下载")
        return result
