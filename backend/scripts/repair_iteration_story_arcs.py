"""回修 storage/reports 中被硬截断 / significant_issue 拆字的迭代演化叙事。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.skills.report.iteration_narrative_skill import IterationNarrativeSkill  # noqa: E402
from app.services.latex_export_service import (  # noqa: E402
    _build_thebibliography_section,
    _collect_bibliography_items,
    build_latex_document,
    compile_latex_to_pdf,
)
from app.services.report_content_sanitizer import sanitize_report_result  # noqa: E402

REPORTS_DIR = BACKEND_ROOT / "storage" / "reports"

_STORY_MARKERS = (
    "评估为「significant_issue」",
    "signif icantissue",
    "significant\\_issue",
    "随后调整依据：['",
    "随后调整依据：[\"",
    "替代简」",
    "需根。",
    "significant_issue",
)


def _extract_hypothesis(data: Dict[str, Any]) -> str:
    for key in ("hypothesis", "research_question"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    run = data.get("run_summary") if isinstance(data.get("run_summary"), dict) else {}
    for key in ("hypothesis", "research_question"):
        v = run.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # 从旧 story 里抠
    story = ""
    narr = (data.get("skill_outputs") or {}).get("iteration_narrative") or {}
    if isinstance(narr, dict):
        story = str(narr.get("story_arc") or "")
    if not story:
        results = (data.get("chapters") or {}).get("results") or ""
        story = str(results)
    m = re.search(r"围绕假设「(.+?)」，开展了可执行的最小代理", story, flags=re.S)
    return (m.group(1).strip() if m else "")[:800]


def _build_sv(data: Dict[str, Any]) -> Dict[str, Any]:
    results_root = data.get("results") if isinstance(data.get("results"), dict) else {}
    actual = results_root.get("actual_results") if isinstance(results_root.get("actual_results"), dict) else {}
    if not actual:
        # chapters 内嵌很少有完整轮次，尽量从 experiment_artifacts 找
        arts = data.get("experiment_artifacts") if isinstance(data.get("experiment_artifacts"), dict) else {}
        actual = arts.get("actual_results") if isinstance(arts.get("actual_results"), dict) else {}
    return {
        "hypothesis": _extract_hypothesis(data),
        "results": {
            "actual_results": actual,
            "result_type_summary": results_root.get("result_type_summary") or "",
        },
        "sandbox_execution": data.get("sandbox_execution")
        if isinstance(data.get("sandbox_execution"), dict)
        else {},
        "narrative_brief": {},
    }


def _needs_repair(text: str) -> bool:
    if not text:
        return False
    return any(m in text for m in _STORY_MARKERS)


def _replace_story_in_results(results_text: str, new_story: str) -> str:
    text = results_text
    # 替换 **迭代演化叙事。** 后到下一个 **小节** 之间的正文
    pat = re.compile(
        r"(\*\*迭代演化叙事。\*\*\s*)(.*?)(?=\n\*\*[^*]+。\*\*|\n### |\Z)",
        flags=re.S,
    )
    if pat.search(text):
        return pat.sub(rf"\1{new_story.strip()}\n\n", text, count=1)
    # markdown ### 结果分析与讨论 下首段
    if "迭代演化叙事" in text:
        return re.sub(
            r"(迭代演化叙事。\*\*\s*)(.*?)(?=\n\*\*[^*]+。\*\*|\Z)",
            rf"\1{new_story.strip()}\n\n",
            text,
            count=1,
            flags=re.S,
        )
    return text


def repair_one(folder: Path, *, compile_pdf: bool = False) -> Dict[str, Any]:
    jp = folder / "report_data.json"
    if not jp.exists():
        return {"id": folder.name, "changed": False, "error": "no_json"}
    data = json.loads(jp.read_text(encoding="utf-8"))
    chapters = data.get("chapters") if isinstance(data.get("chapters"), dict) else {}
    results = str(chapters.get("results") or "")
    old_story = str(((data.get("skill_outputs") or {}).get("iteration_narrative") or {}).get("story_arc") or "")
    if not (_needs_repair(results) or _needs_repair(old_story)):
        return {"id": folder.name, "changed": False, "error": "clean"}

    sv = _build_sv(data)
    actual = (sv.get("results") or {}).get("actual_results") or {}
    has_rounds = bool(actual.get("successful_iterations") or actual.get("failed_iterations") or actual.get("successful_rounds"))
    if not has_rounds and not old_story:
        return {"id": folder.name, "changed": False, "error": "no_rounds"}

    narr = IterationNarrativeSkill.build_narrative(
        small_validation=sv,
        hypothesis=sv.get("hypothesis") or "",
    )
    new_story = str(narr.get("story_arc") or "").strip()
    if not new_story:
        return {"id": folder.name, "changed": False, "error": "empty_story"}

    # skill_outputs
    skills = dict(data.get("skill_outputs") or {})
    old_narr = dict(skills.get("iteration_narrative") or {})
    old_narr.update(narr)
    skills["iteration_narrative"] = old_narr
    data["skill_outputs"] = skills

    if results:
        chapters["results"] = _replace_story_in_results(results, new_story)
        data["chapters"] = chapters

    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    tex_path = folder / "report.tex"
    if tex_path.exists() and results:
        try:
            result_for_tex = sanitize_report_result(
                {
                    "title": data.get("title") or data.get("paper_title") or "报告",
                    "paper_title": data.get("paper_title") or data.get("title") or "报告",
                    "paper_abstract": data.get("paper_abstract") or "",
                    "chapters": data.get("chapters") or {},
                }
            )
            # 仅重写 results 相关太难对齐模板；整篇重建可能改动过大。
            # 改为对 tex 中「迭代演化叙事」粗体后段落做替换。
            tex = tex_path.read_text(encoding="utf-8", errors="replace")
            from app.services.latex_export_service import escape_latex

            story_tex = escape_latex(new_story)
            tex_pat = re.compile(
                r"(\\textbf\{迭代演化叙事。\}\s*)(.*?)(?=\\textbf\{[^}]+。\}|\\subsection\{|\\section\{|\\begin\{thebibliography\}|\\end\{document\})",
                flags=re.S,
            )

            def _sub_story(match: re.Match) -> str:
                return f"{match.group(1)}\n\n{story_tex}\n\n"

            if tex_pat.search(tex):
                tex = tex_pat.sub(_sub_story, tex, count=1)
                tex_path.write_text(tex, encoding="utf-8")
        except Exception as exc:
            return {"id": folder.name, "changed": True, "error": f"tex:{exc}", "story_len": len(new_story)}

    compiled = False
    if compile_pdf and tex_path.exists():
        compiled = bool(compile_latex_to_pdf(folder, "report.tex").get("success"))

    return {
        "id": folder.name,
        "changed": True,
        "story_len": len(new_story),
        "compiled": compiled,
        "has_sig_issue": "significant_issue" in new_story,
        "has_list_lit": "['" in new_story,
    }


def main() -> None:
    compile_pdf = "--compile" in sys.argv
    folders = sorted([d for d in REPORTS_DIR.iterdir() if d.is_dir()], key=lambda p: p.name)
    stats = {"scanned": 0, "changed": 0, "clean": 0, "errors": 0}
    for folder in folders:
        stats["scanned"] += 1
        info = repair_one(folder, compile_pdf=compile_pdf)
        if info.get("changed"):
            stats["changed"] += 1
            print(
                f"[ok] {folder.name} len={info.get('story_len')} "
                f"sig={info.get('has_sig_issue')} list={info.get('has_list_lit')} "
                f"pdf={info.get('compiled')} err={info.get('error')}"
            )
        elif info.get("error") == "clean":
            stats["clean"] += 1
        else:
            stats["errors"] += 1
            if info.get("error") not in {None, "clean"}:
                print(f"[skip] {folder.name}: {info.get('error')}")
    print("DONE", stats)


if __name__ == "__main__":
    main()
