"""Generate report-ready AISci innovation mechanism schematics.

The figures intentionally use a restrained block-diagram style so that data
objects, API messages, decision gates, and feedback paths remain legible when
inserted into the proposal document.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


OUT_DEFAULT = Path("output/innovation_schematics")

COLORS = {
    "ink": "#252525",
    "muted": "#606060",
    "outer": "#8f8f8f",
    "title": "#d7e2f1",
    "title_edge": "#9aa6b3",
    "blue": "#e3f0fa",
    "blue_edge": "#2d8fc4",
    "mint": "#dff2ee",
    "mint_edge": "#20a47a",
    "lavender": "#eeeafd",
    "lavender_edge": "#7566a8",
    "orange": "#fff0d8",
    "orange_edge": "#c7762b",
    "green": "#e9f5d9",
    "green_edge": "#62a52b",
    "panel": "#fafafa",
    "gray": "#ececec",
    "gray_edge": "#7b7b7b",
    "red": "#d95b43",
}


def configure_fonts() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"


def canvas(title: str):
    fig, ax = plt.subplots(figsize=(16, 10), dpi=220)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0.25, 0.25),
            15.5,
            9.5,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="#ffffff",
            edgecolor=COLORS["outer"],
            linewidth=1.5,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.25, 9.17),
            15.5,
            0.58,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=COLORS["title"],
            edgecolor=COLORS["title_edge"],
            linewidth=1.2,
        )
    )
    ax.text(
        8,
        9.46,
        title,
        ha="center",
        va="center",
        fontsize=16,
        fontweight="bold",
        color=COLORS["ink"],
    )
    return fig, ax


def panel(ax, x: float, y: float, w: float, h: float, title: str, edge: str, body: str = ""):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=COLORS["panel"],
            edgecolor=edge,
            linewidth=1.3,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (x, y + h - 0.48),
            w,
            0.48,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor="#ffffff",
            edgecolor=edge,
            linewidth=1.0,
        )
    )
    ax.text(x + w / 2, y + h - 0.24, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color=edge)
    if body:
        ax.text(x + 0.22, y + h - 0.78, body, ha="left", va="top", fontsize=8.3, color=COLORS["muted"], linespacing=1.45)


def block(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str = "",
    face: str = "blue",
    edge: str = "blue_edge",
    title_size: float = 10.5,
    subtitle_size: float = 8.2,
):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=COLORS[face],
            edgecolor=COLORS[edge],
            linewidth=1.25,
        )
    )
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=title_size, fontweight="bold", color=COLORS["ink"])
    if subtitle:
        ax.text(x + w / 2, y + h * 0.28, subtitle, ha="center", va="center", fontsize=subtitle_size, color=COLORS["muted"])


def arrow(ax, start, end, label: str = "", color: str = "#555555", dashed: bool = False, text_offset=(0, 0.12), lw: float = 1.35):
    style = (0, (4, 3)) if dashed else "-"
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=lw,
            linestyle=style,
            color=color,
            connectionstyle="arc3,rad=0",
        )
    )
    if label:
        mx = (start[0] + end[0]) / 2 + text_offset[0]
        my = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=7.6, color=color, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})


def diamond(ax, cx: float, cy: float, w: float, h: float, title: str, subtitle: str = "", edge: str = "green_edge"):
    points = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(points, closed=True, facecolor=COLORS["green"], edgecolor=COLORS[edge], linewidth=1.35))
    ax.text(cx, cy + 0.08, title, ha="center", va="center", fontsize=10, fontweight="bold", color=COLORS["ink"])
    if subtitle:
        ax.text(cx, cy - 0.22, subtitle, ha="center", va="center", fontsize=7.8, color=COLORS["muted"])


def bullets(ax, x: float, y: float, lines: Iterable[str], fontsize: float = 8.1, color: str = "#606060", line_gap: float = 0.33):
    for i, line in enumerate(lines):
        ax.text(x, y - i * line_gap, line, ha="left", va="top", fontsize=fontsize, color=color)


def save(fig, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=240, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(out_dir / f"{name}.svg", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def evidence_chain(out_dir: Path) -> None:
    fig, ax = canvas("证据链迭代推理引擎：运行机制与数据传输（核心创新一）")
    panel(ax, 0.55, 1.1, 3.0, 7.45, "Fact 白名单数据库", COLORS["orange_edge"])
    for i, fact in enumerate(["fact_id: F001", "fact_id: F002", "fact_id: F003", "fact_id: F004"]):
        block(ax, 0.83, 7.35 - i * 0.75, 2.45, 0.46, fact, "source_chunk_id · claim", "gray", "gray_edge", 8.8, 7.0)
    ax.text(2.05, 3.45, "仅允许引用白名单内 fact\n有效来源可定位、可复核", ha="center", va="center", fontsize=8.4, color=COLORS["muted"], style="italic", linespacing=1.5)

    steps = [
        ("步骤 1：提取科学声明", "Claim → structured claims", "blue", "blue_edge"),
        ("步骤 2：检索支持证据", "supporting evidence", "blue", "blue_edge"),
        ("步骤 3：检索反证据", "counter evidence", "mint", "mint_edge"),
        ("步骤 4：证据立场分类", "SUPPORT / REFUTE / NEUTRAL", "lavender", "lavender_edge"),
        ("步骤 5：Fact 白名单约束", "ONLY fact_id from whitelist", "orange", "orange_edge"),
        ("步骤 6：假设修订", "Qwen + rule fallback", "orange", "orange_edge"),
        ("步骤 7：证据接地与引用检查", "grounding + completeness", "mint", "mint_edge"),
        ("步骤 8：证据链构建", "final hypothesis + provenance", "green", "green_edge"),
    ]
    x, w, h = 4.15, 5.55, 0.67
    ys = [8.2 - i * 0.88 for i in range(len(steps))]
    for y, (t, s, fc, ec) in zip(ys, steps):
        block(ax, x, y, w, h, t, s, fc, ec)
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax, (x + w / 2, y1), (x + w / 2, y2 + h), color="#5d5d5d")
    arrow(ax, (3.55, 6.8), (x, ys[4] + h / 2), "fact_id / chunk_id", COLORS["orange_edge"], dashed=True, text_offset=(0, 0.16))

    panel(ax, 10.35, 5.0, 5.05, 3.55, "迭代控制面板", COLORS["lavender_edge"])
    bullets(ax, 10.65, 7.72, [
        "迭代参数：max_iter = N",
        "证据状态：支持证据与反证据",
        "每轮输出：修订假设 + 证据链摘要",
        "质量字段：stance / evidence_level",
        "接口：POST /evidence-chain/iterate",
    ], line_gap=0.46)
    panel(ax, 10.35, 1.1, 5.05, 3.25, "双路径降级机制（Dual-Path Fallback）", COLORS["gray_edge"])
    bullets(ax, 10.65, 3.55, [
        "路径 A：Qwen 智能修订 → 输出新假设",
        "路径 B：规则修订 → 仅保留白名单 fact",
        "触发条件：LLM 失败或偏离约束",
        "返回数据：revised_hypothesis / cited_fact_ids",
    ], line_gap=0.48)
    arrow(ax, (10.35, 6.0), (9.7, ys[4] + h / 2), "约束注入", COLORS["lavender_edge"], dashed=True, text_offset=(-0.08, 0.16))
    arrow(ax, (10.35, 2.55), (9.7, ys[1] + h / 2), "返回步骤 2", COLORS["lavender_edge"], dashed=True, text_offset=(-0.08, -0.30))
    arrow(ax, (x + w, ys[-1] + h / 2), (10.35, 4.6), "evidence_chain", COLORS["green_edge"], text_offset=(0, 0.16))
    save(fig, out_dir, "fig_innovation_1_evidence_chain")


def verdict_gate(out_dir: Path) -> None:
    fig, ax = canvas("Verdict Gate：阶段质量判定、通信与人工放行机制（核心创新二）")
    panel(ax, 0.55, 1.15, 3.1, 7.35, "阶段质量规则注册表", COLORS["lavender_edge"])
    bullets(ax, 0.85, 7.63, [
        "gate_novelty       新颖性",
        "gate_ensemble      集成评审",
        "gate_evidence      证据链",
        "gate_executability 可执行性",
        "gate_sandbox       沙箱执行",
        "gate_plot          图表质量",
        "gate_coverage      覆盖度",
        "gate_hitl          人工审核",
        "gate_acceptance    验收",
        "gate_cot           推理完整性",
        "gate_federated     联邦双门槛",
    ], line_gap=0.42, fontsize=7.8)
    ax.text(2.1, 2.02, "每个 Gate 输出\nPASS / FAIL + 原因 + 证据引用", ha="center", va="center", fontsize=8.5, color=COLORS["muted"], linespacing=1.5)

    x, w = 4.25, 5.7
    block(ax, x, 8.05, w, 0.75, "阶段输出 JSON", "stage_output · metrics · evidence_refs", "blue", "blue_edge")
    block(ax, x, 6.95, w, 0.75, "规则归一化", "thresholds · blockers · required_fields", "lavender", "lavender_edge")
    block(ax, x, 5.85, w, 0.75, "11 类阶段特定质量 Gate", "Boolean decision layer", "mint", "mint_edge")
    diamond(ax, 7.1, 4.45, 3.2, 1.25, "是否通过？", "gate_result.passed")
    for y1, y2 in [(8.05, 7.7), (6.95, 6.6), (5.85, 5.1)]:
        arrow(ax, (7.1, y1), (7.1, y2), color="#555555")

    panel(ax, 10.45, 5.8, 4.95, 2.7, "决策通信报文", COLORS["green_edge"])
    bullets(ax, 10.75, 7.78, [
        "gate_result = {passed, gate_id}",
        "reasons / blockers / evidence_refs",
        "next_action：continue / pause / rerun",
        "持久化：pipeline_run.extra_metadata",
    ], line_gap=0.45)
    panel(ax, 10.45, 1.2, 4.95, 3.0, "HITL 与重跑通道", COLORS["orange_edge"])
    bullets(ax, 10.75, 3.54, [
        "FAIL → 人工审核 / 编辑 / 对话修订",
        "human_modified_output + feedback",
        "POST /human-loop/...",
        "POST /pipeline/rerun-from-stage",
        "审计：audit/{run_id}.jsonl",
    ], line_gap=0.42)

    block(ax, 11.0, 4.35, 3.85, 0.65, "进入下一阶段", "continue", "green", "green_edge", 9.8, 8.0)
    block(ax, 5.0, 2.25, 4.2, 0.75, "暂停并请求人工处理", "pause → review → resume", "orange", "orange_edge")
    arrow(ax, (8.7, 4.45), (11.0, 4.67), "PASS", COLORS["green_edge"], text_offset=(0, 0.18))
    arrow(ax, (7.1, 3.83), (7.1, 3.0), "FAIL", COLORS["red"], text_offset=(0, 0.15))
    arrow(ax, (9.2, 2.62), (10.45, 2.62), "human feedback", COLORS["orange_edge"], dashed=True, text_offset=(0, 0.16))
    arrow(ax, (10.45, 3.9), (9.6, 8.05), "rerun_from_stage", COLORS["orange_edge"], dashed=True, text_offset=(0.25, 0.0))
    arrow(ax, (9.95, 6.95), (10.45, 6.95), "audit record", COLORS["green_edge"], dashed=True, text_offset=(0, 0.16))
    save(fig, out_dir, "fig_innovation_2_verdict_gate")


def feedback_hub(out_dir: Path) -> None:
    fig, ax = canvas("Feedback Hub + HITL：跨阶段反馈传输与重跑机制（核心创新三）")
    panel(ax, 0.55, 1.15, 3.05, 7.35, "反馈来源层", COLORS["orange_edge"])
    sources = [
        ("HITL 人工审核", "stage feedback"),
        ("实验执行结果", "success / failure"),
        ("Data Finder", "coverage / schema"),
        ("文献与证据链", "new facts / weak evidence"),
        ("用户直接输入", "constraints / request"),
    ]
    for i, (t, s) in enumerate(sources):
        block(ax, 0.85, 7.12 - i * 1.08, 2.45, 0.66, t, s, "orange" if i < 2 else "blue", "orange_edge" if i < 2 else "blue_edge", 9.2, 7.4)

    block(ax, 4.15, 7.65, 2.45, 0.75, "阶段 N 输出", "output_data / result", "blue", "blue_edge")
    block(ax, 7.35, 7.65, 2.65, 0.75, "Feedback Hub", "normalize → route → persist", "mint", "mint_edge")
    block(ax, 10.75, 7.65, 2.75, 0.75, "约束存储", "global_constraints / entries", "lavender", "lavender_edge")
    block(ax, 7.35, 5.85, 2.65, 0.75, "后续 Prompt 上下文", "get_active_constraints", "blue", "blue_edge")
    block(ax, 10.75, 5.85, 2.75, 0.75, "阶段 N+1 / 目标重跑", "target_stage / rerun", "green", "green_edge")
    block(ax, 4.15, 3.1, 2.45, 0.75, "HITL 审核面板", "edit / chat / approve", "orange", "orange_edge")
    block(ax, 7.35, 3.1, 2.65, 0.75, "反馈结构化", "source · target · message", "orange", "orange_edge")

    feedback_style = (0, (4, 3))
    feedback_bus_y = 7.35
    for i in range(len(sources)):
        source_y = 7.44 - i * 1.08
        ax.plot([3.6, 3.95], [source_y, source_y], color=COLORS["orange_edge"], linestyle=feedback_style, linewidth=1.35)
        ax.plot([3.95, 3.95], [source_y, feedback_bus_y], color=COLORS["orange_edge"], linestyle=feedback_style, linewidth=1.35)
    ax.plot([3.95, 7.02], [feedback_bus_y, feedback_bus_y], color=COLORS["orange_edge"], linestyle=feedback_style, linewidth=1.35)
    arrow(ax, (7.02, feedback_bus_y), (7.35, 7.78), "", COLORS["orange_edge"], dashed=True)
    ax.text(5.02, 7.12, "feedback_entry", ha="center", va="center", fontsize=7.6, color=COLORS["orange_edge"], bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    arrow(ax, (6.6, 8.02), (7.35, 8.02), "stage_result", COLORS["blue_edge"], text_offset=(0, 0.16))
    arrow(ax, (10.0, 8.02), (10.75, 8.02), "constraint", COLORS["mint_edge"], text_offset=(0, 0.16))
    arrow(ax, (12.1, 7.65), (12.1, 6.6), "inject", COLORS["lavender_edge"], text_offset=(0.2, 0))
    arrow(ax, (10.75, 6.22), (10.0, 6.22), "prompt_context", COLORS["blue_edge"], text_offset=(0, 0.16))
    arrow(ax, (13.5, 6.22), (13.5, 7.65), "rerun_target", COLORS["green_edge"], dashed=True, text_offset=(0.28, 0))
    arrow(ax, (12.1, 5.85), (12.1, 4.65), "stage input", COLORS["green_edge"], text_offset=(0.25, 0))
    arrow(ax, (5.38, 3.85), (7.35, 3.47), "human_edit", COLORS["orange_edge"], text_offset=(0, 0.16))
    arrow(ax, (8.68, 3.85), (8.68, 5.85), "submit feedback", COLORS["orange_edge"], dashed=True, text_offset=(0.45, 0))

    panel(ax, 10.45, 1.2, 4.95, 1.75, "API / 持久化", COLORS["gray_edge"])
    ax.text(10.75, 2.42, "POST /feedback    POST /human-loop    rerun-from-stage\nJSON entries + audit chain", ha="left", va="top", fontsize=8.0, color=COLORS["muted"], linespacing=1.6)
    save(fig, out_dir, "fig_innovation_3_feedback_hub")


def counterfactual(out_dir: Path) -> None:
    fig, ax = canvas("L0 反事实预演：实验前风险过滤与约束注入机制（核心创新四）")
    panel(ax, 0.55, 1.15, 3.05, 7.35, "输入证据与实验计划", COLORS["blue_edge"])
    block(ax, 0.85, 7.15, 2.45, 0.72, "候选假设", "hypothesis + fact_ids", "blue", "blue_edge", 9.5, 7.5)
    block(ax, 0.85, 6.04, 2.45, 0.72, "文献证据", "support / refute", "mint", "mint_edge", 9.5, 7.5)
    block(ax, 0.85, 4.93, 2.45, 0.72, "数据与指标", "columns + primary_metric", "lavender", "lavender_edge", 9.5, 7.5)
    block(ax, 0.85, 3.82, 2.45, 0.72, "实验计划", "steps + baseline", "orange", "orange_edge", 9.5, 7.5)
    ax.text(2.08, 2.25, "通信对象：\nverifiable_spec · evidence_refs\nexperiment_plan · metrics", ha="center", va="center", fontsize=8.2, color=COLORS["muted"], linespacing=1.5)

    x, w = 4.35, 5.2
    block(ax, x, 7.95, w, 0.72, "步骤 1：生成反事实场景", "failure mode / alternative outcome", "blue", "blue_edge")
    block(ax, x, 6.78, w, 0.72, "步骤 2：FALSIFY 过滤器", "falsifiable · evidence-backed · cheap_test", "mint", "mint_edge")
    diamond(ax, 6.95, 5.55, 3.3, 1.2, "是否可控？", "decision impact + failure mode")
    block(ax, x, 3.78, w, 0.78, "步骤 3A：约束注入实验设计", "control group / cheap test / risk note", "green", "green_edge")
    block(ax, x, 2.28, w, 0.78, "步骤 3B：阻断并补充证据", "proceed = false → HITL / literature refresh", "orange", "orange_edge")
    arrow(ax, (6.95, 7.95), (6.95, 7.5), color="#555555")
    arrow(ax, (6.95, 6.78), (6.95, 6.15), color="#555555")
    arrow(ax, (6.95, 4.95), (6.95, 4.56), "YES", COLORS["green_edge"], text_offset=(0.28, 0.0))
    arrow(ax, (8.6, 5.55), (10.0, 5.55), "NO", COLORS["red"], text_offset=(0, 0.18))
    arrow(ax, (10.0, 5.55), (10.0, 3.0), "", COLORS["red"])
    arrow(ax, (10.0, 3.0), (9.55, 3.0), "", COLORS["red"])
    arrow(ax, (3.6, 7.78), (x, 8.3), "input bundle", COLORS["blue_edge"], dashed=True, text_offset=(0, 0.16))
    arrow(ax, (3.6, 6.66), (x, 8.3), "evidence_refs", COLORS["mint_edge"], dashed=True, text_offset=(0, -0.16))
    arrow(ax, (3.6, 4.4), (x, 8.3), "plan / metrics", COLORS["orange_edge"], dashed=True, text_offset=(0, -0.35))

    panel(ax, 10.45, 5.3, 4.95, 3.2, "反事实控制面板", COLORS["lavender_edge"])
    bullets(ax, 10.75, 7.75, [
        "falsifiable：是否可证伪",
        "evidence_fact_ids：证据绑定",
        "cheap_test：低成本验证",
        "decision_impact：能否改变决策",
        "failure_predictions：失败模式",
    ], line_gap=0.43)
    panel(ax, 10.45, 1.2, 4.95, 3.35, "输出与通信", COLORS["gray_edge"])
    bullets(ax, 10.75, 3.82, [
        "proceed_to_iterative_experiment",
        "counterfactual_feedback_constraints",
        "control_group / risk_note",
        "高风险且不可控 → 阻断实验",
        "可控 → 注入 iterative_experiment",
    ], line_gap=0.46)
    arrow(ax, (10.45, 6.35), (9.55, 4.18), "scenario metadata", COLORS["lavender_edge"], dashed=True, text_offset=(0.18, 0.12))
    arrow(ax, (9.55, 4.18), (10.45, 2.7), "decision JSON", COLORS["green_edge"], dashed=True, text_offset=(0.12, 0.12))
    arrow(ax, (10.45, 2.2), (9.55, 2.65), "HITL / supplement", COLORS["orange_edge"], dashed=True, text_offset=(0, 0.18))
    save(fig, out_dir, "fig_innovation_4_counterfactual")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    configure_fonts()
    evidence_chain(args.output_dir)
    verdict_gate(args.output_dir)
    feedback_hub(args.output_dir)
    counterfactual(args.output_dir)
    print(f"Generated schematics in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
