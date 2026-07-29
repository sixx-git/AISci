"""
批量修复 backend/storage/reports 下已生成报告的参考文献：
1. 用 citation_map / verified_references（或清洗后的章节行）重建 GB/T 书目
2. 更新 report_data.json / report.tex / report.md / references.bib
3. 可选重编译 PDF（--compile）
4. 可选同步数据库 reports.references（--sync-db）
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.latex_export_service import (  # noqa: E402
    _build_references_bib,
    _build_thebibliography_section,
    _collect_bibliography_items,
    clean_reference_text,
    compile_latex_to_pdf,
    format_reference_items_as_gbt7714_lines,
    parse_reference_line_to_item,
)

REPORTS_DIR = BACKEND_ROOT / "storage" / "reports"
DB_PATH = BACKEND_ROOT / "data" / "aiscientist.db"

_THEBIB_RE = re.compile(
    r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
    flags=re.S,
)
_MD_REFS_RE = re.compile(
    r"(^##+\s*参考文献\s*\n)(.*?)(?=^##+\s|\Z)",
    flags=re.S | re.M,
)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _clean_existing_lines(refs: Any) -> List[str]:
    if not isinstance(refs, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in refs:
        if not isinstance(raw, str) or not raw.strip():
            continue
        line = clean_reference_text(raw)
        # 统一 {[J]} -> [J]，并去掉重复类型标
        line = re.sub(r"\{\[([A-Z](?:/[A-Z]+)?)\]\}", r"[\1]", line)
        line = re.sub(r"(?:\[([A-Z](?:/[A-Z]+)?)\]\s*){2,}", r"[\1]", line)
        line = re.sub(r"\.\.(?=\S)", ". ", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _rebuild_reference_lines(data: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    citation_map = data.get("citation_map") if isinstance(data.get("citation_map"), list) else []
    verified = data.get("verified_references") if isinstance(data.get("verified_references"), list) else []
    lines = format_reference_items_as_gbt7714_lines(citation_map, verified)
    items = _collect_bibliography_items(
        {"references": []},
        citation_map=citation_map,
        verified_references=verified,
    )
    if lines and items:
        return lines, items

    chapters = data.get("chapters") if isinstance(data.get("chapters"), dict) else {}
    existing = _clean_existing_lines(chapters.get("references") or data.get("references"))
    # 尝试 parse 后重排为 GB/T
    parsed_items: List[Dict[str, Any]] = []
    rebuilt: List[str] = []
    for line in existing:
        item = parse_reference_line_to_item(line)
        if item.get("title"):
            from app.services.latex_export_service import _format_reference_gbt7714

            rebuilt.append(_format_reference_gbt7714(item))
            parsed_items.append(item)
        else:
            rebuilt.append(line)
            parsed_items.append({"note": line})
    return rebuilt, parsed_items


def _replace_thebibliography(tex: str, items: List[Dict[str, Any]]) -> Tuple[str, bool]:
    block = _build_thebibliography_section(items).rstrip() + "\n"

    def _sub_thebib(match: re.Match) -> str:
        return block.rstrip()

    if _THEBIB_RE.search(tex):
        return _THEBIB_RE.sub(_sub_thebib, tex), True
    # 无 thebibliography：若有 \bibliography{...} 则替换该命令
    if re.search(r"\\bibliography\{[^}]+\}", tex):
        tex2 = re.sub(r"\\bibliography\{[^}]+\}", lambda _m: block.rstrip(), tex)
        return tex2, True
    # 插在 \end{document} 前
    if r"\end{document}" in tex:
        return tex.replace(r"\end{document}", block + "\n\\end{document}", 1), True
    return tex + "\n" + block, True


def _replace_markdown_refs(md: str, lines: List[str]) -> str:
    body = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1)) + "\n"
    if _MD_REFS_RE.search(md):
        return _MD_REFS_RE.sub(rf"\g<1>{body}", md)
    return md


_GARBAGE_TITLE_RE = re.compile(
    r"^[A-Za-z][A-Za-z\s.&'\-]+,\s*\d+\s*\(\d{4}\)\s*,\s*\d+"
)
_EB_DOI_RE = re.compile(
    r"\[EB/OL\].{0,120}(?:DOI\s*:|doi\.org|\b10\.\d{4,}/)",
    flags=re.I | re.S,
)


def _needs_fix(tex: str, lines: List[str]) -> bool:
    blob = "\n".join(lines) + "\n" + tex
    markers = ("{[J]}", "{[M]}", "{[J/OL]}", "{[EB/OL]}", r"\{[J]\}", r"\{[M]\}", "<i>", "</i>", "<sub>", "<em>")
    if any(m in blob for m in markers):
        return True
    if re.search(r"\\\{\[[A-Z]", tex):
        return True
    if ".." in blob:
        return True
    if _EB_DOI_RE.search(blob):
        return True
    if r"\textasciicircum{}" in tex:
        return True
    return False


def _sanitize_structured_list(items: Any) -> List[Dict[str, Any]]:
    """清洗 citation_map / verified_references：去 HTML、拒伪题名、去重。"""
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        title = clean_reference_text(item.get("title") or item.get("paper_title") or "")
        if not title or _GARBAGE_TITLE_RE.match(title):
            continue
        item["title"] = title
        item["paper_title"] = title
        if isinstance(item.get("authors"), str):
            item["authors"] = clean_reference_text(item["authors"])
        elif isinstance(item.get("authors"), list):
            item["authors"] = [
                clean_reference_text(a) for a in item["authors"] if clean_reference_text(a)
            ]
        if item.get("journal"):
            item["journal"] = clean_reference_text(item["journal"])
        doi = str(item.get("doi") or "").strip().lower()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip("/")
        if doi:
            item["doi"] = doi
        key = f"doi:{doi}" if doi else f"title:{title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _latest_report_folders() -> List[Path]:
    """每个项目最新报告对应的 storage/reports 目录。"""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.id, r.project_id, r.pdf_path, r.version, r.created_at, r.updated_at
        FROM reports r
        """
    ).fetchall()
    conn.close()

    def _key(row: sqlite3.Row) -> tuple:
        created = str(row["created_at"] or "")
        updated = str(row["updated_at"] or "") or created
        try:
            version = int(row["version"] or 0)
        except (TypeError, ValueError):
            version = 0
        return (created, version, updated, str(row["id"]))

    latest: Dict[str, sqlite3.Row] = {}
    for row in rows:
        pid = row["project_id"]
        prev = latest.get(pid)
        if prev is None or _key(row) > _key(prev):
            latest[pid] = row

    folders: List[Path] = []
    for row in latest.values():
        folder_id = row["pdf_path"] or row["id"]
        folder = REPORTS_DIR / str(folder_id)
        if folder.is_dir():
            folders.append(folder)
    return sorted(folders, key=lambda p: p.name)


def fix_one(folder: Path, *, compile_pdf: bool, force: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"id": folder.name, "changed": False, "compiled": False, "error": None}
    data_path = folder / "report_data.json"
    data = _load_json(data_path)
    if not data:
        result["error"] = "no_report_data"
        return result

    # 先清洗结构化文献，再重建 GB/T
    verified = _sanitize_structured_list(data.get("verified_references"))
    citation = _sanitize_structured_list(data.get("citation_map"))
    if verified or citation:
        data["verified_references"] = verified or citation
        data["citation_map"] = citation or verified

    lines, items = _rebuild_reference_lines(data)
    if not lines:
        result["error"] = "empty_refs"
        return result

    tex_path = folder / "report.tex"
    tex = tex_path.read_text(encoding="utf-8", errors="replace") if tex_path.exists() else ""
    old_lines = list((data.get("chapters") or {}).get("references") or [])
    old_blob = "\n".join(str(x) for x in old_lines)
    new_blob = "\n".join(lines)
    tex_dirty = bool(
        re.search(r"\\\{\[[A-Z]", tex)
        or "<i>" in tex
        or "{[J]}" in tex
        or _EB_DOI_RE.search(tex)
        or r"\textasciicircum{}" in tex
    )
    if not force and old_blob == new_blob and not tex_dirty and _THEBIB_RE.search(tex):
        preview = _build_thebibliography_section(items if items else [{"note": x} for x in lines])
        if preview.strip() in tex.replace("\r\n", "\n"):
            result["error"] = "already_clean"
            return result

    chapters = dict(data.get("chapters") or {})
    chapters["references"] = lines
    data["chapters"] = chapters
    if "verified_references" not in data:
        data["verified_references"] = []
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if tex_path.exists():
        new_tex, _ = _replace_thebibliography(tex, items if items else [{"note": x} for x in lines])
        tex_path.write_text(new_tex, encoding="utf-8")

    md_path = folder / "report.md"
    if md_path.exists():
        md = md_path.read_text(encoding="utf-8", errors="replace")
        md_path.write_text(_replace_markdown_refs(md, lines), encoding="utf-8")

    bib_path = folder / "references.bib"
    bib_content, _ = _build_references_bib(
        chapters,
        citation_map=data.get("citation_map") if isinstance(data.get("citation_map"), list) else [],
        verified_references=data.get("verified_references")
        if isinstance(data.get("verified_references"), list)
        else [],
    )
    if bib_content:
        bib_path.write_text(bib_content + "\n", encoding="utf-8")
    elif items:
        bib_content, _ = _build_references_bib({"references": lines})
        if bib_content:
            bib_path.write_text(bib_content + "\n", encoding="utf-8")

    result["changed"] = True
    result["n_refs"] = len(lines)

    if compile_pdf and tex_path.exists():
        compile_result = compile_latex_to_pdf(folder, "report.tex")
        result["compiled"] = bool(compile_result.get("success"))
        if not result["compiled"]:
            result["compile_warning"] = compile_result.get("warning")

    return result


def sync_db(file_id: str, lines: List[str]) -> bool:
    if not DB_PATH.exists():
        return False
    refs_json = json.dumps(lines, ensure_ascii=False)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            'UPDATE reports SET "references" = ? WHERE pdf_path = ?',
            (refs_json, file_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true", help="重编译 PDF")
    parser.add_argument("--sync-db", action="store_true", help="同步数据库 references 字段")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 个（调试）")
    parser.add_argument("--only-dirty", action="store_true", help="仅处理含脏标记的报告")
    parser.add_argument("--latest-only", action="store_true", help="仅处理每个项目最新报告")
    parser.add_argument("--force", action="store_true", help="强制重建书目（即使看似已干净）")
    args = parser.parse_args()

    if args.latest_only:
        folders = _latest_report_folders()
    else:
        folders = sorted([d for d in REPORTS_DIR.iterdir() if d.is_dir()], key=lambda p: p.name)
    if args.limit:
        folders = folders[: args.limit]

    stats = {"total": 0, "changed": 0, "skipped": 0, "errors": 0, "compiled": 0, "db_synced": 0}
    for folder in folders:
        stats["total"] += 1
        data = _load_json(folder / "report_data.json")
        if not data:
            stats["errors"] += 1
            print(f"[skip] {folder.name}: no json")
            continue
        if args.only_dirty and not args.force:
            old_refs = list((data.get("chapters") or {}).get("references") or [])
            tex = ""
            tex_path = folder / "report.tex"
            if tex_path.exists():
                tex = tex_path.read_text(encoding="utf-8", errors="replace")
            # 结构化脏（HTML / DOI+无刊名导致的 EB/OL）也算需要修
            structured_blob = json.dumps(
                {
                    "v": data.get("verified_references") or [],
                    "c": data.get("citation_map") or [],
                },
                ensure_ascii=False,
            )
            if not _needs_fix(
                tex + "\n" + structured_blob,
                [str(x) for x in old_refs if isinstance(x, str)],
            ):
                # 章节行含 [EB/OL]+DOI 已在 _needs_fix；再查 structured HTML
                if "<i>" not in structured_blob and "<sub>" not in structured_blob and "[EB/OL]" not in (
                    "\n".join(str(x) for x in old_refs)
                ):
                    stats["skipped"] += 1
                    continue

        info = fix_one(folder, compile_pdf=args.compile, force=args.force)
        if info.get("changed"):
            stats["changed"] += 1
            print(f"[ok] {folder.name} refs={info.get('n_refs')} compiled={info.get('compiled')}")
            if args.sync_db:
                lines = ((_load_json(folder / "report_data.json") or {}).get("chapters") or {}).get(
                    "references"
                ) or []
                if isinstance(lines, list) and sync_db(folder.name, lines):
                    stats["db_synced"] += 1
            if info.get("compiled"):
                stats["compiled"] += 1
            if info.get("compile_warning"):
                print(f"  warn: {str(info.get('compile_warning'))[:200]}")
        else:
            stats["skipped"] += 1
            if info.get("error") not in (None, "already_clean"):
                stats["errors"] += 1
                print(f"[warn] {folder.name}: {info.get('error')}")

    print("DONE", stats)


if __name__ == "__main__":
    main()
