"""赛道二 P2 总体思路图：分析对象 → 结果与边界。

风格对齐 generate_p6_architecture_figure.py / generate_p12_workflow_figure.py。
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
        "科研影响力分析总体思路：分析对象与目的 → 结果与边界",
        ha="center", va="center", fontsize=16.0, fontweight="bold", color=COLORS["ink"],
    )

    rounded_box(
        ax, 0.88, 8.18, 5.36, 0.72,
        "输入：论文 / 报告 PDF", "用户上传全文，或评分表系统生成器报告",
        "blue", "blue_edge", 11.0, 7.4,
    )
    rounded_box(
        ax, 6.48, 8.18, 3.04, 0.72,
        "Qwen 结构化判断", "须绑定证据来源字段",
        "purple", "purple_edge", 11.0, 7.4,
    )
    rounded_box(
        ax, 9.76, 8.18, 5.36, 0.72,
        "输出：评估结果 + 使用边界", "四维得分 / 因素 / 偏差 / 不确定性",
        "orange", "orange_edge", 11.0, 7.4,
    )

    ax.text(0.88, 7.88, "八步主链路（实线，蛇形往下）", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])

    st_w, st_h = 3.24, 1.08
    xs = [0.88, 4.44, 8.00, 11.56]
    y1, y2 = 6.50, 4.68
    stages = [
        (xs[0], y1, "1 分析对象与目的", "论文/报告；早期影响力参考", "blue", "blue_edge"),
        (xs[1], y1, "2 数据和资料获取", "PDF 全文 + OpenAlex 元数据", "mint", "mint_edge"),
        (xs[2], y1, "3 内容解析", "结构 / 内容 / 创新 / 质量信号", "mint", "mint_edge"),
        (xs[3], y1, "4 影响力判断", "四维 D1–D4 + 校准总分", "orange", "orange_edge"),
        (xs[3], y2, "5 主要因素解释", "关键因素与权重", "purple", "purple_edge"),
        (xs[2], y2, "6 偏差检查", "七类偏差 + 缓解建议", "gray", "gray_edge"),
        (xs[1], y2, "7 质量核验或人工反馈", "不确定性；人工复核入口", "green", "green_edge"),
        (xs[0], y2, "8 结果与边界", "六档评级；不替代人事决策", "orange", "orange_edge"),
    ]
    for x, y, title, subtitle, face, edge in stages:
        rounded_box(ax, x, y, st_w, st_h, title, subtitle, face, edge, 10.2, 7.0)

    mid1 = y1 + st_h / 2
    mid2 = y2 + st_h / 2
    for left, right in zip(xs[:-1], xs[1:]):
        arrow(ax, (left + st_w, mid1), (right, mid1), lw=1.35)
    arrow(ax, (xs[3] + st_w / 2, y1), (xs[3] + st_w / 2, y2 + st_h), lw=1.35)
    for right, left in zip(xs[::-1][:-1], xs[::-1][1:]):
        arrow(ax, (right, mid2), (left + st_w, mid2), lw=1.35)

    arrow(ax, (3.56, 8.18), (xs[0] + st_w / 2, y1 + st_h), COLORS["blue_edge"], "接收对象",
          dashed=True, text_offset=(-0.78, 0.02), curve=-0.04)
    arrow(ax, (8.00, 8.18), (xs[3] + st_w / 2, y1 + st_h), COLORS["purple_edge"], "四维判断",
          dashed=True, text_offset=(0.62, 0.04))

    ax.text(0.88, 4.38, "核验回流（虚线）：证据不足不硬给结论", ha="left", va="center",
            fontsize=7.6, color=COLORS["muted"])

    fb = [
        (0.88, "元数据 / 引用缺失", "回到 2 数据和资料获取，或标注不确定", "mint", "mint_edge"),
        (5.72, "文本解析失败或不完整", "回到 3 内容解析，不补造结构信号", "mint", "mint_edge"),
        (10.56, "偏差方向无法确认 / 证据冲突", "步骤 7 转人工复核，不输出硬结论", "green", "green_edge"),
    ]
    fb_w, fb_h, fb_y = 4.52, 1.18, 2.82
    for x, title, subtitle, face, edge in fb:
        rounded_box(ax, x, fb_y, fb_w, fb_h, title, subtitle, face, edge, 9.2, 7.0)

    arrow(ax, (3.14, fb_y + fb_h), (xs[1] + st_w / 2, y1), COLORS["mint_edge"], "回资料",
          dashed=True, text_offset=(-0.62, 0.02), lw=1.1)
    arrow(ax, (7.98, fb_y + fb_h), (xs[2] + st_w / 2, y1), COLORS["mint_edge"], "回解析",
          dashed=True, text_offset=(0.55, 0.02), lw=1.1)
    arrow(ax, (12.82, fb_y + fb_h), (xs[1] + st_w / 2, y2), COLORS["green_edge"], "交人复核",
          dashed=True, text_offset=(0.72, 0.0), lw=1.1)

    ax.add_patch(
        FancyBboxPatch(
            (0.88, 0.48), 14.24, 2.00,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS["gray"], edgecolor=COLORS["gray_edge"], linewidth=1.25,
        )
    )
    ax.text(8.00, 2.18, "Qwen、外部工具与人工分别在哪一步",
            ha="center", va="center", fontsize=10.6, fontweight="bold", color=COLORS["ink"])
    ax.text(
        1.12, 1.78,
        "外部工具（步骤 2–3）：PDF 解析抽全文与结构；OpenAlex 取元数据与引用网络；规则计算 1/3/5 年引用预测。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        1.12, 1.36,
        "Qwen（步骤 4–6）：qwen-max 做四维评分与校准；qwen-plus 写主要因素、偏差方向/证据/缓解，判断须回指元数据或文本字段。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        1.12, 0.94,
        "人工与边界（步骤 7–8）：复核可改解释与偏差确认；原始资料、规则计算、模型判断分开存档。"
        "结果含使用边界，不替代录用/职称/基金等人事决策。",
        ha="left", va="top", fontsize=8.4, color=COLORS["muted"],
    )
    ax.text(
        8.00, 0.62,
        "实线：对象往前走到结果与边界     虚线：核验失败回到资料 / 解析，或转人工     缺证据时标注不确定，不编造",
        ha="center", va="center", fontsize=7.3, color=COLORS["muted"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_track2_p2_overview.png"
    svg_path = OUT_DIR / "fig_aisci_track2_p2_overview.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
