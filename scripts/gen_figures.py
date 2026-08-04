# -*- coding: utf-8 -*-
"""生成商创赛论文两张理论模型示意图（深色科技风，英文标签，无中文依赖）。"""
import os, math
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\Workplace\AISci\output\AISci_paper_assets"
os.makedirs(OUT, exist_ok=True)

W, H = 2000, 1125
NAVY = (10, 22, 40)
NAVY2 = (14, 32, 56)
BLUE = (56, 111, 196)
CYAN = (63, 224, 255)
GOLD = (201, 168, 76)
WHITE = (235, 242, 252)
GREY = (150, 165, 185)

# 尝试加载字体（优先等线/微软雅黑，退化为默认）
def load_font(sz):
    for p in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()

FTITLE = load_font(46)
FNODE = load_font(30)
FSUB = load_font(26)
FSMALL = load_font(22)


def bg(img):
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = NAVY[0] + (NAVY2[0]-NAVY[0])*y/H
        g = NAVY[1] + (NAVY2[1]-NAVY[1])*y/H
        b = NAVY[2] + (NAVY2[2]-NAVY[2])*y/H
        d.line([(0, y), (W, y)], fill=(int(r), int(g), int(b)))
    return d


def node(d, cx, cy, r, label, fill, ring=BLUE, font=None):
    """绘制圆形节点，自动换行（空格/字符级），超长时自动缩小字号"""
    f = font or FNODE
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill, outline=ring, width=3)
    # 按空格分行
    words = label.split()
    lines = []
    cur = ""
    for w in words:
        if d.textlength((cur+" "+w).strip(), font=f) > 2*r*1.7 and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur+" "+w).strip()
    if cur:
        lines.append(cur)
    # 单行长单词 → 字符级强制折行
    final_lines = []
    for ln in lines:
        while d.textlength(ln, font=f) > 2*r*1.7 and len(ln) > 1:
            mid = len(ln)//2
            final_lines.append(ln[:mid])
            ln = ln[mid:]
        final_lines.append(ln)
    # 若仍超宽，降级到小一号字体重算（递归一次）
    max_w = max((d.textlength(l, font=f) for l in final_lines), default=0)
    if max_w > 2*r*1.5 and f.size > FSUB.size:
        return node(d, cx, cy, r, label, fill, ring, FSUB)
    lh = f.size + 6
    total = len(final_lines)*lh
    ty = cy - total/2 + lh/2
    for ln in final_lines:
        d.text((cx, ty), ln, font=f, fill=WHITE, anchor="mm")
        ty += lh


# ============ 图1：人本创业 人周期 / 企业周期 双循环 ============
def fig1():
    img = Image.new("RGB", (W, H), NAVY)
    d = bg(img)
    # 标题
    d.text((W/2, 56), "Figure 1. Humane Entrepreneurship: Human & Enterprise Cycles",
            font=FTITLE, fill=GOLD, anchor="mm")
    # 两个圆（拉大间距避免中间拥挤）
    cxL, cyL, R = 540, 620, 300
    cxR, cyR = 1460, 620
    d.ellipse([cxL-R, cyL-R, cxL+R, cyL+R], outline=BLUE, width=4, fill=(16,34,58,255))
    d.ellipse([cxR-R, cyR-R, cxR+R, cyR+R], outline=CYAN, width=4, fill=(16,34,58,255))
    d.text((cxL, cyL-R-70), "HUMAN CYCLE", font=FSUB, fill=BLUE, anchor="mm")
    d.text((cxR, cyR-R-70), "ENTERPRISE CYCLE", font=FSUB, fill=CYAN, anchor="mm")
    # 中心
    d.text((cxL, cyL), "Human", font=FNODE, fill=WHITE, anchor="mm")
    d.text((cxL, cyL+38), "Capital", font=FNODE, fill=WHITE, anchor="mm")
    d.text((cxR, cyR), "Vision &", font=FNODE, fill=WHITE, anchor="mm")
    d.text((cxR, cyR+38), "Mission", font=FNODE, fill=WHITE, anchor="mm")
    # 人周期五要素（圆上分布）
    human = ["Empowerment", "Ethics", "Equality", "Empathy", "Enablement"]
    for i, t in enumerate(human):
        ang = math.pi/2 + i*(2*math.pi/5)
        nx = cxL + (R+100)*math.cos(ang)
        ny = cyL - (R+100)*math.sin(ang)
        node(d, nx, ny, 110, t, (20,44,74), BLUE)  # r=95→110 防溢出
    ent = ["Envisioning", "Enthusiasm", "Enlighten", "Experiment", "Execution"]
    for i, t in enumerate(ent):
        ang = math.pi/2 + i*(2*math.pi/5)
        nx = cxR + (R+100)*math.cos(ang)
        ny = cyR - (R+100)*math.sin(ang)
        node(d, nx, ny, 125, t, (18,52,66), CYAN)  # r=125 给长标签更多空间
    # 底部融合说明
    d.text((W/2, H-46),
            "Integration for Sustainability: Profit, People and Planet — 人周期与企业周期融合形成可持续创业范式",
            font=FSMALL, fill=GREY, anchor="mm")
    img.save(os.path.join(OUT, "fig1_dual_cycle.png"))
    print("fig1 saved")


# ============ 图3：HCOE 以人为本的科研教育编排模型 ============
def fig3():
    img = Image.new("RGB", (W, H), NAVY)
    d = bg(img)
    d.text((W/2, 56), "Figure 3. HCOE Model: Human-Centered Orchestration for Education",
            font=FTITLE, fill=GOLD, anchor="mm")
    ccx, ccy = W/2, 600
    # 外环：教育成效（大椭圆 + 智能两行渲染）
    outcomes = ["Evidence Literacy", "Reproducibility", "Novelty Discovery", "Rigor & Integrity"]
    Ro = 470
    for i, t in enumerate(outcomes):
        ang = -math.pi/2 + i*(math.pi/2)
        ox = ccx + Ro*math.cos(ang)
        oy = ccy + Ro*math.sin(ang)
        d.ellipse([ox-220, oy-60, ox+220, oy+60], outline=GOLD, width=3, fill=(22,40,30))
        # 按优先级找最佳断点：& 连接 > 空格 > 音节近似
        if " & " in t:
            p1, p2 = t.split(" & ", 1)
            d.text((ox, oy-15), p1, font=FSUB, fill=GOLD, anchor="mm")
            d.text((ox, oy+17), "& " + p2, font=FSUB, fill=GOLD, anchor="mm")
        elif " " in t:
            parts = t.split(" ", 1)
            d.text((ox, oy-15), parts[0], font=FSUB, fill=GOLD, anchor="mm")
            d.text((ox, oy+17), parts[1], font=FSUB, fill=GOLD, anchor="mm")
        else:
            # 无空格长单词：用连字符在音节边界断开（硬编码常见英文断点）
            syllable_breaks = {
                "Reproducibility": ("Reproduc-", "ibility"),
                "Accountability": ("Accounta-", "bility"),
                "Sustainability": ("Sustaina-", "bility"),
            }
            if t in syllable_breaks:
                s1, s2 = syllable_breaks[t]
            else:
                mid = len(t)//2
                s1, s2 = t[:mid]+"-", t[mid:]
            d.text((ox, oy-15), s1, font=FSUB, fill=GOLD, anchor="mm")
            d.text((ox, oy+17), s2, font=FSUB, fill=GOLD, anchor="mm")
    # 四个支柱
    pillars = [("Empower", BLUE), ("Ethics", CYAN), ("Empathy", BLUE), ("Experiment", CYAN)]
    Rp = 270
    for i, (t, c) in enumerate(pillars):
        ang = -math.pi/2 + i*(math.pi/2)
        px = ccx + Rp*math.cos(ang)
        py = ccy + Rp*math.sin(ang)
        node(d, px, py, 110, t, (16,34,58), c)
    # 中心 AI 编排器
    d.ellipse([ccx-150, ccy-110, ccx+150, ccy+110], outline=WHITE, width=4, fill=(20,40,70))
    d.text((ccx, ccy-30), "AI Orchestrator", font=FNODE, fill=WHITE, anchor="mm")
    d.text((ccx, ccy+10), "AISci", font=FNODE, fill=CYAN, anchor="mm")
    d.text((ccx, ccy+50), "7-Stage Pipeline", font=FSMALL, fill=GREY, anchor="mm")
    # 连接线
    for i in range(4):
        ang = -math.pi/2 + i*(math.pi/2)
        px = ccx + Rp*math.cos(ang)
        py = ccy + Rp*math.sin(ang)
        ox = ccx + Ro*math.cos(ang)
        oy = ccy + Ro*math.sin(ang)
        d.line([(px, py), (ox, oy)], fill=GREY, width=2)
        d.line([(ccx, ccy), (px, py)], fill=BLUE, width=2)
    d.text((W/2, H-46),
            "Human-in-the-loop + Evidence Audit + Counterfactual L0 将人本理念编码进科研教育全流程",
            font=FSMALL, fill=GREY, anchor="mm")
    img.save(os.path.join(OUT, "fig3_hcoe.png"))
    print("fig3 saved")


# ============ 图2：AISci 七阶段科研 Pipeline ============
def fig2():
    w, h = 2000, 760
    img = Image.new("RGB", (w, h), NAVY)
    d = bg(img)
    d.text((w/2, 46), "Figure 2. AISci Seven-Stage Research Pipeline (Human-in-the-Loop)",
            font=FTITLE, fill=GOLD, anchor="mm")
    stages = ["Problem\nUnderstanding", "Literature\nMining", "Gap\nDiscovery",
              "Hypothesis\nGeneration", "Hypothesis\nReview", "Iterative\nExperiment", "Report\nGeneration"]
    n = len(stages)
    bw, bh, gap = 210, 150, 50
    total = n*bw + (n-1)*gap
    x0 = (w-total)/2
    y = 360
    for i, s in enumerate(stages):
        x = x0 + i*(bw+gap)
        d.rounded_rectangle([x, y, x+bw, y+bh], radius=14, outline=CYAN, width=3, fill=(16,34,58))
        lines = s.split("\n")
        ly = y + bh/2 - (len(lines)-1)*20
        for ln in lines:
            d.text((x+bw/2, ly), ln, font=FSUB, fill=WHITE, anchor="mm")
            ly += 40
        if i < n-1:
            ax = x+bw+8
            d.line([(ax, y+bh/2), (ax+gap-8, y+bh/2)], fill=BLUE, width=4)
            d.polygon([(ax+gap-8, y+bh/2), (ax+gap-26, y+bh/2-12), (ax+gap-26, y+bh/2+12)], fill=BLUE)
        d.text((x+bw/2, y-34), f"{i+1}", font=FNODE, fill=GOLD, anchor="mm")
    # Evidence audit 标注
    d.text((x0, y+bh+50), "Evidence Audit (证据链审计) + Boolean Gate (布尔门控) 贯穿每一阶段",
            font=FSUB, fill=GREY, anchor="mm")  # FSMALL→FSUB 提升可读性
    d.text((x0, y+bh+86), "人在回路（HITL）：用户在任意阶段查看、编辑、重跑 → 反事实 L0 安全实验",
            font=FSUB, fill=GREY, anchor="mm")  # FSMALL→FSUB
    img.save(os.path.join(OUT, "fig2_pipeline.png"))
    print("fig2 saved")


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    print("done")
