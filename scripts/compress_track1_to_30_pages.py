# -*- coding: utf-8 -*-
"""压缩赛道一模板版式，目标 ≤30 页（尽量不改正文措辞）。"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pythoncom
import win32com.client

TPL = Path(
    r"d:/Workplace/AISci/output/提交/模板/赛道一-方向1A-科学假设生成与研究计划设计-提交要求及模板.docx"
)

# Word constants
WD_STAT_PAGES = 2
WD_LINE_SPACE_MULTIPLE = 5
CM = 28.35  # points per cm (approx)


def open_word(path: Path, read_only: bool = False):
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Open(
        str(path.resolve()),
        ConfirmConversions=False,
        ReadOnly=read_only,
        AddToRecentFiles=False,
    )
    return word, doc


def page_count(doc) -> int:
    # force pagination
    doc.Repaginate()
    return int(doc.ComputeStatistics(WD_STAT_PAGES))


def set_margins(doc, cm: float = 2.0) -> None:
    ps = doc.PageSetup
    m = cm * CM
    ps.LeftMargin = m
    ps.RightMargin = m
    ps.TopMargin = m
    ps.BottomMargin = m


def shrink_shapes(doc, schematic_max_w_cm: float, reg_max_h_cm: float) -> None:
    """InlineShapes 1-2 报名截图；3-6 为 P2/P6/P7/P12 示意图。"""
    n = doc.InlineShapes.Count
    for i in range(1, n + 1):
        s = doc.InlineShapes(i)
        w_cm = s.Width / CM
        h_cm = s.Height / CM
        if i <= 2:
            # 报名表截图：限制高度，保持比例
            if h_cm > reg_max_h_cm:
                scale = reg_max_h_cm / h_cm
                s.Height = reg_max_h_cm * CM
                s.Width = w_cm * scale * CM
        else:
            if w_cm > schematic_max_w_cm:
                scale = schematic_max_w_cm / w_cm
                s.Width = schematic_max_w_cm * CM
                s.Height = h_cm * scale * CM


def tighten_paragraphs(doc, space_after_cap: float = 4.0, line_mult: float = 1.05) -> None:
    """压缩段后距与行距（中文 Word 样式名因环境而异，直接扫段落更稳）。"""
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        pf = p.Format
        try:
            if pf.SpaceAfter > space_after_cap:
                pf.SpaceAfter = space_after_cap
            if pf.SpaceBefore > 3:
                pf.SpaceBefore = 3
            # LineSpacingRule 5 = Multiple；LineSpacing 为倍数*240 的旧式，或直接倍数
            # 对 Multiple：LineSpacing 常为 1.15 等浮点；保守只在明显偏大时压
            if pf.LineSpacingRule == WD_LINE_SPACE_MULTIPLE and pf.LineSpacing > line_mult + 0.01:
                # 有的文档 LineSpacing 存的是 12~14（磅），有的是 1.15
                if pf.LineSpacing >= 8:
                    # 当作磅：略压到约 1.05*字体
                    pf.LineSpacing = max(12.0, pf.LineSpacing * 0.92)
                else:
                    pf.LineSpacing = line_mult
        except Exception:
            continue


def tighten_styles(doc) -> None:
    for name in ["正文", "Normal", "标题 1", "标题 2", "Heading 1", "Heading 2", "列表项目符号"]:
        try:
            st = doc.Styles(name)
            pf = st.ParagraphFormat
            if pf.SpaceAfter > 6:
                pf.SpaceAfter = 6
            if pf.SpaceBefore > 6:
                pf.SpaceBefore = 6
        except Exception:
            pass


def compress_once(
    path: Path,
    margin_cm: float,
    schematic_max_w_cm: float,
    reg_max_h_cm: float,
    space_after_cap: float,
) -> int:
    word, doc = open_word(path, read_only=False)
    try:
        set_margins(doc, margin_cm)
        tighten_styles(doc)
        shrink_shapes(doc, schematic_max_w_cm, reg_max_h_cm)
        tighten_paragraphs(doc, space_after_cap=space_after_cap)
        pages = page_count(doc)
        doc.Save()
        return pages
    finally:
        doc.Close(False)
        word.Quit()
        pythoncom.CoUninitialize()


def main() -> None:
    if not TPL.exists():
        raise FileNotFoundError(TPL)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TPL.with_name(TPL.stem + f".pre30p_bak_{stamp}.docx")
    shutil.copy2(TPL, bak)
    print("backup", bak.name)

    word, doc = open_word(TPL, read_only=True)
    try:
        before = page_count(doc)
    finally:
        doc.Close(False)
        word.Quit()
        pythoncom.CoUninitialize()
    print("pages before", before)

    # 阶梯压缩：够用即停，避免过度压扁
    attempts = [
        dict(margin_cm=2.1, schematic_max_w_cm=14.5, reg_max_h_cm=6.8, space_after_cap=6.0),
        dict(margin_cm=2.0, schematic_max_w_cm=13.8, reg_max_h_cm=6.2, space_after_cap=4.0),
        dict(margin_cm=1.9, schematic_max_w_cm=13.2, reg_max_h_cm=5.8, space_after_cap=3.0),
        dict(margin_cm=1.8, schematic_max_w_cm=12.6, reg_max_h_cm=5.4, space_after_cap=2.0),
    ]

    pages = before
    for i, cfg in enumerate(attempts, 1):
        pages = compress_once(TPL, **cfg)
        print(f"attempt {i}", cfg, "->", pages)
        if pages <= 30:
            break

    print("pages after", pages)
    if pages > 30:
        print("WARN still above 30; may need light text condensation")
    else:
        print("OK within 30 pages")


if __name__ == "__main__":
    main()
