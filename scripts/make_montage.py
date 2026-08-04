#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a 5x4 contact sheet of all 19+1 page backgrounds, labeled by page."""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = "D:/Workplace/AISci/output/图片"
OUT = "D:/Workplace/AISci/output/图片_质量总览.png"

# page folder order (1..19) with short title for label
TITLES = {
    "第一页": "P1 封面·知识星座",
    "第二页": "P2 价值·左右对比",
    "第三页": "P3 政策·上升柱状",
    "第四页": "P4 痛点·裂纹断裂",
    "第五页": "P5 方案·四锚点",
    "第六页": "P6 产品·三玻璃板",
    "第七页": "P7 Demo·柔化虚",
    "第八页": "P8 架构·七阶环",
    "第九页": "P9 创新·四象限",
    "第十页": "P10 壁垒·气泡网",
    "第十一页": "P11 竞品·极简网格",
    "第十二页": "P12 模式·金字塔",
    "第十三页": "P13 推广·上升路",
    "第十四页": "P14 成果·徽章墙",
    "第十五页": "P15 团队·协作网",
    "第十六页": "P16 教育·四维辐射",
    "第十七页": "P17 财务·仪表盘",
    "第十八页": "P18 规划·时间轴",
    "第十九页": "P19 结束·金光晕",
}
ORDER = ["第一页","第二页","第三页","第四页","第五页","第六页","第七页","第八页",
         "第九页","第十页","第十一页","第十二页","第十三页","第十四页","第十五页",
         "第十六页","第十七页","第十八页","第十九页"]

CW, CH = 600, 338          # cell thumbnail (16:9)
LABEL = 36
GAP = 14
COLS = 5
ROWS = 4

def get_font(size):
    for p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
              "C:/Windows/Fonts/simhei.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

font = get_font(22)

# collect cells: (label, image)
cells = []
for f in ORDER:
    fd = os.path.join(BASE, f)
    pngs = sorted([os.path.join(fd, x) for x in os.listdir(fd) if x.lower().endswith(".png")])
    label = TITLES[f]
    for i, p in enumerate(pngs):
        im = Image.open(p).convert("RGB")
        im.thumbnail((CW, CH))
        # pad to exact CWxCH (center)
        bg = Image.new("RGB", (CW, CH), (10, 16, 28))
        bg.paste(im, ((CW-im.width)//2, (CH-im.height)//2))
        tag = label + (f" (b{i+1})" if len(pngs) > 1 else "")
        cells.append((tag, bg))

W = COLS*CW + (COLS+1)*GAP
H = ROWS*(CH+LABEL) + (ROWS+1)*GAP
sheet = Image.new("RGB", (W, H), (20, 20, 24))
d = ImageDraw.Draw(sheet)

for idx, (tag, thumb) in enumerate(cells):
    r, c = divmod(idx, COLS)
    x = GAP + c*(CW+GAP)
    y = GAP + r*(CH+LABEL+GAP)
    # label bar
    d.rectangle([x, y, x+CW, y+LABEL], fill=(15, 29, 53))
    d.text((x+8, y+6), tag, fill=(233, 213, 140), font=font)
    sheet.paste(thumb, (x, y+LABEL))

sheet.save(OUT)
print("SAVED", OUT, sheet.size, "cells:", len(cells))
