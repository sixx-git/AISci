"""
报告图表生成 Skill
根据 PreliminaryAnalysisSkill 输出生成折线图、柱状图、散点图、热力图等，
仅基于真实数据生成图表，禁止在无数据时生成随机图。
输出 Base64 编码图片或文件路径，可在 Markdown/PDF/JSON 中嵌入。
"""
import os
import io
import base64
import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


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
      - charts: List[dict]                  图表列表，每项含 plot_id、type、title、base64、url、
                                            source_dataset_id、is_generated_from_real_data
      - total_charts: int                   图表总数
      - output_dir: str                     输出目录
    """

    name = "ReportChartGeneration"
    description = "根据分析结果基于真实数据生成图表，输出 Base64/文件路径供报告嵌入"
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

        if not plot_specs:
            result.add_warning("无图表规格")
            result.data = {
                "charts": [],
                "total_charts": 0,
                "output_dir": output_dir,
            }
            return result

        if not data_rows:
            result.add_warning("无真实数据，未生成图表")
            result.data = {
                "charts": [],
                "total_charts": 0,
                "output_dir": output_dir,
                "warning": "无真实数据，未生成图表。请上传 CSV/Excel 等结构化数据集以启用图表生成。",
            }
            result.metadata = {
                "format": output_format,
                "dpi": dpi,
                "generated_at": datetime.now().isoformat(),
                "note": "skipped_due_to_no_data",
            }
            return result

        charts: List[dict] = []

        for spec in plot_specs:
            if not spec.get("is_generated_from_real_data"):
                logger.info(f"跳过非真实数据图表: {spec.get('plot_id', '?')}")
                continue
            try:
                chart_data = self._generate_chart(
                    spec, data_rows, output_dir, output_format, dpi, fig_size
                )
                if chart_data:
                    charts.append(chart_data)
            except Exception as e:
                logger.warning(f"图表生成失败 {spec.get('plot_id', '?')}: {e}")
                result.add_warning(f"图表 {spec.get('plot_id', '?')} 生成失败: {e}")

        if not charts:
            result.add_warning("数据行不足以生成任何图表")

        result.data = {
            "charts": charts,
            "total_charts": len(charts),
            "output_dir": output_dir,
        }
        result.metadata = {
            "format": output_format,
            "dpi": dpi,
            "total_charts": len(charts),
            "has_real_data": True,
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
        source_dataset_id = spec.get("source_dataset_id", "")
        is_from_real = spec.get("is_generated_from_real_data", False)

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

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
                "source_dataset_id": source_dataset_id,
                "is_generated_from_real_data": is_from_real,
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
                "source_dataset_id": source_dataset_id,
                "is_generated_from_real_data": False,
            }

    def _plot_by_type(self, ax, chart_type: str, spec: dict, data_rows: List[dict]) -> bool:
        try:
            import numpy as np
        except ImportError:
            return False

        x_key = spec.get("x_key", "index")
        y_key = spec.get("y_key", "")

        if not data_rows:
            return False

        if chart_type == "line":
            if y_key:
                keys_in_data = [y_key in r for r in data_rows[:5]]
                if not any(keys_in_data):
                    numeric_cols = [k for k, v in data_rows[0].items()
                                    if isinstance(v, (int, float)) and v is not None]
                    if numeric_cols:
                        y_key = numeric_cols[0]
                    else:
                        return False
                y_data = []
                for r in data_rows[:200]:
                    v = r.get(y_key)
                    if v is not None:
                        try:
                            y_data.append(float(v))
                        except (ValueError, TypeError):
                            y_data.append(0)
                    else:
                        y_data.append(0)
                if not y_data:
                    return False
                ax.plot(range(len(y_data)), y_data, marker="o", markersize=3, linewidth=1.5)
                return True
            return False

        elif chart_type == "bar":
            if y_key:
                is_numeric_data = True
                for r in data_rows[:5]:
                    v = r.get(y_key)
                    if v is not None and not isinstance(v, (int, float)):
                        try:
                            float(v)
                        except (ValueError, TypeError):
                            is_numeric_data = False
                            break

                if is_numeric_data:
                    vals = []
                    labels = []
                    for i, r in enumerate(data_rows[:30]):
                        v = r.get(y_key)
                        if v is not None:
                            try:
                                vals.append(float(v))
                            except (ValueError, TypeError):
                                vals.append(0)
                        else:
                            vals.append(0)
                        labels.append(str(r.get(x_key, f"#{i}"))[:12])
                    if not vals:
                        return False
                    ax.bar(range(len(vals)), vals, tick_label=labels, color="steelblue", alpha=0.8)
                    ax.tick_params(axis="x", rotation=45, labelsize=8)
                    return True
                else:
                    val_counts: Dict[str, int] = {}
                    for r in data_rows[:200]:
                        v = str(r.get(y_key, ""))[:30]
                        val_counts[v] = val_counts.get(v, 0) + 1
                    if not val_counts:
                        return False
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

            xs = []
            ys = []
            for r in data_rows[:200]:
                xv = r.get(x_key_actual)
                yv = r.get(y_key_actual)
                if xv is not None and yv is not None:
                    try:
                        xs.append(float(xv))
                        ys.append(float(yv))
                    except (ValueError, TypeError):
                        continue
            if not xs:
                return False
            ax.scatter(xs, ys, alpha=0.6, s=20, c="steelblue")
            return True

        elif chart_type == "histogram":
            if y_key:
                vals = []
                for r in data_rows[:500]:
                    v = r.get(y_key)
                    if v is not None:
                        try:
                            vals.append(float(v))
                        except (ValueError, TypeError):
                            continue
                if not vals:
                    return False
                ax.hist(vals, bins=min(30, len(set(vals))), color="steelblue", alpha=0.7, edgecolor="white")
                return True
            return False

        elif chart_type == "box":
            if y_key:
                vals = []
                for r in data_rows[:500]:
                    v = r.get(y_key)
                    if v is not None:
                        try:
                            vals.append(float(v))
                        except (ValueError, TypeError):
                            continue
                if not vals:
                    return False
                ax.boxplot(vals, vert=True, patch_artist=True,
                           boxprops={"facecolor": "steelblue", "alpha": 0.7})
                ax.set_xticklabels([y_key[:20]])
                return True
            return False

        elif chart_type == "heatmap":
            numeric_cols = [k for k, v in data_rows[0].items()
                            if isinstance(v, (int, float)) and v is not None]
            if len(numeric_cols) < 2:
                numeric_cols = []
                for k, v in data_rows[0].items():
                    try:
                        float(v)
                        numeric_cols.append(k)
                    except (ValueError, TypeError):
                        pass

            if len(numeric_cols) < 2:
                return False

            numeric_cols = numeric_cols[:8]
            n = len(numeric_cols)
            matrix = np.zeros((n, n))
            for i, c1 in enumerate(numeric_cols):
                for j, c2 in enumerate(numeric_cols):
                    if i == j:
                        matrix[i][j] = 1.0
                    else:
                        pairs = []
                        for r in data_rows[:200]:
                            v1 = r.get(c1)
                            v2 = r.get(c2)
                            if v1 is not None and v2 is not None:
                                try:
                                    pairs.append((float(v1), float(v2)))
                                except (ValueError, TypeError):
                                    continue
                        if len(pairs) >= 2:
                            mean1 = sum(p[0] for p in pairs) / len(pairs)
                            mean2 = sum(p[1] for p in pairs) / len(pairs)
                            cov = sum((p[0] - mean1) * (p[1] - mean2) for p in pairs) / len(pairs)
                            std1 = (sum((p[0] - mean1) ** 2 for p in pairs) / len(pairs)) ** 0.5
                            std2 = (sum((p[1] - mean2) ** 2 for p in pairs) / len(pairs)) ** 0.5
                            if std1 and std2:
                                matrix[i][j] = cov / (std1 * std2)

            im = ax.imshow(matrix, cmap="RdBu_r", aspect="auto", vmin=-1, vmax=1)
            plt.colorbar(im, ax=ax, shrink=0.8)
            for i in range(n):
                for j in range(n):
                    ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=7)
            ax.set_xticks(range(n))
            ax.set_yticks(range(n))
            ax.set_xticklabels([c[:12] for c in numeric_cols], rotation=45, fontsize=7)
            ax.set_yticklabels([c[:12] for c in numeric_cols], fontsize=7)
            return True

        return False