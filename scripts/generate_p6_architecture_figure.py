"""P6 实际架构图：科学问题 / 证据 / 候选假设 / 研究计划 / 反馈，以及 Qwen、外部工具与人工位置。

风格对齐 scripts/generate_runtime_three_innovations_figure.py。
"""

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


def rounded_box(
    ax,
    x,
    y,
    w,
    h,
    title,
    subtitle="",
    face="gray",
    edge="gray_edge",
    title_size=10.5,
    subtitle_size=7.7,
):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face],
            edgecolor=COLORS[edge],
            linewidth=1.25,
        )
    )
    ax.text(
        x + w / 2,
        y + h * (0.62 if subtitle else 0.50),
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="bold",
        color=COLORS["ink"],
    )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.28,
            subtitle,
            ha="center",
            va="center",
            fontsize=subtitle_size,
            color=COLORS["muted"],
        )


def panel(ax, x, y, w, h, title, edge, title_color, body_lines, effect, face="gray"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor="#FFFFFF",
            edgecolor=COLORS[edge],
            linewidth=1.35,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (x, y + h - 0.48),
            w,
            0.48,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face],
            edgecolor=COLORS[edge],
            linewidth=1.1,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.24,
        title,
        ha="center",
        va="center",
        fontsize=10.4,
        fontweight="bold",
        color=COLORS[title_color],
    )
    for index, line in enumerate(body_lines):
        ax.text(
            x + 0.22,
            y + h - 0.76 - index * 0.34,
            line,
            ha="left",
            va="top",
            fontsize=8.0,
            color=COLORS["muted"],
        )
    ax.add_patch(
        FancyBboxPatch(
            (x + 0.16, y + 0.16),
            w - 0.32,
            0.50,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=COLORS[face],
            edgecolor=COLORS[edge],
            linewidth=0.85,
        )
    )
    ax.text(
        x + w / 2,
        y + 0.41,
        effect,
        ha="center",
        va="center",
        fontsize=7.6,
        color=COLORS["ink"],
        fontweight="bold",
    )


def arrow(ax, start, end, color="#56616B", label="", dashed=False, text_offset=(0, 0.12), curve=0.0, lw=1.25):
    linestyle = (0, (4, 3)) if dashed else "-"
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=lw,
            linestyle=linestyle,
            color=color,
            connectionstyle=f"arc3,rad={curve}",
        )
    )
    if label:
        mid_x = (start[0] + end[0]) / 2 + text_offset[0]
        mid_y = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(
            mid_x,
            mid_y,
            label,
            ha="center",
            va="center",
            fontsize=7.0,
            color=color,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.0},
        )


def generate() -> None:
    configure_fonts()
    fig, ax = plt.subplots(figsize=(16, 10), dpi=240)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.add_patch(
        FancyBboxPatch(
            (0.25, 0.25),
            15.5,
            9.5,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="#FFFFFF",
            edgecolor=COLORS["outer"],
            linewidth=1.5,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.25, 9.16),
            15.5,
            0.59,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=COLORS["title"],
            edgecolor=COLORS["title_edge"],
            linewidth=1.15,
        )
    )
    ax.text(
        8,
        9.46,
        "AISci 实际架构：科学问题 · 证据 · 候选假设 · 研究计划 · 反馈",
        ha="center",
        va="center",
        fontsize=16.2,
        fontweight="bold",
        color=COLORS["ink"],
    )

    # 三类参与者（P6 要求标明 Qwen / 外部工具 / 人工位置）
    rounded_box(
        ax, 0.88, 8.22, 4.48, 0.68,
        "人工参与", "提交问题 · HITL Gate · 约束修订",
        "orange", "orange_edge", 11.0, 7.5,
    )
    rounded_box(
        ax, 5.76, 8.22, 4.48, 0.68,
        "Qwen（阿里云百炼）", "qwen-max / qwen-plus · 结构化 JSON",
        "purple", "purple_edge", 11.0, 7.5,
    )
    rounded_box(
        ax, 10.64, 8.22, 4.48, 0.68,
        "外部工具", "arXiv · PDF 解析 · 向量检索 · 沙箱",
        "mint", "mint_edge", 11.0, 7.5,
    )

    ax.text(0.88, 7.98, "数据对象主链路（实线）", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])
    artifacts = [
        ("① 科学问题", "用户输入或 Science 125", "blue", "blue_edge"),
        ("② 证据", "Fact 白名单 + chunk_id", "mint", "mint_edge"),
        ("③ 候选假设", "绑定有效 fact_id", "purple", "purple_edge"),
        ("④ 研究计划", "方案 / 脚本 / 沙箱结果", "orange", "orange_edge"),
        ("⑤ 反馈修订", "自动回流 + 人工约束", "green", "green_edge"),
    ]
    art_w, art_h, art_y = 2.52, 0.98, 6.82
    art_xs = [0.88, 3.72, 6.56, 9.40, 12.24]
    for x, (title, subtitle, face, edge) in zip(art_xs, artifacts):
        rounded_box(ax, x, art_y, art_w, art_h, title, subtitle, face, edge, 11.0, 7.3)
    for left, right in zip(art_xs[:-1], art_xs[1:]):
        arrow(ax, (left + art_w, art_y + art_h / 2), (right, art_y + art_h / 2), lw=1.45)

    # 角色注入：人工→科学问题；Qwen→候选假设；工具→证据与研究计划
    arrow(ax, (3.12, 8.22), (2.14, art_y + art_h), COLORS["orange_edge"], "提交 / 审核",
          dashed=True, text_offset=(-0.62, 0.0), curve=-0.05)
    arrow(ax, (8.00, 8.22), (7.82, art_y + art_h), COLORS["purple_edge"], "推理 / 抽取",
          dashed=True, text_offset=(0.58, 0.0))
    arrow(ax, (12.20, 8.22), (4.98, art_y + art_h), COLORS["mint_edge"], "检索 / 解析",
          dashed=True, text_offset=(-1.15, 0.08), curve=0.10)
    arrow(ax, (13.70, 8.22), (10.66, art_y + art_h), COLORS["mint_edge"], "沙箱执行",
          dashed=True, text_offset=(0.62, 0.0), curve=-0.04)

    ax.text(0.88, 6.62, "对应智能体阶段", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])
    stages = [
        ("1 问题理解", "三维拆解", "blue", "blue_edge"),
        ("2 文献挖掘", "Fact 抽取", "mint", "mint_edge"),
        ("3 知识缺口", "空白与矛盾", "mint", "mint_edge"),
        ("4 假设生成", "候选 + 依据", "purple", "purple_edge"),
        ("5 假设评审", "对齐 / 新颖性", "purple", "purple_edge"),
        ("6 迭代实验", "计划与验证", "orange", "orange_edge"),
        ("7 报告生成", "结构化报告", "green", "green_edge"),
    ]
    st_w, st_h, st_y = 1.78, 0.88, 5.52
    st_xs = [1.03, 3.04, 5.05, 7.06, 9.07, 11.08, 13.09]
    for x, (title, subtitle, face, edge) in zip(st_xs, stages):
        rounded_box(ax, x, st_y, st_w, st_h, title, subtitle, face, edge, 9.1, 6.9)
    for left, right in zip(st_xs[:-1], st_xs[1:]):
        arrow(ax, (left + st_w, st_y + st_h / 2), (right, st_y + st_h / 2))

    # 数据对象落到对应阶段（短虚线，不打标签）
    links = [
        (2.14, 1.92, "blue_edge"),
        (4.98, 3.93, "mint_edge"),
        (4.98, 5.94, "mint_edge"),
        (7.82, 7.95, "purple_edge"),
        (7.82, 9.96, "purple_edge"),
        (10.66, 11.97, "orange_edge"),
        (13.50, 13.98, "green_edge"),
    ]
    for x0, x1, edge in links:
        arrow(ax, (x0, art_y), (x1, st_y + st_h), COLORS[edge], dashed=True, lw=1.0)

    # 反馈回流条：把闭环方向集中标清，避免长弧线压字
    fb_y, fb_h = 4.52, 0.66
    rounded_box(
        ax, 0.88, fb_y, 14.24, fb_h,
        "反馈回流（回注上一环节，形成技术闭环）",
        "证据不足 → 补文献重跑     评审不通过 → 修订假设     脚本失败 → 重设计再运行     人工意见 → 全局约束池",
        "green", "green_edge", 10.4, 7.5,
    )
    arrow(ax, (3.93, fb_y + fb_h), (3.93, st_y), COLORS["mint_edge"], "补文献", dashed=True,
          text_offset=(-0.50, 0.0), lw=1.05)
    arrow(ax, (7.95, fb_y + fb_h), (7.95, st_y), COLORS["purple_edge"], "改假设", dashed=True,
          text_offset=(-0.50, 0.0), lw=1.05)
    arrow(ax, (11.97, fb_y + fb_h), (11.97, st_y), COLORS["orange_edge"], "改脚本", dashed=True,
          text_offset=(-0.50, 0.0), lw=1.05)

    # 三类参与者在系统中的具体位置
    panel(
        ax,
        0.82,
        0.58,
        4.55,
        3.38,
        "Qwen 在系统中的位置",
        "purple_edge",
        "purple_edge",
        [
            "问题理解 / 知识缺口：结构化拆解与缺口分析",
            "文献挖掘：从检索片段抽取可溯源 Fact",
            "假设生成与评审：候选生成、集成评审、门禁",
            "实验分析与报告：方案、结果解读、12 字段报告",
            "Coordinator：质量判定、反馈路由、指定重跑",
        ],
        "作用：推理与结构化输出；不直接检索或执行代码",
        "purple",
    )
    panel(
        ax,
        5.72,
        0.58,
        4.60,
        3.38,
        "外部工具在系统中的位置",
        "mint_edge",
        "mint_edge",
        [
            "文献：arXiv 检索、PDF 解析、向量 RAG",
            "证据：Fact 绑定 source_chunk_id 进入白名单",
            "实验：沙箱执行脚本，产出指标与可视化",
            "审计：阶段 JSON、审计链、报告 PDF",
            "受版权限制的原文不直接切片下载，仅供模型辅助",
        ],
        "作用：检索、解析、执行与落库；结果回注上下文",
        "mint",
    )
    panel(
        ax,
        10.67,
        0.58,
        4.48,
        3.38,
        "人工参与在系统中的位置",
        "orange_edge",
        "orange_edge",
        [
            "入口：提交科学问题、目标与全局约束",
            "HITL Gate：可行性评估后暂停，进入迭代实验页",
            "实验页：确认方案、数据、脚本后启动沙箱",
            "反馈：审核意见写入约束池，注入后续轮次",
            "复核：任意阶段重跑、审计链与版本对比",
        ],
        "作用：把关不可自动判定的选择，并驱动修订闭环",
        "orange",
    )

    ax.text(
        8,
        0.48,
        "实线：科学问题 → 证据 → 候选假设 → 研究计划 → 反馈修订     虚线：角色注入、阶段对应与回流路径",
        ha="center",
        va="center",
        fontsize=7.3,
        color=COLORS["muted"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_p6_architecture.png"
    svg_path = OUT_DIR / "fig_aisci_p6_architecture.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
