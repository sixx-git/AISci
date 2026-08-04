"""
毛笔书法精确抠图 —— 只保留墨色笔画（字体），其余透明。
原图: 黑墨写在米色底上（非纯白）。
输出: 透明 PNG，笔画染金铜渐变，保留飞白质感。
"""
import numpy as np
from PIL import Image
import os, glob

# ── 配置 ────────────────────────────────────────
BRUSH_DIR = r'D:\Workplace\AISci\output\_brush'
ORIG_GLOB = os.path.join(BRUSH_DIR, 'Traditional_Chinese_brush_call_*.png')
OUT_PATH  = os.path.join(BRUSH_DIR, 'lianbang_zhiyan_brush_clean.png')

# 金铜渐变 (上浅 → 下深)
GOLD_TOP   = np.array([245, 222, 179], dtype=np.float64)  # #F5DEB3 wheat
GOLD_BOT   = np.array([184, 134, 11], dtype=np.float64)   # #B8860B dark goldenrod

# 抽图阈值 (收紧：只保留纯墨色)
STROKE_CORE_LUM = 95      # L < 此值 → 笔画核心 (完全不透明)
FRINGE_LO       = 95      # 过渡带下界
FRINGE_HI       = 138     # 过渡带上界 (L > 此值 → 完全透明)

# 水印区强制透明 (右下角)
WM_X_RATIO = 0.78
WM_Y_RATIO = 0.82


def main():
    # 1) 加载原始图
    orig_files = glob.glob(ORIG_GLOB)
    if not orig_files:
        print("ERROR: 原始书法图未找到")
        return
    orig_path = orig_files[0]
    im_orig = Image.open(orig_path).convert('RGB')
    arr = np.array(im_orig, dtype=np.float64)
    h, w = arr.shape[:2]
    print(f"原始: {w}x{h}")

    # 2) 亮度通道
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    # 3) Alpha 掩码 (软过渡)
    alpha_raw = np.clip((FRINGE_HI - lum) / max(FRINGE_HI - FRINGE_LO, 1), 0, 1)
    alpha_raw[lum < STROKE_CORE_LUM] = 1.0
    alpha_raw[lum > FRINGE_HI] = 0.0

    # 4) 水印区强制透明
    wm_mask = np.zeros((h, w), dtype=bool)
    wm_y1 = int(h * WM_Y_RATIO)
    wm_x1 = int(w * WM_X_RATIO)
    wm_mask[wm_y1:, wm_x1:] = True
    alpha_raw[wm_mask] = 0.0

    # 统计
    opaque_px = int((alpha_raw > 0.05).sum())
    total_px = h * w
    print(f"  不透明像素: {opaque_px} ({opaque_px / total_px * 100:.1f}%)")

    # 5) 金铜渐变染色 (保留墨色深浅变化 → 飞白质感)
    y_norm = np.arange(h, dtype=np.float64).reshape(-1, 1) / max(h - 1, 1)
    gold_r = GOLD_TOP[0] + (GOLD_BOT[0] - GOLD_TOP[0]) * y_norm
    gold_g = GOLD_TOP[1] + (GOLD_BOT[1] - GOLD_TOP[1]) * y_norm
    gold_b = GOLD_TOP[2] + (GOLD_BOT[2] - GOLD_TOP[2]) * y_norm

    # 用原始亮度调制金色的明暗 (暗墨→深金, 飞白亮处→浅金)
    stroke_ref = np.clip(lum / 140.0, 0.15, 1.0)  # 归一化到笔画的亮度范围

    out_r = np.clip(gold_r * stroke_ref, 0, 255)
    out_g = np.clip(gold_g * stroke_ref, 0, 255)
    out_b = np.clip(gold_b * stroke_ref, 0, 255)

    # 6) 组装 RGBA
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = np.clip(out_r, 0, 255).astype(np.uint8)
    rgba[:, :, 1] = np.clip(out_g, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = np.clip(out_b, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = (alpha_raw * 255).astype(np.uint8)

    out_img = Image.fromarray(rgba, mode='RGBA')
    out_img.save(OUT_PATH, optimize=True)
    size_kb = os.path.getsize(OUT_PATH) // 1024

    # 验证
    final_alpha = rgba[:, :, 3]
    print(f"\n输出: {OUT_PATH}")
    print(f"  尺寸: {w}x{h}")
    print(f"  大小: {size_kb} KB")
    print(f"  Alpha: min={final_alpha.min()} max={final_alpha.max()} mean={final_alpha.mean():.1f}")
    print(f"  不透明(a>20): {(final_alpha>20).sum()}px ({(final_alpha>20).mean()*100:.1f}%)")
    print(f"  透明(a<10):  {(final_alpha<10).sum()}px ({(final_alpha<10).mean()*100:.1f}%)")


if __name__ == '__main__':
    main()
