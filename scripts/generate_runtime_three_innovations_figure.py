"""Generate a single AISci runtime overview with three innovation intervention layers."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_DIR = Path("output/innovation_schematics")

COLORS = {
    "ink": "#20252B",
    "muted": "#5E6873",
    "outer": "#87929E",
    "title": "#DCE7F5",
    "title_edge": "#8EA2B8",
    "blue": "#E6F2FA",
    "blue_edge": "#237FB3",
    "mint": "#E2F3EC",
    "mint_edge": "#249C74",
    "purple": "#EEEAF8",
    "purple_edge": "#775FA8",
    "orange": "#FFF0DC",
    "orange_edge": "#C97928",
    "green": "#EAF5D9",
    "green_edge": "#5C9E32",
    "gray": "#F5F6F7",
    "gray_edge": "#6D7781",
    "red": "#CE5A45",
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


def rounded_box(ax, x, y, w, h, title, subtitle="", face="gray", edge="gray_edge", title_size=10.5, subtitle_size=7.7):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=1.25,
        )
    )
    ax.text(x + w / 2, y + h * 0.60, title, ha="center", va="center", fontsize=title_size,
            fontweight="bold", color=COLORS["ink"])
    if subtitle:
        ax.text(x + w / 2, y + h * 0.28, subtitle, ha="center", va="center", fontsize=subtitle_size,
                color=COLORS["muted"])


def panel(ax, x, y, w, h, title, edge, title_color, body_lines, effect, face="gray"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor="#FFFFFF", edgecolor=COLORS[edge], linewidth=1.35,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (x, y + h - 0.52), w, 0.52,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=1.1,
        )
    )
    ax.text(x + w / 2, y + h - 0.26, title, ha="center", va="center", fontsize=10.6,
            fontweight="bold", color=COLORS[title_color])
    for index, line in enumerate(body_lines):
        ax.text(x + 0.24, y + h - 0.84 - index * 0.36, line, ha="left", va="top", fontsize=8.2,
                color=COLORS["muted"])
    ax.add_patch(
        FancyBboxPatch(
            (x + 0.18, y + 0.20), w - 0.36, 0.58,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=0.85,
        )
    )
    ax.text(x + w / 2, y + 0.49, effect, ha="center", va="center", fontsize=7.8,
            color=COLORS["ink"], fontweight="bold")


def arrow(ax, start, end, color="#56616B", label="", dashed=False, text_offset=(0, 0.12), curve=0.0, lw=1.25):
    linestyle = (0, (4, 3)) if dashed else "-"
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=12, linewidth=lw, linestyle=linestyle,
            color=color, connectionstyle=f"arc3,rad={curve}",
        )
    )
    if label:
        mid_x = (start[0] + end[0]) / 2 + text_offset[0]
        mid_y = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(mid_x, mid_y, label, ha="center", va="center", fontsize=7.0, color=color,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.0})


def chip(ax, x, y, text, face, edge):
    width = 0.17 * len(text) + 0.42
    ax.add_patch(
        FancyBboxPatch(
            (x, y), width, 0.31,
            boxstyle="round,pad=0.01,rounding_size=0.05",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=0.8,
        )
    )
    ax.text(x + width / 2, y + 0.155, text, ha="center", va="center", fontsize=6.7,
            color=COLORS["ink"])
    return width


def generate() -> None:
    configure_fonts()
    fig, ax = plt.subplots(figsize=(16, 10), dpi=240)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.add_patch(
        FancyBboxPatch(
            (0.25, 0.25), 15.5, 9.5,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="#FFFFFF", edgecolor=COLORS["outer"], linewidth=1.5,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.25, 9.16), 15.5, 0.59,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=COLORS["title"], edgecolor=COLORS["title_edge"], linewidth=1.15,
        )
    )
    ax.text(8, 9.46, "AISci 项目运行过程与三大核心创新作用位置", ha="center", va="center",
            fontsize=17, fontweight="bold", color=COLORS["ink"])

    # Innovation 3 controls the whole project rather than a single stage.
    rounded_box(
        ax, 0.88, 7.86, 14.24, 0.88,
        "创新三  “大家长”Agent：项目级质量评估与协调",
        "项目上下文（问题 / Fact / 假设版本 / 实验状态 / Gate / 反馈）  |  作用：记忆压缩、质量门禁、反馈路由、指定阶段重跑 / HITL",
        "purple", "purple_edge", 12.1, 8.0,
    )

    rounded_box(ax, 1.08, 6.95, 3.0, 0.50, "用户输入", "科学问题 / 目标约束", "blue", "blue_edge", 8.8, 7.0)
    rounded_box(ax, 5.05, 6.95, 3.0, 0.50, "外部证据", "论文、私有文献、数据集", "mint", "mint_edge", 8.8, 7.0)
    rounded_box(ax, 11.72, 6.95, 3.0, 0.50, "HITL 反馈", "导师审核 / 用户修改", "orange", "orange_edge", 8.8, 7.0)

    stages = [
        ("1  问题理解", "结构化研究问题", "blue", "blue_edge"),
        ("2  文献挖掘", "Fact + 来源片段", "blue", "blue_edge"),
        ("3  知识缺口", "识别空白与矛盾", "mint", "mint_edge"),
        ("4  假设生成", "候选假设 + fact_ids", "purple", "purple_edge"),
        ("5  假设评审", "新颖性 / 可行性 / L0 风险", "purple", "purple_edge"),
        ("6  迭代实验", "数据、脚本、沙箱", "orange", "orange_edge"),
        ("7  报告生成", "结构化报告 + 引用", "green", "green_edge"),
    ]
    x_positions = [1.03, 3.04, 5.05, 7.06, 9.07, 11.08, 13.09]
    width, y, height = 1.78, 5.55, 1.02
    for x, (title, subtitle, face, edge) in zip(x_positions, stages):
        rounded_box(ax, x, y, width, height, title, subtitle, face, edge, 9.6, 7.2)
    for left, right in zip(x_positions[:-1], x_positions[1:]):
        arrow(ax, (left + width, y + height / 2), (right, y + height / 2))

    arrow(ax, (2.58, 6.95), (1.92, y + height), COLORS["blue_edge"], "研究任务", dashed=True, text_offset=(-0.08, 0.14))
    arrow(ax, (6.55, 6.95), (3.93, y + height), COLORS["mint_edge"], "文献 / 数据", dashed=True, text_offset=(0, 0.14), curve=0.08)
    arrow(ax, (13.22, 6.95), (12.95, 6.57), COLORS["orange_edge"], "人工反馈", dashed=True, text_offset=(0.10, 0.12))

    # Manager observes quality events and routes feedback to the relevant earlier stage.
    arrow(ax, (9.96, y + height), (9.96, 7.86), COLORS["purple_edge"], "质量事件 / 版本", dashed=True, text_offset=(0.38, 0.0), lw=1.1)
    arrow(ax, (8.08, 7.86), (8.08, y + height), COLORS["purple_edge"], dashed=True, lw=1.1)
    arrow(ax, (13.22, 6.95), (13.22, 7.86), COLORS["orange_edge"], dashed=True, lw=1.1)
    arrow(ax, (11.97, y), (7.95, y), COLORS["purple_edge"], "FAIL → 反馈重跑", dashed=True, text_offset=(0, -0.26), curve=-0.22, lw=1.2)

    # Innovation 1: Facts form a governed evidence loop before and after hypothesis generation.
    panel(
        ax, 0.82, 1.04, 4.55, 3.82,
        "创新一  多轮证据链迭代机制", "blue_edge", "blue_edge",
        [
            "① 文献事实提取：Fact 绑定来源 chunk_id",
            "② 支持证据与反证检索：主动检查矛盾",
            "③ Fact 白名单：仅允许有效 fact_id 进入推理",
            "④ 证据不足 / 实验新证据：补文献并更新白名单",
        ],
        "作用：声明—事实可溯源 · 引用受约束 · 假设可复核",
        "blue",
    )
    arrow(ax, (3.93, y), (3.93, 4.86), COLORS["blue_edge"], "Fact", dashed=True, text_offset=(0.22, 0.0), lw=1.1)
    arrow(ax, (5.24, 4.42), (7.95, y), COLORS["blue_edge"], "", dashed=True, curve=0.12, lw=1.1)
    ax.text(2.95, 2.08, "证据不足 / 新实验结果 → 补文献更新 Fact", ha="center", va="center", fontsize=7.2,
            color=COLORS["blue_edge"], bbox={"facecolor": "#F5FAFE", "edgecolor": COLORS["blue_edge"], "boxstyle": "round,pad=0.20"})

    # Innovation 2: two filters turn evidence and executability into decisions.
    panel(
        ax, 5.72, 1.04, 4.60, 3.82,
        "创新二  知识库对齐 + 小样本预检", "orange_edge", "orange_edge",
        [
            "G1 知识库对齐：候选假设必须绑定有效 Fact",
            "    无事实依据 / 无法对齐 → 驳回并重新生成",
            "G2 小样本预检：元数据匹配 → 测试数据 → 脚本试跑",
            "    脚本失败 / 结果异常 → 阻断正式实验并反馈",
        ],
        "作用：过滤无据假设 · 前置排除不可执行方案 · 节约算力",
        "orange",
    )
    arrow(ax, (8.95, y), (8.95, 4.86), COLORS["orange_edge"], "G1", dashed=True, text_offset=(0.22, 0.0), lw=1.1)
    arrow(ax, (11.97, y), (10.15, 4.86), COLORS["orange_edge"], "G2", dashed=True, text_offset=(0.12, 0.06), curve=0.08, lw=1.1)

    # The audit trail turns the three intervention layers into inspectable project evidence.
    panel(
        ax, 10.67, 1.04, 4.48, 3.82,
        "可审计运行产物", "gray_edge", "gray_edge",
        [
            "项目状态：输入 / 输出 / Prompt / 模型参数 / Token / 耗时",
            "证据状态：fact_id、来源、支持与反证、引用完整性",
            "质量状态：PASS / FAIL、失败原因、Gate 趋势、HITL",
            "版本状态：重跑目标、反馈来源、假设与实验迭代记录",
        ],
        "最终输出：科研报告 + 引用链 + 审计链（JSONL）",
        "gray",
    )
    arrow(ax, (13.98, y), (13.98, 4.86), COLORS["gray_edge"], "报告 + 审计", dashed=True, text_offset=(0.25, 0.0), lw=1.1)

    ax.text(8, 0.52, "实线：主运行链路   虚线：创新机制注入、反馈或审计数据流", ha="center", va="center",
            fontsize=7.4, color=COLORS["muted"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_runtime_three_innovations.png"
    svg_path = OUT_DIR / "fig_aisci_runtime_three_innovations.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
