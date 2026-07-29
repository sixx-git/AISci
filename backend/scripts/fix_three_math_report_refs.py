"""修复纳维-斯托克斯 / 黎曼猜想 / 素数三份报告的错误参考文献并重编译。

主要问题：
1. 有 DOI 的期刊论文被标成 [EB/OL]（旧数据未按新规则重建）
2. journal 字段缺失，GB/T 条目不完整
3. 素数报告作者张冠李戴（Andrew Granville, Yiliang Zhang）
4. 题名含 HTML / 科学计数法转义难看
5. citation_map 混入「期刊卷期页码」伪条目
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.latex_export_service import (  # noqa: E402
    clean_reference_text,
    compile_latex_to_pdf,
    format_reference_items_as_gbt7714_lines,
    _build_references_bib,
    _build_thebibliography_section,
    _collect_bibliography_items,
)
from scripts.fix_stored_report_references import (  # noqa: E402
    _replace_markdown_refs,
    _replace_thebibliography,
    sync_db,
)

DB = BACKEND / "data" / "aiscientist.db"
REPORTS = BACKEND / "storage" / "reports"
EXPORT_DST = Path(r"D:\浏览器\报告2")

PROJECT_NAMES = [
    "纳维-斯托克斯问题终将被解决吗",
    "黎曼猜想是否成立",
    "素数为何如此特殊",
]

# DOI → 期刊名（已知权威文献，避免依赖外网）
DOI_JOURNAL: Dict[str, str] = {
    "10.1002/cpa.3160350604": "Communications on Pure and Applied Mathematics",
    "10.1070/rm2003v058n02abeh000609": "Russian Mathematical Surveys",
    "10.1090/jams/860": "Journal of the American Mathematical Society",
    "10.4007/annals.2019.189.1.3": "Annals of Mathematics",
    "10.1112/blms.12438": "Bulletin of the London Mathematical Society",
    "10.1006/jnth.1997.2137": "Journal of Number Theory",
    "10.1007/s002200000261": "Communications in Mathematical Physics",
    "10.4007/annals.2015.181.1.9": "Annals of Mathematics",
    "10.4007/annals.2008.167.481": "Annals of Mathematics",
    "10.4007/annals.2014.179.3.7": "Annals of Mathematics",
    "10.1080/00029890.2008.11920530": "The American Mathematical Monthly",
}

# 题名关键词 → 修正字段（作者张冠李戴、缺 DOI 等）
TITLE_FIXES: List[Dict[str, Any]] = [
    {
        "match": re.compile(r"positivity of a sequence of numbers", re.I),
        "authors": "Xian-Jin Li",
        "title": "The Positivity of a Sequence of Numbers and the Riemann Hypothesis",
        "year": 1997,
        "doi": "10.1006/jnth.1997.2137",
        "journal": "Journal of Number Theory",
        "source_url": "https://doi.org/10.1006/jnth.1997.2137",
    },
    {
        "match": re.compile(r"bounded\s+gaps\s+between\s+primes", re.I),
        "authors": "Yitang Zhang",
        "title": "Bounded gaps between primes",
        "year": 2014,
        "doi": "10.4007/annals.2014.179.3.7",
        "journal": "Annals of Mathematics",
        "source_url": "https://doi.org/10.4007/annals.2014.179.3.7",
    },
    {
        "match": re.compile(r"existence and smoothness of the navier.?stokes", re.I),
        "authors": "Charles L. Fefferman",
        "journal": "Clay Mathematics Institute Millennium Prize Problems",
        "year": 2006,
    },
    {
        "match": re.compile(r"grandes valeurs de la fonction somme", re.I),
        "authors": "Guy Robin",
        "journal": "Journal de Théorie des Nombres de Bordeaux",
        "year": 1984,
    },
    {
        "match": re.compile(r"pair correlation of zeros of the zeta", re.I),
        "authors": "Hugh L. Montgomery",
        "journal": "Analytic Number Theory (Proc. Sympos. Pure Math.)",
        "year": 1973,
    },
    {
        "match": re.compile(r"^the riemann hypothesis$", re.I),
        "authors": "J. Brian Conrey",
        "journal": "Notices of the American Mathematical Society",
        "year": 2003,
    },
    {
        "match": re.compile(r"structure and randomness in the prime", re.I),
        "authors": "Terence Tao",
        "journal": "Surveys in Number Theory",
        "year": 2007,
    },
    {
        "match": re.compile(r"non-uniqueness of the navier.?stokes equations with a given", re.I),
        "authors": "Dallas Albritton, Elia Brué, Maria Colombo",
        "year": 2022,
        "journal": "arXiv preprint",
        "source_url": "https://arxiv.org/abs/2112.03116",
        "doi": "",
    },
    {
        "match": re.compile(r"potentially singular behavior of the 3d navier", re.I),
        "authors": "Thomas Y. Hou",
        "year": 2023,
        "journal": "arXiv preprint",
        "source_url": "https://arxiv.org/abs/2107.05855",
    },
]


def _norm_doi(doi: Any) -> str:
    s = str(doi or "").strip().lower()
    s = s.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return s.strip("/")


def _clean_item(item: Dict[str, Any]) -> Dict[str, Any] | None:
    out = dict(item)
    title = clean_reference_text(out.get("title") or out.get("paper_title") or "")
    if not title:
        return None
    # 伪题名：期刊卷期页码
    if re.match(r"^[A-Za-z][A-Za-z\s.&'\-]+,\s*\d+\s*\(\d{4}\)\s*,\s*\d+", title):
        return None
    out["title"] = title
    out["paper_title"] = title
    if isinstance(out.get("authors"), str):
        out["authors"] = clean_reference_text(out["authors"])
    elif isinstance(out.get("authors"), list):
        out["authors"] = [clean_reference_text(a) for a in out["authors"] if clean_reference_text(a)]

    doi = _norm_doi(out.get("doi"))
    if doi:
        out["doi"] = doi
        if not out.get("journal") and doi in DOI_JOURNAL:
            out["journal"] = DOI_JOURNAL[doi]
        url = str(out.get("source_url") or "")
        if not url or "doi.org" in url.lower():
            out["source_url"] = f"https://doi.org/{doi}"

    for fix in TITLE_FIXES:
        if fix["match"].search(title):
            for k, v in fix.items():
                if k == "match":
                    continue
                if v == "" and k in out:
                    out.pop(k, None)
                elif v not in (None, ""):
                    out[k] = v
            break

    if out.get("journal"):
        out["journal"] = clean_reference_text(out["journal"])
    return out


def _clean_list(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = _clean_item(raw)
        if not item:
            continue
        key = _norm_doi(item.get("doi")) or f"t:{(item.get('title') or '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def latest_report_folder(project_id: str) -> tuple[str, Path]:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT id, pdf_path, paper_title, created_at
        FROM reports WHERE project_id=?
        ORDER BY created_at DESC, version DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise SystemExit(f"no report for project {project_id}")
    folder_id = row["pdf_path"] or row["id"]
    return folder_id, REPORTS / str(folder_id)


def fix_folder(folder: Path, folder_id: str, paper_title: str) -> Dict[str, Any]:
    data_path = folder / "report_data.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    verified = _clean_list(data.get("verified_references"))
    citation = _clean_list(data.get("citation_map"))
    # 以清洗后的 verified 为主；若空则用 citation
    primary = verified or citation
    data["verified_references"] = primary
    data["citation_map"] = citation or primary

    lines = format_reference_items_as_gbt7714_lines(citation or primary, primary)
    items = _collect_bibliography_items(
        {"references": []},
        citation_map=citation or primary,
        verified_references=primary,
    )
    chapters = dict(data.get("chapters") or {})
    chapters["references"] = lines
    data["chapters"] = chapters
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    tex_path = folder / "report.tex"
    if tex_path.exists():
        tex = tex_path.read_text(encoding="utf-8", errors="replace")
        new_tex, _ = _replace_thebibliography(tex, items if items else [{"note": x} for x in lines])
        tex_path.write_text(new_tex, encoding="utf-8")

    md_path = folder / "report.md"
    if md_path.exists():
        md = md_path.read_text(encoding="utf-8", errors="replace")
        md_path.write_text(_replace_markdown_refs(md, lines), encoding="utf-8")

    bib_path = folder / "references.bib"
    bib_content, _ = _build_references_bib(
        chapters,
        citation_map=data["citation_map"],
        verified_references=data["verified_references"],
    )
    if bib_content:
        bib_path.write_text(bib_content + "\n", encoding="utf-8")

    sync_db(folder_id, lines)
    compile_result = compile_latex_to_pdf(folder, "report.tex") if tex_path.exists() else {}
    return {
        "folder": folder_id,
        "title": paper_title,
        "n_refs": len(lines),
        "refs": lines,
        "compiled": bool(compile_result.get("success")),
        "compile_warning": compile_result.get("warning"),
        "bib_preview": _build_thebibliography_section(items)[:500],
    }


def export_pdf(folder: Path, paper_title: str) -> Path | None:
    pdf = folder / "report.pdf"
    if not pdf.is_file() or pdf.stat().st_size <= 0:
        return None
    EXPORT_DST.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*]', "_", (paper_title or "untitled").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")[:180] or "untitled"
    dst = EXPORT_DST / f"{name}.pdf"
    shutil.copy2(pdf, dst)
    return dst


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    projects = []
    for name in PROJECT_NAMES:
        row = conn.execute(
            "SELECT id, name FROM projects WHERE name LIKE ? LIMIT 1",
            (f"%{name}%",),
        ).fetchone()
        if not row:
            print(f"[miss] project {name}")
            continue
        projects.append(row)
    conn.close()

    for proj in projects:
        folder_id, folder = latest_report_folder(proj["id"])
        print("=" * 60)
        print(proj["name"], folder_id)
        # paper title from db
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT paper_title FROM reports WHERE pdf_path=? OR id=? ORDER BY created_at DESC LIMIT 1",
            (folder_id, folder_id),
        ).fetchone()
        conn.close()
        title = (r["paper_title"] if r else "") or proj["name"]
        info = fix_folder(folder, folder_id, title)
        print("n_refs", info["n_refs"], "compiled", info["compiled"])
        for i, line in enumerate(info["refs"], 1):
            print(f"  [{i}] {line}")
        if info.get("compile_warning"):
            print("compile_warning", info["compile_warning"][:300])
        dst = export_pdf(folder, title)
        print("exported", dst)


if __name__ == "__main__":
    main()
