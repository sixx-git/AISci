"""批量修复最新报告「历史数据」(source) 英文文献串入，并重编译 PDF。"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.latex_export_service import (  # noqa: E402
    compile_latex_to_pdf,
    escape_latex,
)
from app.services.report_content_sanitizer import strip_english_literature_bleed  # noqa: E402

DB = BACKEND / "data" / "aiscientist.db"
REPORTS = BACKEND / "storage" / "reports"
EXPORT_DST = Path(r"D:\浏览器\报告2")

CJK = re.compile(r"[\u4e00-\u9fff]")


def latest_key(row: sqlite3.Row) -> tuple:
    created = str(row["created_at"] or "")
    try:
        version = int(row["version"] or 0)
    except (TypeError, ValueError):
        version = 0
    return (created, version, str(row["id"]))


def has_english_bleed(text: str) -> bool:
    if not text:
        return False
    for line in str(text).splitlines():
        s = line.strip()
        if not s or CJK.search(s):
            continue
        # 跳过纯 latex 命令
        if s.startswith("\\") and " " not in s[:20]:
            continue
        norm = unicodedata.normalize("NFKC", s)
        # 去 latex 转义后再判
        plain = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", norm)
        plain = re.sub(r"\\[&%$#_{}]", "", plain)
        letters = len(re.findall(r"[A-Za-z]", plain))
        if len(plain) >= 35 and letters >= 25 and letters / max(len(plain), 1) >= 0.5:
            if not re.search(
                r"(?i)\b(accuracy|baseline|metrics?|datasets?|figures?)\b|DOI\s*:|https?://",
                plain,
            ):
                return True
        if re.match(r"^(Received|DOI:|Contents lists|journal homepage|Our website uses cookies)", plain, re.I):
            return True
    return False


def build_source_tex_body(source: str) -> str:
    lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
    if not lines:
        return "（暂无历史数据说明）\n"
    if all(ln.startswith("-") for ln in lines):
        items = [f"    \\item {escape_latex(ln.lstrip('-').strip())}" for ln in lines]
        return "\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}\n"
    # 混合：有 - 开头的做列表，其余段落
    items = []
    paras = []
    for ln in lines:
        if ln.startswith("-"):
            items.append(f"    \\item {escape_latex(ln.lstrip('-').strip())}")
        else:
            paras.append(escape_latex(ln))
    parts: List[str] = []
    if items:
        parts.append("\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}")
    if paras:
        parts.append("\n\n".join(paras))
    return "\n".join(parts) + "\n"


def replace_history_subsection(tex: str, source: str) -> Tuple[str, bool]:
    body = build_source_tex_body(source)
    replacement = "\\subsection{历史数据}\n\n" + body + "\n"

    def _sub(_m: re.Match) -> str:
        return replacement

    new_tex, n = re.subn(
        r"\\subsection\{历史数据\}\s*.*?(?=\\subsection\{)",
        _sub,
        tex,
        count=1,
        flags=re.S,
    )
    return new_tex, n > 0


def safe_name(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', "_", (title or "").strip())
    title = re.sub(r"\s+", " ", title).strip(" .")
    return (title or "untitled")[:180]


def fix_one(folder: Path, report_id: str, source: str, paper_title: str, *, compile_pdf: bool) -> Dict[str, Any]:
    info: Dict[str, Any] = {"id": report_id, "changed": False, "compiled": False}
    cleaned = strip_english_literature_bleed(source)
    # 再扫一遍：若仍有 bleed，按行硬删
    if has_english_bleed(cleaned):
        kept = []
        for ln in cleaned.splitlines():
            s = ln.strip()
            if not s:
                continue
            if CJK.search(s) or s.startswith("-") and CJK.search(s):
                kept.append(ln if ln.startswith("-") or CJK.search(ln) else f"- {s}")
            elif CJK.search(s):
                kept.append(s)
        cleaned = "\n".join(kept).strip() or cleaned
        # 最终：只保留含汉字行
        cleaned = "\n".join(
            ln for ln in cleaned.splitlines() if CJK.search(ln)
        ).strip() or "（历史数据来源说明已清洗；请参见数据集章节与参考文献。）"

    jp = folder / "report_data.json"
    data: Dict[str, Any] = {}
    if jp.exists():
        data = json.loads(jp.read_text(encoding="utf-8"))
        ch = dict(data.get("chapters") or {})
        old = str(ch.get("source") or "")
        ch["source"] = cleaned
        data["chapters"] = ch
        jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if old != cleaned:
            info["changed"] = True

    tex_path = folder / "report.tex"
    if tex_path.exists():
        tex = tex_path.read_text(encoding="utf-8", errors="replace")
        new_tex, ok = replace_history_subsection(tex, cleaned)
        if ok and new_tex != tex:
            tex_path.write_text(new_tex, encoding="utf-8")
            info["changed"] = True
            info["tex_ok"] = True
        elif not ok:
            info["tex_ok"] = False

    md_path = folder / "report.md"
    if md_path.exists():
        md = md_path.read_text(encoding="utf-8", errors="replace")
        md2, n = re.subn(
            r"(?ms)(^##+\s*历史数据\s*\n)(.*?)(?=^##+\s|\Z)",
            lambda m: m.group(1) + cleaned + "\n\n",
            md,
        )
        if n and md2 != md:
            md_path.write_text(md2, encoding="utf-8")

    if compile_pdf and tex_path.exists() and info.get("changed"):
        res = compile_latex_to_pdf(folder, "report.tex")
        info["compiled"] = bool(res.get("success"))
        if not info["compiled"]:
            info["warning"] = str(res.get("warning") or "")[:200]
        elif (folder / "report.pdf").is_file():
            EXPORT_DST.mkdir(parents=True, exist_ok=True)
            name = safe_name(paper_title)
            dst = EXPORT_DST / f"{name}.pdf"
            shutil.copy2(folder / "report.pdf", dst)
            for npath in EXPORT_DST.glob(f"*{name}.pdf"):
                if npath.resolve() != dst.resolve():
                    shutil.copy2(folder / "report.pdf", npath)
            info["exported"] = str(dst)

    info["source"] = cleaned
    return info


def main() -> None:
    compile_pdf = "--compile" in sys.argv
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        select r.id, r.project_id, r.pdf_path, r.paper_title, r.source,
               r.created_at, r.version, p.name as project_name
        from reports r join projects p on p.id = r.project_id
        """
    ).fetchall()

    latest: Dict[str, sqlite3.Row] = {}
    for r in rows:
        prev = latest.get(r["project_id"])
        if prev is None or latest_key(r) > latest_key(prev):
            latest[r["project_id"]] = r

    stats = {"checked": 0, "dirty": 0, "fixed": 0, "compiled": 0, "failed": 0}
    for r in sorted(latest.values(), key=lambda x: x["project_name"] or ""):
        stats["checked"] += 1
        folder = REPORTS / (r["pdf_path"] or r["id"])
        source = r["source"] or ""
        # 也查 json / tex
        dirty = has_english_bleed(source)
        if folder.joinpath("report_data.json").exists():
            data = json.loads(folder.joinpath("report_data.json").read_text(encoding="utf-8"))
            dirty = dirty or has_english_bleed(str((data.get("chapters") or {}).get("source") or ""))
        if folder.joinpath("report.tex").exists():
            tex = folder.joinpath("report.tex").read_text(encoding="utf-8", errors="replace")
            m = re.search(r"\\subsection\{历史数据\}(.*?)\\subsection\{", tex, flags=re.S)
            if m:
                dirty = dirty or has_english_bleed(m.group(1))
        if not dirty:
            continue
        stats["dirty"] += 1
        print(f"[fix] {r['project_name']}")
        info = fix_one(
            folder,
            r["id"],
            source if source else str((json.loads(folder.joinpath("report_data.json").read_text(encoding="utf-8")).get("chapters") or {}).get("source") or "") if folder.joinpath("report_data.json").exists() else "",
            r["paper_title"] or r["project_name"] or "",
            compile_pdf=compile_pdf,
        )
        conn.execute(
            "update reports set source=?, updated_at=datetime('now') where id=?",
            (info["source"], r["id"]),
        )
        if info.get("changed") or info.get("source") != source:
            stats["fixed"] += 1
        if info.get("compiled"):
            stats["compiled"] += 1
        if info.get("warning"):
            stats["failed"] += 1
            print("  warn", info["warning"])
        print("  source=", info["source"][:100].replace("\n", " | "))

    conn.commit()
    conn.close()
    print("DONE", stats)


if __name__ == "__main__":
    main()
