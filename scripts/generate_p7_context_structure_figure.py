"""P7 上下文结构示意：科学问题 / 已有证据 / 反对证据 / 关键约束 / 历史结果 / 反馈如何进入 Qwen。

风格对齐 scripts/generate_runtime_three_innovations_figure.py 与 generate_p6_architecture_figure.py。
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
                title_size=10.5, subtitle_size=7.4):
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
        ax.text(
            (start[0] + end[0]) / 2 + text_offset[0],
            (start[1] + end[1]) / 2 + text_offset[1],
            label, ha="center", va="center", fontsize=7.0, color=color,
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
        "AISci 上下文结构：六通道如何进入 Qwen",
        ha="center", va="center", fontsize=16.2, fontweight="bold", color=COLORS["ink"],
    )

    ax.text(0.88, 8.98, "一次生成前的六类输入（提交模板 P7）", ha="left", va="center",
            fontsize=7.6, color=COLORS["muted"])
    channels = [
        ("科学问题", "research_question", "blue", "blue_edge"),
        ("已有证据", "核心白名单 fact_id", "mint", "mint_edge"),
        ("反对证据", "反证 / 矛盾 / 弱点", "orange", "orange_edge"),
        ("关键约束", "项目 + 全局约束池", "purple", "purple_edge"),
        ("历史结果", "审计摘要 / Gate", "gray", "gray_edge"),
        ("反馈信息", "HITL / 人工意见", "green", "green_edge"),
    ]
    ch_w, ch_h, ch_y = 2.20, 0.92, 7.88
    ch_xs = [0.88 + i * 2.38 for i in range(6)]
    for x, (title, subtitle, face, edge) in zip(ch_xs, channels):
        rounded_box(ax, x, ch_y, ch_w, ch_h, title, subtitle, face, edge, 10.4, 7.2)

    # 打包层
    pack_y, pack_h = 6.72, 0.78
    rounded_box(
        ax, 0.88, pack_y, 14.24, pack_h,
        "上下文打包（写入 user 消息，不是六段独立调用）",
        "阶段 Prompt  +  formatted_facts / available_fact_ids  +  formatted_constraints  +  上轮输出摘要  +  JSON Schema",
        "purple", "purple_edge", 11.0, 7.5,
    )
    for x in ch_xs:
        arrow(ax, (x + ch_w / 2, ch_y), (x + ch_w / 2, pack_y + pack_h), COLORS["purple_edge"], dashed=True, lw=1.0)

    # 一次真实调用的消息结构
    call_x, call_y, call_w, call_h = 0.88, 4.42, 14.24, 2.08
    ax.add_patch(
        FancyBboxPatch(
            (call_x, call_y), call_w, call_h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor="#FFFFFF", edgecolor=COLORS["purple_edge"], linewidth=1.35,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (call_x, call_y + call_h - 0.46), call_w, 0.46,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=COLORS["purple"], edgecolor=COLORS["purple_edge"], linewidth=1.1,
        )
    )
    ax.text(
        8, call_y + call_h - 0.23,
        "一次 Qwen 调用（qwen_structured_chat → 阿里云百炼 DashScope）",
        ha="center", va="center", fontsize=10.6, fontweight="bold", color=COLORS["purple_edge"],
    )

    slots = [
        ("system", "阶段 Prompt", "引用只能使用白名单", "fact_id；输出须为 JSON"),
        ("user · 问题", "科学问题", "研究问题原文", "写入各阶段提示词"),
        ("user · 证据", "已有 / 反对", "核心 Fact 可引用", "反证与辅助事实不升格"),
        ("user · 约束", "关键约束", "项目约束 + 全局约束池", "含人工反馈转换项"),
        ("user · 记忆", "历史 / 反馈", "审计摘要 / 上轮 Gate", "HITL 意见注入后续轮"),
    ]
    slot_w = 2.52
    slot_xs = [1.10 + i * 2.76 for i in range(5)]
    for x, (tag, title, l1, l2) in zip(slot_xs, slots):
        ax.add_patch(
            FancyBboxPatch(
                (x, call_y + 0.18), slot_w, 1.28,
                boxstyle="round,pad=0.02,rounding_size=0.04",
                facecolor=COLORS["gray"], edgecolor=COLORS["gray_edge"], linewidth=0.9,
            )
        )
        ax.text(x + slot_w / 2, call_y + 1.22, tag, ha="center", va="center",
                fontsize=6.8, color=COLORS["purple_edge"], fontweight="bold")
        ax.text(x + slot_w / 2, call_y + 0.92, title, ha="center", va="center",
                fontsize=8.6, color=COLORS["ink"], fontweight="bold")
        ax.text(x + slot_w / 2, call_y + 0.54, l1, ha="center", va="center", fontsize=6.7, color=COLORS["muted"])
        ax.text(x + slot_w / 2, call_y + 0.34, l2, ha="center", va="center", fontsize=6.7, color=COLORS["muted"])

    arrow(ax, (8, pack_y), (8, call_y + call_h), COLORS["purple_edge"], "打包为一次消息", dashed=False, lw=1.35)

    panel(
        ax, 0.82, 0.62, 4.55, 3.52,
        "六通道的真实来源", "blue_edge", "blue_edge",
        [
            "科学问题：用户输入或 Science 125 原文",
            "已有证据：文献 Fact 白名单（核心可引用）",
            "反对证据：反证检索、缺口矛盾、评审弱点",
            "关键约束：项目边界 + 全局约束池",
            "历史 / 反馈：审计摘要、HITL、人工意见",
        ],
        "来源可追溯；核心证据必须带 fact_id / chunk_id",
        "blue",
    )
    panel(
        ax, 5.72, 0.62, 4.60, 3.52,
        "如何进入模型", "purple_edge", "purple_edge",
        [
            "Agent 将六通道填入阶段 Prompt 变量",
            "available_fact_ids 作为引用白名单发出",
            "约束经 formatted_constraints 编号注入",
            "qwen_structured_chat 强制 JSON Schema",
            "生成后过滤不在白名单中的 fact_id",
        ],
        "作用：从机制上减少无依据生成与幻觉引用",
        "purple",
    )
    panel(
        ax, 10.67, 0.62, 4.48, 3.52,
        "调用后如何更新上下文", "green_edge", "green_edge",
        [
            "新 Fact 入库 → 更新核心白名单",
            "门禁失败 → 审计摘要写入历史结果",
            "评审弱点 / 反证 → 进入反对证据",
            "人工意见 → 转为 global_constraints",
            "证据不足 → 补文献后重建证据通道",
        ],
        "触发：新证据、Gate 失败、人工反馈、自迭代",
        "green",
    )

    ax.text(
        8, 0.44,
        "实线：六通道打包为一次 Qwen 调用     虚线：各通道汇入打包层     引用门禁只允许核心白名单 fact_id",
        ha="center", va="center", fontsize=7.3, color=COLORS["muted"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / "fig_aisci_p7_context_structure.png"
    svg_path = OUT_DIR / "fig_aisci_p7_context_structure.svg"
    fig.savefig(png_path, dpi=260, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(png_path)
    print(svg_path)


if __name__ == "__main__":
    generate()
