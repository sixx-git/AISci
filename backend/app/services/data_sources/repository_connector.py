"""开放仓库连接器 — Zenodo / Figshare 等（search + fetch）"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional

from app.services.data_sources.base import CandidateHit, FetchedAsset

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25MB
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json"}


class RepositoryConnector:
    name = "Repository"

    async def search(
        self,
        query: str,
        data_spec: Dict[str, Any],
        *,
        limit: int = 5,
    ) -> List[CandidateHit]:
        from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill

        hits: List[CandidateHit] = []
        zen = ExternalDatasetSearchSkill._search_zenodo(query)
        for item in (zen.get("results") or [])[:limit]:
            hits.append(CandidateHit(
                source_platform=item.get("source_platform", "Zenodo"),
                dataset_name=item.get("dataset_name", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                license=str(item.get("license", "")),
                confidence=float(item.get("confidence", 0.72)),
                record_id=_zenodo_id_from_url(item.get("url", "")),
                availability="search_and_import",
                import_supported=True,
                api_type="live",
                size_hint_bytes=25 * 1024 * 1024,
            ))
        fig = _search_figshare(query)
        for item in (fig.get("results") or [])[: max(0, limit - len(hits))]:
            hits.append(CandidateHit(
                source_platform="Figshare",
                dataset_name=item.get("dataset_name", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                license=str(item.get("license", "")),
                confidence=float(item.get("confidence", 0.68)),
                record_id=str(item.get("record_id", "")),
                availability="search_and_import",
                import_supported=True,
                api_type="live",
            ))
        return hits

    async def fetch(
        self,
        candidate: Dict[str, Any],
        output_dir: str,
    ) -> List[FetchedAsset]:
        url = (candidate.get("url") or "").lower()
        os.makedirs(output_dir, exist_ok=True)

        if "zenodo.org" in url:
            return await self._fetch_zenodo(candidate, output_dir)
        if "figshare.com" in url:
            return await self._fetch_direct_file(candidate, output_dir)
        if "datadryad.org" in url or "dryad.org" in url:
            return await self._fetch_direct_file(candidate, output_dir)
        return []

    async def _fetch_zenodo(
        self,
        candidate: Dict[str, Any],
        output_dir: str,
    ) -> List[FetchedAsset]:
        rec_id = candidate.get("record_id") or _zenodo_id_from_url(candidate.get("url", ""))
        if not rec_id:
            raise ValueError("无法解析 Zenodo record id")

        api_url = f"https://zenodo.org/api/records/{rec_id}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "AISci-DataFinder/2.0"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        files = data.get("files") or []
        title = (data.get("metadata") or {}).get("title") or candidate.get("dataset_name", "Zenodo")
        assets: List[FetchedAsset] = []

        for fmeta in files:
            fname = fmeta.get("key") or ""
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ALLOWED_EXTENSIONS and ext != ".zip":
                continue
            download_url = fmeta.get("links", {}).get("self") or ""
            if not download_url:
                continue
            local = _download_file(download_url, output_dir, fname)
            if ext == ".zip":
                extracted = _extract_zip_tables(local, output_dir, title)
                assets.extend(extracted)
            elif ext in ALLOWED_EXTENSIONS:
                from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill

                skill = TabularFileExtractionSkill()
                res = await skill.run({"file_path": local, "source_title": title}, {})
                for tbl in res.data.get("tables", []):
                    assets.append(FetchedAsset(
                        source_type="open_repository",
                        source_title=title,
                        local_path=tbl["csv_path"],
                        file_kind="csv",
                        url=candidate.get("url", ""),
                        columns=tbl.get("columns", []),
                        row_count=int(tbl.get("row_count") or 0),
                        extraction_method="zenodo_fetch",
                        confidence=0.7,
                    ))
            if assets:
                break
        if not assets:
            raise ValueError("Zenodo 记录中无可用表格文件（csv/tsv/xlsx/zip）")
        return assets

    async def _fetch_direct_file(
        self,
        candidate: Dict[str, Any],
        output_dir: str,
    ) -> List[FetchedAsset]:
        url = candidate.get("url", "")
        if not url:
            raise ValueError("无下载 URL")
        fname = os.path.basename(urllib.parse.urlparse(url).path) or "download.csv"
        local = _download_file(url, output_dir, fname)
        ext = os.path.splitext(local)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {ext}")

        from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill

        skill = TabularFileExtractionSkill()
        res = await skill.run(
            {"file_path": local, "source_title": candidate.get("dataset_name", "Repository")},
            {},
        )
        assets = []
        for tbl in res.data.get("tables", []):
            assets.append(FetchedAsset(
                source_type="open_repository",
                source_title=candidate.get("dataset_name", "Repository"),
                local_path=tbl["csv_path"],
                file_kind="csv",
                url=url,
                columns=tbl.get("columns", []),
                row_count=int(tbl.get("row_count") or 0),
                extraction_method="repository_fetch",
                confidence=0.65,
            ))
        return assets


def _zenodo_id_from_url(url: str) -> str:
    m = re.search(r"zenodo\.org/records?/(\d+)", url or "", re.I)
    return m.group(1) if m else ""


def _search_figshare(query: str, *, limit: int = 5) -> Dict[str, Any]:
    """Figshare public search API（仅 metadata + 下载链接）。"""
    try:
        params = urllib.parse.urlencode({"search_for": query, "page_size": limit})
        url = f"https://api.figshare.com/v2/articles/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/2.0"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for item in (data if isinstance(data, list) else [])[:limit]:
            title = item.get("title") or ""
            art_id = item.get("id") or ""
            results.append({
                "dataset_name": title[:200],
                "url": f"https://figshare.com/articles/article/{art_id}" if art_id else "",
                "description": (item.get("description") or "")[:300],
                "license": item.get("license", {}).get("name", "") if isinstance(item.get("license"), dict) else "",
                "confidence": 0.68,
                "record_id": str(art_id),
            })
        return {"results": results}
    except Exception as exc:
        logger.warning("Figshare 检索失败: %s", exc)
        return {"error": str(exc), "results": []}


def _download_file(url: str, output_dir: str, filename: str) -> str:
    safe = re.sub(r"[^\w.\-]", "_", filename)[:120]
    dest = os.path.join(output_dir, safe)
    req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/2.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"文件超过 {MAX_DOWNLOAD_BYTES // (1024*1024)}MB 限制")
        with open(dest, "wb") as f:
            f.write(data)
    return dest


def _extract_zip_tables(zip_path: str, output_dir: str, title: str) -> List[FetchedAsset]:
    assets: List[FetchedAsset] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            extract_path = os.path.join(output_dir, os.path.basename(name))
            with zf.open(name) as src, open(extract_path, "wb") as dst:
                dst.write(src.read(MAX_DOWNLOAD_BYTES))
            assets.append(FetchedAsset(
                source_type="open_repository",
                source_title=title,
                local_path=extract_path,
                file_kind=ext.lstrip("."),
                url="",
                extraction_method="zenodo_zip",
                confidence=0.68,
            ))
            if len(assets) >= 3:
                break
    return assets
