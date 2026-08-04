# -*- coding: utf-8 -*-
"""批量移除即梦AI平台水印 v3 —— 亮像素替换法。
   原理：水印是白色/浅色文字和logo在深色背景上。
   检测水印区内的亮像素，直接用周围深色背景的采样色替换。"""
import os
from PIL import Image, ImageDraw, ImageFilter

BASE = r"D:\Workplace\AISci\output\图片"


def remove_jimeng_watermark(img):
    """移除右下角'即梦 AI'水印 —— 亮像素替换版。"""
    w, h = img.size
    result = img.copy()
    pixels = result.load()

    # 水印区域（加大范围确保完全覆盖）
    ww, wh = 320, 110
    x1 = w - ww - 10
    y1 = h - wh - 8
    x2 = w - 10
    y2 = h - 8

    # ---- 第一步：从干净区域采样背景色 ----
    # 取水印区左上方较远的区域（避开任何可能的水印扩散）
    ref_x1, ref_y1 = max(0, x1 - 60), max(0, y1 - 80)
    ref_x2, ref_y2 = x1 - 10, y1 - 10
    if ref_x2 > ref_x1 and ref_y2 > ref_y1:
        ref_region = img.crop((ref_x1, ref_y1, ref_x2, ref_y2))
        # 计算参考区域的暗色调平均值（忽略过亮的异常像素）
        dark_pixels = []
        for px in ref_region.getdata():
            brightness = (px[0] + px[1] + px[2]) / 3
            if brightness < 100:  # 只取暗像素作为背景参考
                dark_pixels.append(px)
        if dark_pixels:
            bg_r = sum(p[0] for p in dark_pixels) // len(dark_pixels)
            bg_g = sum(p[1] for p in dark_pixels) // len(dark_pixels)
            bg_b = sum(p[2] for p in dark_pixels) // len(dark_pixels)
            bg_color = (bg_r, bg_g, bg_b)
        else:
            bg_color = (10, 22, 40)  # 默认深海军蓝
    else:
        bg_color = (10, 22, 40)

    # ---- 第二步：遍历水印区，替换亮像素 ----
    brightness_threshold = 60  # 降低阈值：捕获更多半透明logo像素
    for py in range(y1, y2):
        for px in range(x1, x2):
            r, g, b = pixels[px, py][:3]
            brightness = (r + g + b) / 3
            if brightness > brightness_threshold:
                # 亮像素 → 用背景色替换（带轻微随机扰动避免过于均匀）
                import random
                noise = random.randint(-3, 3)
                nr = max(0, min(255, bg_color[0] + noise))
                ng = max(0, min(255, bg_color[1] + noise))
                nb = max(0, min(255, bg_color[2] + noise))
                pixels[px, py] = (nr, ng, nb)

    # ---- 第三步：对整个水印区做强力高斯模糊融合边缘 ----
    # 扩大模糊范围以消除任何残留的硬边
    expand = 25
    ex1 = max(0, x1 - expand)
    ey1 = max(0, y1 - expand)
    ex2 = min(w, x2 + expand)
    ey2 = min(h, y2 + expand)
    blurred = result.crop((ex1, ey1, ex2, ey2)).filter(
        ImageFilter.GaussianBlur(radius=15)
    )
    result.paste(blurred, (ex1, ey1))

    return result


def main():
    files = []
    for root, dirs, fnames in os.walk(BASE):
        for f in fnames:
            if f.lower().endswith('.png'):
                files.append(os.path.join(root, f))

    print(f"找到 {len(files)} 张图片，v3 亮像素替换法移除水印...")

    processed = 0
    for fp in sorted(files):
        try:
            img = Image.open(fp).convert("RGB")
            out = remove_jimeng_watermark(img)
            out.save(fp, optimize=True)
            processed += 1
            print(f"  ✅ {os.path.basename(fp)[:50]}")
        except Exception as e:
            print(f"  ❌ {os.path.basename(fp)}: {e}")

    print(f"\n完成！{processed}/{len(files)} 张")


if __name__ == "__main__":
    main()
