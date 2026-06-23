"""PDF 图块裁剪 Skill — 为 VLM 图表抽取提供 image_path"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id


class PdfFigureCropSkill(BaseSkill):
    name = "PdfFigureCrop"
    description = "从 PDF 按图注定位页面并导出图块 PNG"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        file_path = input_data.get("file_path", "")
        paper_id = input_data.get("paper_id", "")
        figures = input_data.get("figures", []) or []
        output_dir = input_data.get("output_dir", "")

        if not file_path or not os.path.exists(file_path):
            result.data = {"figures": figures, "cropped_count": 0}
            return result

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(file_path), "figures")
        os.makedirs(output_dir, exist_ok=True)

        cropped = 0
        out_figures: List[Dict[str, Any]] = []

        try:
            import fitz
        except ImportError:
            result.add_warning("PyMuPDF 未安装，跳过图块裁剪")
            result.data = {"figures": figures, "cropped_count": 0}
            return result

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            result.add_warning(f"无法打开 PDF: {exc}")
            result.data = {"figures": figures, "cropped_count": 0}
            return result

        try:
            for fig in figures:
                fig_copy = dict(fig)
                fig_num = str(fig.get("figure_number", "")).strip()
                caption = fig.get("caption", "") or ""
                page_idx = self._find_figure_page(doc, fig_num, caption)

                crop_result = self._export_figure_region(
                    doc, page_idx, output_dir, paper_id, fig_num or new_id("fig")[:8],
                    fig_num, caption,
                )
                if crop_result:
                    fig_copy["image_path"] = crop_result["image_path"]
                    fig_copy["page"] = page_idx + 1
                    fig_copy["crop_method"] = crop_result.get("crop_method", "page_render")
                    fig_copy["bbox"] = crop_result.get("bbox")
                    cropped += 1
                out_figures.append(fig_copy)
        finally:
            doc.close()

        result.data = {"figures": out_figures, "cropped_count": cropped}
        if figures and cropped == 0:
            result.add_warning("未能从 PDF 裁剪图块，将仅使用 caption 规则抽取")
        return result

    @staticmethod
    def _find_figure_page(doc, fig_num: str, caption: str) -> int:
        needles: List[str] = []
        if fig_num:
            needles.extend([
                f"figure {fig_num}",
                f"fig. {fig_num}",
                f"fig {fig_num}",
                f"图 {fig_num}",
            ])
        if caption:
            needles.append(caption[:60].lower())

        for i in range(len(doc)):
            text = (doc[i].get_text() or "").lower()
            for n in needles:
                if n and n.lower() in text:
                    return i
        return 0

    @staticmethod
    def _export_figure_region(
        doc,
        page_idx: int,
        output_dir: str,
        paper_id: str,
        fig_key: str,
        fig_num: str,
        caption: str,
    ) -> Optional[Dict[str, Any]]:
        if page_idx < 0 or page_idx >= len(doc):
            return None

        safe_paper = re.sub(r"[^\w\-]", "_", paper_id)[:24]
        safe_fig = re.sub(r"[^\w\-]", "_", str(fig_key))[:16]
        out_path = os.path.join(output_dir, f"{safe_paper}_fig_{safe_fig}.png")
        page = doc[page_idx]

        proximity = PdfFigureCropSkill._crop_block_proximity(page, doc, fig_num, caption, out_path)
        if proximity:
            return proximity

        return PdfFigureCropSkill._export_page_fallback(page, out_path)

    @staticmethod
    def _crop_block_proximity(page, doc, fig_num: str, caption: str, out_path: str) -> Optional[Dict[str, Any]]:
        try:
            import fitz
        except ImportError:
            return None

        caption_rect = PdfFigureCropSkill._find_caption_rect(page, fig_num, caption)
        if not caption_rect:
            return None

        best_rect = None
        best_area = 0.0
        for block in page.get_text("dict").get("blocks") or []:
            if block.get("type") != 1:
                continue
            bbox = block.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            rect = fitz.Rect(bbox)
            area = rect.width * rect.height
            if area < 2000 or rect.y1 > caption_rect.y0 + 20:
                continue
            if area > best_area:
                best_area = area
                best_rect = rect

        if not best_rect:
            return None

        pad = 8
        clip = fitz.Rect(
            max(0, best_rect.x0 - pad),
            max(0, best_rect.y0 - pad),
            min(page.rect.width, best_rect.x1 + pad),
            min(page.rect.height, best_rect.y1 + pad),
        )
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            pix.save(out_path)
            return {
                "image_path": out_path,
                "crop_method": "block_proximity",
                "bbox": [clip.x0, clip.y0, clip.x1, clip.y1],
            }
        except Exception:
            return None

    @staticmethod
    def _find_caption_rect(page, fig_num: str, caption: str):
        try:
            import fitz
        except ImportError:
            return None

        needles: List[str] = []
        if fig_num:
            needles.extend([f"Figure {fig_num}", f"Fig. {fig_num}", f"Fig {fig_num}", f"图 {fig_num}"])
        if caption:
            needles.append(caption[:40])

        for needle in needles:
            if not needle:
                continue
            rects = page.search_for(needle[:80])
            if rects:
                return rects[0]
        return None

    @staticmethod
    def _export_page_fallback(page, out_path: str) -> Optional[Dict[str, Any]]:
        images = page.get_images(full=True)
        if images:
            try:
                xref = images[0][0]
                base = page.parent.extract_image(xref)
                if base and base.get("image"):
                    with open(out_path, "wb") as f:
                        f.write(base["image"])
                    return {
                        "image_path": out_path,
                        "crop_method": "embedded_image",
                        "bbox": None,
                    }
            except Exception:
                pass

        try:
            import fitz

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pix.save(out_path)
            page_rect = page.rect
            return {
                "image_path": out_path,
                "crop_method": "page_render",
                "bbox": [page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1],
            }
        except Exception:
            return None
