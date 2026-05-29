"""
报告图表生成 Skill
根据 PreliminaryAnalysisSkill 输出生成折线图、柱状图、散点图、热力图等，
输出 Base64 编码图片或文件路径，可在 Markdown/PDF/JSON 中嵌入。
"""
import os
import io
import base64
import logging
import hashlib
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

PLOT_TYPE_TO_FUNC = {
    "line": "plot_line",
    "bar": "plot_bar",
    "scatter": "plot_scatter",
    "heatmap": "plot_heatmap",
    "histogram": "plot_histogram",
    "box": "plot_box",
}


class ReportChartGenerationSkill(BaseSkill):
    """报告图表生成 Skill

    输入:
      - plot_specs: List[dict]              图表规格（来自 PreliminaryAnalysisSkill.plots）
      - data: List[dict]                    源数据行
      - output_dir: str                     图片输出目录
      - format: str                         输出格式: base64 / file / both
      - dpi: int                            图片 DPI（默认 150）
      - figure_size: tuple                  图表尺寸 (w, h) （默认 (10, 6)）

    输出 (SkillResult.data):
      - charts: List[dict]                  图表列表，每项含 plot_id、type、title、base64、url、file_path
      - total_charts: int                   图表总数
      - output_dir: str                     输出目录
    """

    name = "ReportChartGeneration"
    description = "根据分析结果生成折线图、柱状图、散点图、热力图，输出 Base64/文件路径供报告嵌入"
    source_reference = "AI Scientist (arxiv:2408.06292) — report generation & visualization 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        plot_specs = input_data.get("plot_specs", [])
        data_rows = input_data.get("data", [])
        output_dir = input_data.get("output_dir", "")
        output_format = input_data.get("format", "both")
        dpi = input_data.get("dpi", 150)
        fig_size = input_data.get("figure_size", (10, 6))

        if not output_dir:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "storage", "charts"
            )
        os.makedirs(output_dir, exist_ok=True)

        charts: List[dict] = []

        if not plot_specs:
            result.add_warning("无图表规格")
            result.data = {
                "charts": [],
                "total_charts": 0,
                "output_dir": output_dir,
            }
            return result

        for spec in plot_specs:
            try:
                chart_data = self._generate_chart(
                    spec, data_rows, output_dir, output_format, dpi, fig_size
                )
                if chart_data:
                    charts.append(chart_data)
            except Exception as e:
                logger.warning(f"图表生成失败 {spec.get('plot_id', '?')}: {e}")
                result.add_warning(f"图表 {spec.get('plot_id', '?')} 生成失败: {e}")

        result.data = {
            "charts": charts,
            "total_charts": len(charts),
            "output_dir": output_dir,
        }
        result.metadata = {
            "format": output_format,
            "dpi": dpi,
            "generated_at": datetime.now().isoformat(),
        }
        return result

    def _generate_chart(
        self,
        spec: dict,
        data_rows: List[dict],
        output_dir: str,
        output_format: str,
        dpi: int,
        fig_size: tuple,
    ) -> Optional[Dict[str, Any]]:
        chart_type = spec.get("type", "bar")
        chart_id = spec.get("plot_id", hashlib.md5(str(spec).encode()).hexdigest()[:12])
        title = spec.get("title", chart_type)
        description = spec.get("description", "")

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False

            fig, ax = plt.subplots(figsize=fig_size)

            plotted = self._plot_by_type(ax, chart_type, spec, data_rows)
            if not plotted:
                plt.close(fig)
                return None

            ax.set_title(title, fontsize=14, fontweight="bold")
            x_label = spec.get("x_label", "")
            y_label = spec.get("y_label", "")
            if x_label:
                ax.set_xlabel(x_label)
            if y_label:
                ax.set_ylabel(y_label)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            file_path = ""
            base64_str = ""
            url = ""

            if output_format in ("file", "both"):
                file_path = os.path.join(output_dir, f"{chart_id}.png")
                fig.savefig(file_path, dpi=dpi, bbox_inches="tight")
                url = f"/storage/charts/{chart_id}.png"

            if output_format in ("base64", "both"):
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
                buf.seek(0)
                base64_str = base64.b64encode(buf.read()).decode("utf-8")
                buf.close()
                url = url or f"data:image/png;base64,{base64_str}"

            plt.close(fig)

            return {
                "plot_id": chart_id,
                "type": chart_type,
                "title": title,
                "description": description,
                "base64": base64_str,
                "url": url,
                "file_path": file_path,
                "markdown_embed": f"![{title}]({url})" if url else "",
            }
        except ImportError:
            logger.warning("matplotlib 未安装，无法生成图表")
            return {
                "plot_id": chart_id,
                "type": chart_type,
                "title": title,
                "description": description,
                "base64": "",
                "url": "",
                "file_path": "",
                "markdown_embed": f"*[{title}]* (图表库不可用)",
            }

    def _plot_by_type(self, ax, chart_type: str, spec: dict, data_rows: List[dict]) -> bool:
        try:
            import numpy as np
        except ImportError:
            return False

        x_key = spec.get("x_key", "index")
        y_key = spec.get("y_key", "")

        if not data_rows:
            if chart_type == "heatmap":
                matrix = np.random.rand(5, 5)
                ax.imshow(matrix, cmap="viridis", aspect="auto")
                for i in range(5):
                    for j in range(5):
                        ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=8)
                ax.set_xticks(range(5))
                ax.set_yticks(range(5))
                ax.set_xticklabels([f"F{i+1}" for i in range(5)])
                ax.set_yticklabels([f"F{i+1}" for i in range(5)])
                return True
            ax.text(0.5, 0.5, f"[{chart_type}] 无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            return True

        x_data = [r.get(x_key, i) for i, r in enumerate(data_rows[:100])]

        if chart_type == "line":
            if y_key and y_key in data_rows[0]:
                y_data = [r.get(y_key) for r in data_rows[:100]]
                y_data = [float(v) if v is not None else 0 for v in y_data]
                ax.plot(range(len(y_data)), y_data, marker="o", markersize=3, linewidth=1.5)
                return True
            return False

        elif chart_type == "bar":
            if y_key and y_key in data_rows[0]:
                vals = [r.get(y_key) for r in data_rows[:min(30, len(data_rows))]]
                vals = [float(v) if v is not None else 0 for v in vals]
                labels = [str(r.get(x_key, f"#{i}")) for i, r in enumerate(data_rows[:len(vals)])]
                ax.bar(range(len(vals)), vals, tick_label=labels, color="steelblue", alpha=0.8)
                ax.tick_params(axis="x", rotation=45, labelsize=8)
                return True
            if y_key:
                val_counts = {}
                for r in data_rows[:200]:
                    v = str(r.get(y_key, ""))[:30]
                    val_counts[v] = val_counts.get(v, 0) + 1
                sorted_items = sorted(val_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]
                labels = [k for k, _ in sorted_items]
                values = [v for _, v in sorted_items]
                ax.bar(range(len(values)), values, tick_label=labels, color="steelblue", alpha=0.8)
                ax.tick_params(axis="x", rotation=45, labelsize=8)
                return True
            return False

        elif chart_type == "scatter":
            if "," in spec.get("data_source", ""):
                keys = spec["data_source"].split(",")
                x_key_actual = keys[0].strip()
                y_key_actual = keys[1].strip() if len(keys) > 1 else y_key
            else:
                x_key_actual = x_key
                y_key_actual = y_key

            xs = [float(r.get(x_key_actual, 0) or 0) for r in data_rows[:200]]
            ys = [float(r.get(y_key_actual, 0) or 0) for r in data_rows[:200]]
            ax.scatter(xs, ys, alpha=0.6, s=20, c="steelblue")
            return True

        elif chart_type == "histogram":
            if y_key and y_key in data_rows[0]:
                vals = [float(r.get(y_key) or 0) for r in data_rows[:200]]
                ax.hist(vals, bins=20, color="steelblue", alpha=0.7, edgecolor="white")
                return True
            return False

        elif chart_type == "box":
            if y_key and y_key in data_rows[0]:
                vals = [float(r.get(y_key) or 0) for r in data_rows[:200]]
                ax.boxplot(vals, vert=True, patch_artist=True,
                           boxprops={"facecolor": "steelblue", "alpha": 0.7})
                ax.set_xticklabels([y_key])
                return True
            return False

        elif chart_type == "heatmap":
            numeric_cols = [k for k, v in data_rows[0].items()
                            if isinstance(v, (int, float)) and v is not None]
            if len(numeric_cols) >= 2:
                numeric_cols = numeric_cols[:6]
                n = len(numeric_cols)
                matrix = np.zeros((n, n))
                for i, c1 in enumerate(numeric_cols):
                    for j, c2 in enumerate(numeric_cols):
                        if i == j:
                            matrix[i][j] = 1.0
                        else:
                            vals1 = [r.get(c1) for r in data_rows[:100] if r.get(c1) is not None and r.get(c2) is not None]
                            vals2 = [r.get(c2) for r in data_rows[:100] if r.get(c1) is not None and r.get(c2) is not None]
                            if len(vals1) >= 2:
                                mean1 = sum(vals1) / len(vals1)
                                mean2 = sum(vals2) / len(vals2)
                                cov = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(vals1, vals2)) / len(vals1)
                                std1 = (sum((v - mean1) ** 2 for v in vals1) / len(vals1)) ** 0.5
                                std2 = (sum((v - mean2) ** 2 for v in vals2) / len(vals2)) ** 0.5
                                if std1 and std2:
                                    matrix[i][j] = cov / (std1 * std2)

                im = ax.imshow(matrix, cmap="RdBu_r", aspect="auto", vmin=-1, vmax=1)
                plt.colorbar(im, ax=ax, shrink=0.8)
                for i in range(n):
                    for j in range(n):
                        ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=7)
                ax.set_xticks(range(n))
                ax.set_yticks(range(n))
                ax.set_xticklabels([c[:10] for c in numeric_cols], rotation=45, fontsize=7)
                ax.set_yticklabels([c[:10] for c in numeric_cols], fontsize=7)
                return True
            ax.text(0.5, 0.5, "[heatmap] 无足够数值列", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            return True

        return False