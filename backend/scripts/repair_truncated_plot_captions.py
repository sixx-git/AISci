"""回修报告 plots：恢复被 academic_chart_title[:120] 硬截断的图表说明。

从 storage/iterative_experiments 的 visualization_notes 取全文，
写入 caption/description，并重算短 title；同步 report_data.json 与 DB。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.report_content_sanitizer import (  # noqa: E402
    academic_chart_caption,
    academic_chart_title,
)

REPORTS = BACKEND / "storage" / "reports"
EXPERIMENTS = BACKEND / "storage" / "iterative_experiments"


def _walk_viz_notes(obj: Any, out: List[Dict[str, str]]) -> None:
    if isinstance(obj, dict):
        notes = obj.get("visualization_notes")
        if isinstance(notes, list):
            for n in notes:
                if not isinstance(n, dict):
                    continue
                name = str(n.get("chart_name") or "").strip()
                desc = str(n.get("description") or "").strip()
                if desc:
                    out.append({"chart_name": name, "description": desc})
        for v in obj.values():
            _walk_viz_notes(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_viz_notes(v, out)


def load_note_corpus() -> Tuple[Dict[str, str], List[str]]:
    """stem -> full description；以及全部 description 列表。"""
    by_stem: Dict[str, str] = {}
    all_desc: List[str] = []
    if not EXPERIMENTS.exists():
        return by_stem, all_desc
    for p in EXPERIMENTS.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        notes: List[Dict[str, str]] = []
        _walk_viz_notes(data, notes)
        for n in notes:
            desc = n["description"]
            all_desc.append(desc)
            stem = Path(n["chart_name"]).stem.lower() if n["chart_name"] else ""
            if stem and (stem not in by_stem or len(desc) > len(by_stem[stem])):
                by_stem[stem] = desc
    # 去重保留最长
    uniq: Dict[str, str] = {}
    for d in all_desc:
        key = d[:40]
        if key not in uniq or len(d) > len(uniq[key]):
            uniq[key] = d
    return by_stem, list(uniq.values())


def looks_hard_truncated(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    if len(t) == 120 and t[-1] not in "。！？.!?;；…」』）)]":
        return True
    if len(t) >= 100 and t.endswith(("各参", "以及", "从而", "因此", "其中", "由于", "并且", "Pearson/Spe")):
        return True
    return False


def resolve_full_note(
    plot: Dict[str, Any],
    by_stem: Dict[str, str],
    all_desc: List[str],
) -> Optional[str]:
    pid = str(plot.get("plot_id") or "").strip().lower()
    title = str(plot.get("title") or "").strip()
    existing = str(plot.get("caption") or plot.get("description") or "").strip()

    if pid and pid in by_stem:
        return by_stem[pid]

    # 前缀匹配：截断 title 是全文前缀
    if title:
        candidates = [d for d in all_desc if d.startswith(title) and len(d) > len(title)]
        if candidates:
            return max(candidates, key=len)
        # 去掉诊断前缀后再匹配
        clean = title
        for pref in ("【反例/失败轮诊断】",):
            if clean.startswith(pref):
                clean = clean[len(pref) :]
        candidates = [d for d in all_desc if d.startswith(clean) and len(d) >= len(clean)]
        if candidates:
            return max(candidates, key=len)

    if existing and (not title or existing.startswith(title) or len(existing) > len(title)):
        return existing
    return None


def repair_plot(plot: Dict[str, Any], by_stem: Dict[str, str], all_desc: List[str]) -> bool:
    if not isinstance(plot, dict):
        return False
    title = str(plot.get("title") or "").strip()
    cap = str(plot.get("caption") or plot.get("description") or "").strip()
    full = resolve_full_note(plot, by_stem, all_desc)

    changed = False
    # 有全文：重写 caption + 短 title
    if full:
        new_cap = academic_chart_caption(full)
        name = str(plot.get("plot_id") or plot.get("path") or "result")
        new_title = academic_chart_title(
            name=name,
            note=full,
            iteration_number=int(plot.get("iteration_number") or 0),
            iteration_status=str(plot.get("iteration_status") or ""),
        )
        if plot.get("is_diagnostic_candidate") or str(title).startswith("【反例"):
            if not new_title.startswith("【反例"):
                new_title = f"【反例/失败轮诊断】{new_title}"
        if plot.get("caption") != new_cap or plot.get("description") != new_cap:
            plot["caption"] = new_cap
            plot["description"] = new_cap
            changed = True
        # 若旧 title 是截断全文，或等于/接近全文，换短标题
        if looks_hard_truncated(title) or (len(title) > 64 and title[:64] == full[:64]):
            if plot.get("title") != new_title:
                plot["title"] = new_title
                changed = True
        elif not cap and len(title) > 80 and title == full[: len(title)]:
            # title 存了完整/接近完整说明但无 caption
            plot["title"] = new_title
            changed = True
        return changed

    # 无全文可恢复：至少把硬截断 title 按句界收尾，并复制到 caption
    if looks_hard_truncated(title):
        from app.services.report_content_sanitizer import _clip_at_sentence

        fixed = _clip_at_sentence(title, 119)
        if not cap:
            plot["caption"] = title  # 保留已有片段作为 caption
            plot["description"] = title
        plot["title"] = academic_chart_title(
            name=str(plot.get("plot_id") or "result"),
            note=fixed,
            iteration_number=int(plot.get("iteration_number") or 0),
        )
        changed = True
    elif not cap and len(title) > 80:
        # 长 title 无 caption：拆到 caption，title 取首句
        plot["caption"] = title
        plot["description"] = title
        plot["title"] = academic_chart_title(
            name=str(plot.get("plot_id") or "result"),
            note=title,
            iteration_number=int(plot.get("iteration_number") or 0),
        )
        changed = True
    return changed


def sync_db_plots(report_id: str, plots: List[Dict[str, Any]], db_report_id: str = "") -> bool:
    try:
        from app.core.database import SessionLocal, init_db
        from app.models.project import Report
        from app.services.report_plot_service import prepare_plots_for_persistence
    except Exception as exc:
        print(f"  [db skip] import: {exc}")
        return False
    try:
        init_db()
    except Exception as exc:
        print(f"  [db skip] init: {exc}")
        return False
    from app.core.database import SessionLocal as SL

    if SL is None:
        print("  [db skip] SessionLocal is None")
        return False
    db = SL()
    try:
        ids = [x for x in (db_report_id, report_id) if x]
        row = None
        for rid in ids:
            row = db.query(Report).filter(Report.id == rid).first()
            if row:
                break
        if row is None:
            for r in db.query(Report).all():
                blob = " ".join(
                    str(x or "")
                    for x in (
                        getattr(r, "id", None),
                        getattr(r, "pdf_path", None),
                        (r.extra_metadata or {}).get("report_path")
                        if isinstance(r.extra_metadata, dict)
                        else "",
                        (r.extra_metadata or {}).get("report_id")
                        if isinstance(r.extra_metadata, dict)
                        else "",
                    )
                )
                if any(rid in blob for rid in ids):
                    row = r
                    break
        if not row:
            return False
        extra = dict(row.extra_metadata or {}) if isinstance(row.extra_metadata, dict) else {}
        extra["plots"] = prepare_plots_for_persistence(plots, report_file_id=report_id)
        row.extra_metadata = extra
        db.add(row)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        print(f"  [db err] {report_id}: {exc}")
        return False
    finally:
        db.close()


def main() -> None:
    by_stem, all_desc = load_note_corpus()
    print(f"corpus stems={len(by_stem)} descriptions={len(all_desc)}")
    repaired_reports = 0
    repaired_plots = 0
    for d in sorted(REPORTS.iterdir()):
        if not d.is_dir():
            continue
        path = d / "report_data.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        plots = data.get("plots")
        if not isinstance(plots, list) or not plots:
            continue
        changed_n = 0
        for pl in plots:
            if repair_plot(pl, by_stem, all_desc):
                changed_n += 1
        if not changed_n:
            continue
        data["plots"] = plots
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            db_ok = sync_db_plots(
                d.name,
                plots,
                db_report_id=str(data.get("report_id") or ""),
            )
        except Exception as exc:
            db_ok = False
            print(f"  [db exc] {d.name}: {exc}")
        repaired_reports += 1
        repaired_plots += changed_n
        print(f"repaired {d.name}: plots={changed_n} db={db_ok}")
    print(f"done reports={repaired_reports} plots={repaired_plots}")


if __name__ == "__main__":
    main()
