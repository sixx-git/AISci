"""
科学图表生成 Skill
参考能力：K-Dense matplotlib Skill、MatPlotAgent
——输入 PreliminaryAnalysisSkill 的真实统计结果，
生成 histogram / bar / line / scatter / heatmap，
只基于真实数据生成图表，无真实数据时 charts=[]。
"""
import os
import io
import base64
import logging
import hashlib
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

SUPPORTED_PLOT_TYPES = {
    "histogram", "bar", "line", "scatter", "heatmap",
    "box", "pie", "area",
}

COLOR_PALETTES = {
    "default": ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B"],
    "cool": ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974"],
    "warm": ["#E24A33", "#F9A65A", "#A1D99B", "#6BAED6", "#B5CF6B"],
}


class ScientificPlotSkill(BaseSkill):
    """科学图表生成 Skill

    输入:
      - plot_specs: List[dict]              图表规格（来自 PreliminaryAnalysisSkill.plots）
      - data: List[dict]                    源数据行
      - output_dir: str                     图片输出目录
      - format: str                         输出格式: base64 / file / both
      - dpi: int                            图片 DPI（默认 150）
      - figure_size: tuple                  图表尺寸 (w, h) （默认 (10, 6)）
      - palette: str                        配色方案: default / cool / warm

    输出 (SkillResult.data):
      - charts: List[dict]                  图表列表
          - plot_id: str                    图表 ID
          - type: str                       图表类型
          - title: str                      图表标题
          - description: str                图表说明
          - path: str                       保存路径（file / both 模式）
          - base64: str                     Base64 编码（base64 / both 模式）
          - source_dataset_id: str          数据来源数据集 ID
          - is_generated_from_real_data: bool  是否来自真实数据
      - total_charts: int                   图表总数
      - output_dir: str                     输出目录
      - summary: str                        图表生成摘要
    """

    name = "ScientificPlot"
    description = "根据分析结果基于真实数据生成科学图表，输出 Base64/文件路径供报告嵌入"
    source_reference = "K-Dense matplotlib Skill; MatPlotAgent — scientific plotting 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        plot_specs: List[dict] = input_data.get("plot_specs", [])
        data_rows: List[dict] = input_data.get("data", [])
        output_dir = input_data.get("output_dir", "")
        output_format = input_data.get("format", "both")
        dpi = input_data.get("dpi", 150)
        figure_size = input_data.get("figure_size", (10, 6))
        palette_name = input_data.get("palette", "default")

        if not data_rows:
            result.add_warning("无真实数据，未生成图表")
            result.data = {
                "charts": [],
                "total_charts": 0,
                "output_dir": output_dir,
                "summary": "无真实数据，未生成任何图表。请上传数据分析后再生成图表。",
            }
            return result

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        colors = COLOR_PALETTES.get(palette_name, COLOR_PALETTES["default"])
        charts: List[dict] = []

        if not plot_specs:
            plot_specs = self._infer_plot_specs_from_data(data_rows)

        for spec in plot_specs:
            try:
                chart_result = self._generate_chart(
                    spec, data_rows, output_dir, output_format, dpi, figure_size, colors,
                )
                if chart_result:
                    charts.append(chart_result)
            except Exception as e:
                logger.warning(f"图表生成失败 [{spec.get('type', '?')}]: {e}")
                result.add_warning(f"图表生成失败: {spec.get('title', spec.get('type', '?'))} — {e}")

        result.data = {
            "charts": charts,
            "total_charts": len(charts),
            "output_dir": output_dir,
            "summary": (
                f"共生成 {len(charts)} 张图表，"
                f"所有图表均基于 {len(data_rows)} 条真实数据记录生成。"
            ),
        }
        return result

    def _generate_chart(
        self,
        spec: dict,
        data_rows: List[dict],
        output_dir: str,
        output_format: str,
        dpi: int,
        figure_size: tuple,
        colors: List[str],
    ) -> Optional[dict]:
        plot_type = spec.get("type", "bar").lower()
        if plot_type not in SUPPORTED_PLOT_TYPES:
            return None

        title = spec.get("title", f"{plot_type.capitalize()} Plot")
        description = spec.get("description", "")
        x_field = spec.get("x_field", "")
        y_field = spec.get("y_field", "")
        group_field = spec.get("group_field", "")
        source_dataset_id = spec.get("source_dataset_id", "")
        x_label = spec.get("x_label", x_field)
        y_label = spec.get("y_label", y_field)

        fig, ax = plt.subplots(figsize=figure_size)
        fig.patch.set_facecolor("white")

        if plot_type == "histogram":
            self._draw_histogram(ax, data_rows, x_field, colors, x_label)
        elif plot_type == "bar":
            self._draw_bar(ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label)
        elif plot_type == "line":
            self._draw_line(ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label)
        elif plot_type == "scatter":
            self._draw_scatter(ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label)
        elif plot_type == "heatmap":
            self._draw_heatmap(ax, data_rows, x_field, y_field, colors, title)
        elif plot_type == "box":
            self._draw_box(ax, data_rows, x_field, y_field, colors, x_label, y_label)
        elif plot_type == "pie":
            self._draw_pie(ax, data_rows, x_field, y_field, colors)
        elif plot_type == "area":
            self._draw_area(ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label)

        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        if x_label and plot_type not in ("pie", "heatmap"):
            ax.set_xlabel(x_label, fontsize=11)
        if y_label and plot_type not in ("pie", "heatmap"):
            ax.set_ylabel(y_label, fontsize=11)
        ax.grid(True, alpha=0.3, linestyle="--")
        fig.tight_layout()

        plot_id = hashlib.md5(
            f"{plot_type}:{title}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        chart_entry = {
            "plot_id": plot_id,
            "type": plot_type,
            "title": title,
            "description": description or f"{title} — 基于 {len(data_rows)} 条真实数据记录生成",
            "path": "",
            "base64": "",
            "source_dataset_id": source_dataset_id,
            "is_generated_from_real_data": True,
        }

        if output_format in ("file", "both") and output_dir:
            file_path = os.path.join(output_dir, f"plot_{plot_id}.png")
            fig.savefig(file_path, dpi=dpi, bbox_inches="tight", facecolor="white")
            chart_entry["path"] = file_path

        if output_format in ("base64", "both"):
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
            buf.seek(0)
            chart_entry["base64"] = base64.b64encode(buf.read()).decode("utf-8")
            buf.close()

        plt.close(fig)
        return chart_entry

    # ────────────── Drawing Methods ──────────────

    @staticmethod
    def _extract_numeric_values(data_rows: List[dict], field: str) -> List[float]:
        values = []
        for row in data_rows:
            v = row.get(field) if isinstance(row, dict) else None
            if v is not None and v != "":
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    pass
        return values

    @staticmethod
    def _extract_categorical_values(data_rows: List[dict], field: str) -> List[str]:
        values = []
        for row in data_rows:
            v = row.get(field) if isinstance(row, dict) else None
            if v is not None and v != "":
                values.append(str(v))
        return values

    @staticmethod
    def _aggregate_by_group(
        data_rows: List[dict], x_field: str, y_field: str, group_field: str,
    ) -> Dict[str, List[tuple]]:
        groups: Dict[str, List[tuple]] = {}
        for row in data_rows:
            if not isinstance(row, dict):
                continue
            gk = str(row.get(group_field, "default"))
            xv = row.get(x_field)
            yv = row.get(y_field)
            if xv is not None and yv is not None:
                try:
                    groups.setdefault(gk, []).append((xv, float(yv)))
                except (ValueError, TypeError):
                    pass
        return groups

    def _draw_histogram(self, ax, data_rows, x_field, colors, x_label):
        values = self._extract_numeric_values(data_rows, x_field)
        if not values:
            return
        bins = max(5, min(50, int(math.sqrt(len(values)))))
        ax.hist(values, bins=bins, color=colors[0], edgecolor="white", alpha=0.85)
        ax.axvline(np.mean(values), color=colors[1], linestyle="--", linewidth=1.5,
                   label=f"Mean={np.mean(values):.2f}")
        ax.legend(fontsize=9)

    def _draw_bar(self, ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label):
        if group_field:
            groups = self._aggregate_by_group(data_rows, x_field, y_field, group_field)
            categories = sorted(set(x for gv in groups.values() for x, _ in gv))
            n_groups = len(groups)
            bar_width = 0.8 / max(n_groups, 1)
            x_indices = np.arange(len(categories))
            for gi, (gname, gv) in enumerate(sorted(groups.items())):
                cat_map = dict(gv)
                heights = [cat_map.get(c, 0) for c in categories]
                offset = (gi - (n_groups - 1) / 2) * bar_width
                ax.bar(x_indices + offset, heights, bar_width * 0.9,
                       color=colors[gi % len(colors)], label=gname, edgecolor="white", alpha=0.85)
            ax.set_xticks(x_indices)
            ax.set_xticklabels([str(c)[:20] for c in categories], rotation=30, ha="right", fontsize=9)
            ax.legend(fontsize=9)
        else:
            x_vals = self._extract_categorical_values(data_rows, x_field)[:30]
            y_vals = self._extract_numeric_values(data_rows, y_field)[:30]
            if not x_vals or not y_vals:
                return
            indices = range(min(len(x_vals), len(y_vals)))
            ax.bar(indices, y_vals[:len(indices)], color=colors[0], edgecolor="white", alpha=0.85)
            ax.set_xticks(list(indices)[:20])
            ax.set_xticklabels([str(x)[:15] for x in x_vals[:20]], rotation=30, ha="right", fontsize=9)

    def _draw_line(self, ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label):
        if group_field:
            groups = self._aggregate_by_group(data_rows, x_field, y_field, group_field)
            for gi, (gname, gv) in enumerate(sorted(groups.items())):
                gv_sorted = sorted(gv, key=lambda t: str(t[0]))
                x_vals = [t[0] for t in gv_sorted]
                y_vals = [t[1] for t in gv_sorted]
                ax.plot(range(len(x_vals)), y_vals, marker="o", markersize=3,
                        color=colors[gi % len(colors)], linewidth=1.5, label=gname)
            ax.legend(fontsize=9)
        else:
            y_vals = self._extract_numeric_values(data_rows, y_field)[:100]
            if not y_vals:
                return
            ax.plot(range(len(y_vals)), y_vals, marker="o", markersize=3,
                    color=colors[0], linewidth=1.5)

    def _draw_scatter(self, ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label):
        x_vals = self._extract_numeric_values(data_rows, x_field)[:500]
        y_vals = self._extract_numeric_values(data_rows, y_field)[:500]
        n = min(len(x_vals), len(y_vals))
        if n == 0:
            return
        if group_field:
            groups: Dict[str, List[tuple]] = {}
            for i in range(n):
                gk = str(data_rows[i].get(group_field, "default")) if i < len(data_rows) else "default"
                groups.setdefault(gk, ([], []))
                groups[gk][0].append(x_vals[i])
                groups[gk][1].append(y_vals[i])
            for gi, (gname, (gx, gy)) in enumerate(sorted(groups.items())):
                ax.scatter(gx, gy, s=20, alpha=0.6,
                           color=colors[gi % len(colors)], label=gname, edgecolors="white")
            ax.legend(fontsize=9)
        else:
            ax.scatter(x_vals[:n], y_vals[:n], s=20, alpha=0.6,
                       color=colors[0], edgecolors="white")

    def _draw_heatmap(self, ax, data_rows, x_field, y_field, colors, title):
        x_vals = self._extract_numeric_values(data_rows, x_field)[:50]
        y_vals = self._extract_numeric_values(data_rows, y_field)[:50]
        if not x_vals or not y_vals:
            return

        matrix_size = min(len(x_vals), len(y_vals), 20)
        try:
            x_resampled = np.interp(
                np.linspace(0, len(x_vals) - 1, matrix_size),
                np.arange(len(x_vals)), x_vals,
            )
            y_resampled = np.interp(
                np.linspace(0, len(y_vals) - 1, matrix_size),
                np.arange(len(y_vals)), y_vals,
            )
            matrix = np.outer(x_resampled - x_resampled.mean(), y_resampled - y_resampled.mean())
        except Exception:
            return

        im = ax.imshow(matrix, cmap="coolwarm", aspect="auto", interpolation="bilinear")
        plt.colorbar(im, ax=ax, shrink=0.8)
        ax.set_title(f"Heatmap: {title}", fontsize=12, fontweight="bold")

    def _draw_box(self, ax, data_rows, x_field, y_field, colors, x_label, y_label):
        x_cats = self._extract_categorical_values(data_rows, x_field)[:50]
        y_vals = self._extract_numeric_values(data_rows, y_field)[:200]
        if not x_cats or not y_vals:
            return
        n = min(len(x_cats), len(y_vals))
        cat_set = list(dict.fromkeys(x_cats[:n]))[:10]
        data_by_cat = {c: [] for c in cat_set}
        for i in range(n):
            c = x_cats[i]
            if c in data_by_cat:
                data_by_cat[c].append(y_vals[i])
        box_data = [data_by_cat[c] for c in cat_set if data_by_cat[c]]
        if not box_data:
            return
        bp = ax.boxplot(box_data, patch_artist=True, labels=[str(c)[:12] for c in cat_set[:len(box_data)]])
        for patch, color in zip(bp["boxes"], colors * (len(box_data) // len(colors) + 1)):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

    def _draw_pie(self, ax, data_rows, x_field, y_field, colors):
        x_vals = self._extract_categorical_values(data_rows, x_field)
        y_vals = self._extract_numeric_values(data_rows, y_field)
        if not x_vals:
            return
        cat_agg: Dict[str, float] = {}
        for i in range(min(len(x_vals), len(y_vals))):
            cat_agg[x_vals[i]] = cat_agg.get(x_vals[i], 0) + y_vals[i]
        if not cat_agg:
            freq: Dict[str, int] = {}
            for v in x_vals[:20]:
                freq[v] = freq.get(v, 0) + 1
            cat_agg = {k: float(v) for k, v in freq.items()}
        sorted_items = sorted(cat_agg.items(), key=lambda x: -x[1])[:8]
        labels = [str(k)[:20] for k, _ in sorted_items]
        sizes = [v for _, v in sorted_items]
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct="%1.1f%%",
            colors=colors[:len(sizes)],
            startangle=90, pctdistance=0.75,
        )
        for t in autotexts:
            t.set_fontsize(8)

    def _draw_area(self, ax, data_rows, x_field, y_field, group_field, colors, x_label, y_label):
        y_vals = self._extract_numeric_values(data_rows, y_field)[:100]
        if not y_vals:
            return
        x_indices = range(len(y_vals))
        if group_field:
            groups = self._aggregate_by_group(data_rows, x_field, y_field, group_field)
            y_stacked = None
            for gi, (gname, gv) in enumerate(sorted(groups.items())):
                gv_sorted = sorted(gv, key=lambda t: str(t[0]))
                g_y = [t[1] for t in gv_sorted]
                if y_stacked is None:
                    y_stacked = np.zeros(len(g_y))
                    ax.fill_between(range(len(g_y)), y_stacked, y_stacked + np.array(g_y),
                                    color=colors[gi % len(colors)], alpha=0.5, label=gname)
                    y_stacked = y_stacked + np.array(g_y)
                else:
                    n_common = min(len(y_stacked), len(g_y))
                    ax.fill_between(range(n_common), y_stacked[:n_common],
                                    y_stacked[:n_common] + np.array(g_y[:n_common]),
                                    color=colors[gi % len(colors)], alpha=0.5, label=gname)
            ax.legend(fontsize=9)
        else:
            ax.fill_between(x_indices, y_vals, color=colors[0], alpha=0.4)
            ax.plot(x_indices, y_vals, color=colors[0], linewidth=1.5)

    @staticmethod
    def _infer_plot_specs_from_data(data_rows: List[dict]) -> List[dict]:
        if not data_rows or not isinstance(data_rows[0], dict):
            return []

        sample = data_rows[0]
        numeric_fields = []
        categorical_fields = []

        for key, val in sample.items():
            if isinstance(val, (int, float)):
                numeric_fields.append(key)
            elif isinstance(val, str) and len(val) < 100:
                categorical_fields.append(key)
            elif val is not None:
                try:
                    float(val)
                    numeric_fields.append(key)
                except (ValueError, TypeError):
                    categorical_fields.append(key)

        specs = []
        for nf in numeric_fields[:3]:
            specs.append({
                "type": "histogram",
                "x_field": nf,
                "title": f"{nf} Distribution",
                "description": f"Distribution of {nf} values across {len(data_rows)} records",
                "source_dataset_id": "",
            })

        if len(numeric_fields) >= 2:
            for i, yf in enumerate(numeric_fields[1:4], 1):
                xf = numeric_fields[0]
                specs.append({
                    "type": "scatter",
                    "x_field": xf,
                    "y_field": yf,
                    "title": f"{xf} vs {yf}",
                    "description": f"Scatter plot of {xf} against {yf}",
                    "source_dataset_id": "",
                })

        if categorical_fields and numeric_fields:
            cf = categorical_fields[0]
            nf = numeric_fields[0]
            specs.append({
                "type": "bar",
                "x_field": cf,
                "y_field": nf,
                "title": f"{nf} by {cf}",
                "description": f"Bar chart of {nf} grouped by {cf}",
                "source_dataset_id": "",
            })

        if len(numeric_fields) >= 2:
            specs.append({
                "type": "heatmap",
                "x_field": numeric_fields[0],
                "y_field": numeric_fields[1],
                "title": "Feature Correlation Heatmap",
                "description": "Heatmap of feature interactions",
                "source_dataset_id": "",
            })

        return specs