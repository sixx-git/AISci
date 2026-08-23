"""赛道二 P6 实际架构图：分析对象 / 原始资料 / 提取信息 / 影响力结果 /
因素解释 / 偏差提示 / 质量反馈，以及 Qwen、外部工具与人工位置。

风格对齐 generate_p6_architecture_figure.py / generate_track2_p2_overview_figure.py。
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
                title_size=10.5, subtitle_size=7.7):
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
            (x, y + h - 0.48), w, 0.48,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=1.1,
        )
    )
    ax.text(
        x + w / 2, y + h - 0.24, title,
        ha="center", va="center", fontsize=10.4, fontweight="bold", color=COLORS[title_color],
    )
    for index, line in enumerate(body_lines):
        ax.text(
            x + 0.22, y + h - 0.76 - index * 0.34, line,
            ha="left", va="top", fontsize=8.0, color=COLORS["muted"],
        )
    ax.add_patch(
        FancyBboxPatch(
            (x + 0.16, y + 0.16), w - 0.32, 0.50,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=COLORS[face], edgecolor=COLORS[edge], linewidth=0.85,
        )
    )
    ax.text(
        x + w / 2, y + 0.41, effect,
        ha="center", va="center", fontsize=7.6, color=COLORS["ink"], fontweight="bold",
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
        "科研影响力分析实际架构：对象 · 资料 · 提取 · 结果 · 解释 · 偏差 · 反馈",
        ha="center", va="center", fontsize=15.4, fontweight="bold", color=COLORS["ink"],
    )

    rounded_box(
        ax, 0.88, 8.22, 4.48, 0.68,
        "人工参与", "上传 PDF · 复核入口 · 修改解释/偏差",
        "orange", "orange_edge", 11.0, 7.5,
    )
    rounded_box(
        ax, 5.76, 8.22, 4.48, 0.68,
        "Qwen（阿里云百炼）", "qwen-max 评分 · qwen-plus 解释",
        "purple", "purple_edge", 11.0, 7.5,
    )
    rounded_box(
        ax, 10.64, 8.22, 4.48, 0.68,
        "外部工具", "PDF 解析 · OpenAlex · 规则预测",
        "mint", "mint_edge", 11.0, 7.5,
    )

    ax.text(0.88, 7.98, "数据对象主链路（实线）", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])
    artifacts = [
        ("① 分析对象", "论文/报告 PDF", "blue", "blue_edge"),
        ("② 原始资料", "全文 + OpenAlex", "mint", "mint_edge"),
        ("③ 提取信息", "文本特征 + 引用指标", "mint", "mint_edge"),
        ("④ 影响力结果", "D1–D4 / 校准总分", "orange", "orange_edge"),
        ("⑤ 因素解释", "关键因素与权重", "purple", "purple_edge"),
        ("⑥ 偏差提示", "方向 / 量级 / 缓解", "gray", "gray_edge"),
        ("⑦ 质量反馈", "不确定 / 复核 / 降级", "green", "green_edge"),
    ]
    art_w, art_h, art_y = 1.78, 0.98, 6.82
    art_xs = [0.88, 2.92, 4.96, 7.00, 9.04, 11.08, 13.12]
    for x, (title, subtitle, face, edge) in zip(art_xs, artifacts):
        rounded_box(ax, x, art_y, art_w, art_h, title, subtitle, face, edge, 10.2, 6.9)
    for left, right in zip(art_xs[:-1], art_xs[1:]):
        arrow(ax, (left + art_w, art_y + art_h / 2), (right, art_y + art_h / 2), lw=1.45)

    arrow(ax, (3.12, 8.22), (1.77, art_y + art_h), COLORS["orange_edge"], "提交",
          dashed=True, text_offset=(-0.42, 0.0), curve=-0.05)
    arrow(ax, (8.00, 8.22), (7.89, art_y + art_h), COLORS["purple_edge"], "评分 / 解释",
          dashed=True, text_offset=(0.70, 0.0))
    arrow(ax, (12.20, 8.22), (3.81, art_y + art_h), COLORS["mint_edge"], "解析 / 取数",
          dashed=True, text_offset=(-1.05, 0.08), curve=0.10)
    arrow(ax, (13.70, 8.22), (5.85, art_y + art_h), COLORS["mint_edge"], "规则特征",
          dashed=True, text_offset=(0.58, 0.0), curve=-0.04)
    arrow(ax, (4.20, 8.22), (14.01, art_y + art_h), COLORS["orange_edge"], "复核",
          dashed=True, text_offset=(2.35, 0.10), curve=0.12)

    ax.text(0.88, 6.62, "对应处理模块", ha="left", va="center", fontsize=7.6, color=COLORS["muted"])
    stages = [
        ("PDF 解析", "全文与结构抽取", "blue", "blue_edge"),
        ("OpenAlex", "元数据 / 引用网络", "mint", "mint_edge"),
        ("规则计算", "规模/速度/百分位", "mint", "mint_edge"),
        ("四维评估", "qwen-max + 校准", "orange", "orange_edge"),
        ("因素生成", "qwen-plus 权重", "purple", "purple_edge"),
        ("偏差分析", "qwen-plus 七类", "gray", "gray_edge"),
        ("展示 / HITL", "雷达图 · JSON · 复核", "green", "green_edge"),
    ]
    st_w, st_h, st_y = 1.78, 0.88, 5.52
    st_xs = art_xs
    for x, (title, subtitle, face, edge) in zip(st_xs, stages):
        rounded_box(ax, x, st_y, st_w, st_h, title, subtitle, face, edge, 9.1, 6.9)
    for left, right in zip(st_xs[:-1], st_xs[1:]):
        arrow(ax, (left + st_w, st_y + st_h / 2), (right, st_y + st_h / 2))

    for x0, edge in zip(art_xs, [a[3] for a in artifacts]):
        arrow(ax, (x0 + art_w / 2, art_y), (x0 + st_w / 2, st_y + st_h), COLORS[edge], dashed=True, lw=1.0)

    fb_y, fb_h = 4.52, 0.66
    rounded_box(
        ax, 0.88, fb_y, 14.24, fb_h,
        "质量反馈回流（失败则降级标注，必要时转人工，不编造）",
        "引用/元数据缺失 → 回 OpenAlex 或标不确定     解析不完整 → 回 PDF 解析     无法回溯 / 偏差方向不明 → HITL",
        "green", "green_edge", 10.4, 7.5,
    )
    arrow(ax, (3.81, fb_y + fb_h), (3.81, st_y), COLORS["mint_edge"], "回取数",
          dashed=True, text_offset=(-0.48, 0.0), lw=1.05)
    arrow(ax, (1.77, fb_y + fb_h), (1.77, st_y), COLORS["blue_edge"], "回解析",
          dashed=True, text_offset=(-0.50, 0.0), lw=1.05)
    arrow(ax, (14.01, fb_y + fb_h), (14.01, st_y), COLORS["green_edge"], "交人",
          dashed=True, text_offset=(-0.38, 0.0), lw=1.05)

    panel(
        ax, 0.82, 0.58, 4.55, 3.38,
        "Qwen 在系统中的位置",
        "purple_edge", "purple_edge",
        [
            "qwen-max：四维评分（D1 文本质量 / D2 声誉",
            "网络 / D3 未来影响 / D4 偏差公平）与校准",
            "qwen-plus：主要因素、权重，以及七类偏差",
            "（方向 / 量级 / 缓解），须回指证据字段",
            "不检索、不跑 OpenAlex、不解析 PDF",
        ],
        "作用：结构化判断与解释；证据由工具提供",
        "purple",
    )
    panel(
        ax, 5.72, 0.58, 4.60, 3.38,
        "外部工具在系统中的位置",
        "mint_edge", "mint_edge",
        [
            "PDF 解析：抽取全文、结构、图表与参考文献",
            "OpenAlex：标题/作者/期刊/DOI/引用网络",
            "规则计算：引用规模/速度/领域百分位",
            "生命周期模型：1/3/5 年引用预测",
            "前端：雷达图、预测曲线、偏差报告、JSON",
        ],
        "作用：取数、特征与展示；结果回注评估上下文",
        "mint",
    )
    panel(
        ax, 10.67, 0.58, 4.48, 3.38,
        "人工参与在系统中的位置",
        "orange_edge", "orange_edge",
        [
            "入口：上传论文/报告 PDF，可选附评分文件",
            "复核：修改因素解释与偏差方向确认",
            "触发：引用缺失、无法回溯、证据冲突、",
            "涉及录用/职称/基金等人事含义时转人工",
            "存档：原始资料、规则、模型、人工意见分开",
        ],
        "作用：把关不能自动判定的结论，并留下复核记录",
        "orange",
    )

    ax.text(
        8, 0.48,
        "实线：分析对象 → 原始资料 → 提取信息 → 影响力结果 → 因素解释 → 偏差提示 → 质量反馈     虚线：角色注入、模块对应与回流路径",
        ha="center", va="center", fontsize=7.3, color=COLORS["muted"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_track2_p6_architecture.png"
    svg_path = OUT_DIR / "fig_aisci_track2_p6_architecture.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
