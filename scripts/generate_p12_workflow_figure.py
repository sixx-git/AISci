"""P12 完整运行流程图：接收科学问题 → 候选假设与研究计划，并标明反馈回到哪一环。

风格对齐 generate_p6_architecture_figure.py / generate_p7_context_structure_figure.py。
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


def rounded_box(ax, x, y, w, h, title, subtitle="", face="gray", edge="gray_edge",
                title_size=10.5, subtitle_size=7.3):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=1.25,
        )
    )
    ax.text(
        x + w / 2, y + h * (0.62 if subtitle else 0.50), title,
        ha="center", va="center", fontsize=title_size, fontweight="bold", color=COLORS["ink"],
    )
    if subtitle:
        ax.text(
            x + w / 2, y + h * 0.28, subtitle,
            ha="center", va="center", fontsize=subtitle_size, color=COLORS["muted"],
        )


def arrow(ax, start, end, color="#56616B", label="", dashed=False, text_offset=(0, 0.12), curve=0.0, lw=1.25):
    linestyle = (0, (4, 3)) if dashed else "-"
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=12, linewidth=lw,
            linestyle=linestyle, color=color, connectionstyle=f"arc3,rad={curve}",
        )
    )
    if label:
        mid_x = (start[0] + end[0]) / 2 + text_offset[0]
        mid_y = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(
            mid_x, mid_y, label, ha="center", va="center", fontsize=7.0, color=color,
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
    ax.text(
        8, 9.46,
        "AISci 一次完整运行：接收科学问题 → 候选假设与研究计划",
        ha="center", va="center", fontsize=16.0, fontweight="bold", color=COLORS["ink"],
    )

    rounded_box(ax, 0.88, 8.18, 5.36, 0.72, "输入：科学问题原文", "用户提交 / Science 125 题干+背景",
                "blue", "blue_edge", 11.0, 7.4)
    rounded_box(ax, 9.76, 8.18, 5.36, 0.72, "输出：候选假设 + 研究计划", "含入选/未入选理由；计划可执行或记为不可执行",
                "orange", "orange_edge", 11.0, 7.4)
    rounded_box(ax, 6.48, 8.18, 3.04, 0.72, "大家长审核", "启动或终止证据链",
                "purple", "purple_edge", 11.0, 7.4)

    ax.text(0.88, 7.88, "七阶段主链路（实线）", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])
    stages = [
        ("1 问题理解", "对象 / 变量 / 边界", "blue", "blue_edge"),
        ("2 文献挖掘", "Fact 白名单 + 反证", "mint", "mint_edge"),
        ("3 知识缺口", "空白与矛盾", "mint", "mint_edge"),
        ("4 假设生成", "多候选 + fact_id", "purple", "purple_edge"),
        ("5 假设评审", "筛选与入选理由", "purple", "purple_edge"),
        ("6 迭代实验", "计划 / 预检 / 沙箱", "orange", "orange_edge"),
        ("7 报告生成", "结构化报告", "green", "green_edge"),
    ]
    st_w, st_h, st_y = 1.78, 1.02, 6.58
    st_xs = [0.88, 2.92, 4.96, 7.00, 9.04, 11.08, 13.12]
    for x, (title, subtitle, face, edge) in zip(st_xs, stages):
        rounded_box(ax, x, st_y, st_w, st_h, title, subtitle, face, edge, 9.0, 6.8)
    for left, right in zip(st_xs[:-1], st_xs[1:]):
        arrow(ax, (left + st_w, st_y + st_h / 2), (right, st_y + st_h / 2), lw=1.35)

    arrow(ax, (3.56, 8.18), (1.77, st_y + st_h), COLORS["blue_edge"], "接收题目",
          dashed=True, text_offset=(-0.72, 0.0), curve=-0.04)
    arrow(ax, (8.00, 8.18), (9.93, st_y + st_h), COLORS["purple_edge"], "阶段审核",
          dashed=True, text_offset=(0.55, 0.04))
    arrow(ax, (12.44, 8.18), (13.99, st_y + st_h), COLORS["orange_edge"], "交出产物",
          dashed=True, text_offset=(0.62, 0.0), curve=-0.04)

    ax.text(0.88, 6.28, "反馈回到哪一环（虚线，提交模板 P12 必标）", ha="left", va="center",
            fontsize=7.6, color=COLORS["muted"])

    fb = [
        (0.88, "证据不足 / 反证未完成", "回到 2 文献挖掘，重建白名单", "mint", "mint_edge"),
        (4.80, "无法对齐 / 不可证伪", "回到 4–5 假设，修订或淘汰", "purple", "purple_edge"),
        (8.72, "计划空泛或脚本跑不通", "回到 6 实验，预检后重设计", "orange", "orange_edge"),
        (12.64, "计划当前做不了", "大家长终止当轮，交 HITL", "green", "green_edge"),
    ]
    fb_w, fb_h, fb_y = 3.48, 1.22, 4.58
    for x, title, subtitle, face, edge in fb:
        rounded_box(ax, x, fb_y, fb_w, fb_h, title, subtitle, face, edge, 9.2, 7.0)

    arrow(ax, (2.62, fb_y + fb_h), (3.81, st_y), COLORS["mint_edge"], "回文献",
          dashed=True, text_offset=(-0.58, 0.0), lw=1.1)
    arrow(ax, (6.54, fb_y + fb_h), (7.89, st_y), COLORS["purple_edge"], "回假设",
          dashed=True, text_offset=(-0.52, 0.0), lw=1.1)
    arrow(ax, (10.46, fb_y + fb_h), (11.97, st_y), COLORS["orange_edge"], "回实验",
          dashed=True, text_offset=(-0.50, 0.0), lw=1.1)
    arrow(ax, (14.38, fb_y + fb_h), (8.00, 8.18), COLORS["green_edge"], "交人后再启动",
          dashed=True, text_offset=(1.15, 0.18), curve=0.18, lw=1.1)

    ax.add_patch(
        FancyBboxPatch(
            (0.88, 0.52), 14.24, 3.52,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS["gray"], edgecolor=COLORS["gray_edge"], linewidth=1.25,
        )
    )
    ax.text(8.00, 3.68, "sjtu_q_087 一次真实路径（说明反馈回到哪一环，不是装饰）",
            ha="center", va="center", fontsize=10.6, fontweight="bold", color=COLORS["ink"])
    ax.text(
        1.12, 3.22,
        "第一轮：接收口号题「人工智能能否取代医生？」→ 七阶段跑完 → 入选 H-03，评审 Accept 7.04。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        1.12, 2.72,
        "大家长在假设评审后终止当轮（HITL），没有把万例前瞻改写成已可执行。Pipeline 实验阶段仍为 PENDING。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        1.12, 2.22,
        "反馈回到的环节：人工约束从 2 文献挖掘起重跑（打开缺口补搜），而不是点「证据链迭代」覆盖第一轮冻结件。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        1.12, 1.72,
        "第二轮输出新 H-01（公开影像上的不确定性门控）；第一轮 H-03 与 RSNA 烟雾测试指标保持原样，旧数字不能贴到新假设上。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        8.00, 0.88,
        "实线：题目往前走到假设与计划     虚线：反馈回到文献 / 假设 / 实验 / 大家长     上一轮已审核输出不得被下一轮覆盖",
        ha="center", va="center", fontsize=7.3, color=COLORS["muted"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_p12_workflow.png"
    svg_path = OUT_DIR / "fig_aisci_p12_workflow.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
