"""
毛笔书法抠图+染金铜渐变
1. 去除右下角 AI生成水印区域
2. 白底→透明（亮度反转为alpha，保留墨迹质感）
3. 墨色染为金铜渐变（适配深色首页）
4. 输出透明PNG
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def process_brush(src_path, dst_path):
    im = Image.open(src_path).convert('RGB')
    arr = np.array(im, dtype=np.float64)
    h, w = arr.shape[:2]
    print(f"  source: {w}x{h}")

    # ── 1. 清除水印区（右下角约15%x12%）──
    wm_x1 = int(w * 0.82)
    wm_y1 = int(h * 0.82)
    arr[wm_y1:h, wm_x1:w] = 255.0  # 漂白

    # ── 2. 计算亮度 & alpha（越暗=墨迹=不透明）──
    lum = np.mean(arr, axis=2)  # 0~255
    # 阈值：亮度>220 视为背景（接近白），<220 为墨迹
    # alpha 用 S 型曲线让边缘柔和
    alpha_raw = np.clip((220 - lum) / 40.0, 0, 1)  # 线性映射
    # 轻微高斯模糊柔化边缘
    alpha_img = Image.fromarray((alpha_raw * 255).astype(np.uint8), mode='L')
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=1.5))
    alpha_arr = np.array(alpha_img, dtype=np.float64) / 255.0

    # 进一步收紧：极淡的墨迹(灰度>200)设为全透明
    weak_mask = lum > 200
    alpha_arr[weak_mask] *= 0.0

    # ── 3. 金铜渐变色（垂直方向）──
    # 上方浅金 #F5DEB3 → 下方深铜 #B8860B
    y_coords = np.arange(h).reshape(-1, 1) / max(h - 1, 1)
    r_grad = (245 * (1 - y_coords) + 184 * y_coords).astype(np.float64)
    g_grad = (222 * (1 - y_coords) + 134 * y_coords).astype(np.float64)
    b_grad = (179 * (1 - y_coords) + 11 * y_coords).astype(np.float64)

    # ── 4. 合成：用墨迹亮度调制颜色明度（保留飞白质感）──
    # 墨迹越深的地方颜色越实，飞白处半透
    ink_density = 1.0 - (lum / 255.0)  # 0=白底, 1=纯黑墨

    out_r = np.clip(r_grad * (0.4 + 0.6 * ink_density), 0, 255)
    out_g = np.clip(g_grad * (0.4 + 0.6 * ink_density), 0, 255)
    out_b = np.clip(b_grad * (0.4 + 0.6 * ink_density), 0, 255)

    # ── 5. 组装 RGBA ──
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = np.clip(out_r, 0, 255).astype(np.uint8)
    rgba[:, :, 1] = np.clip(out_g, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = np.clip(out_b, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = (alpha_arr * 255).astype(np.uint8)

    # 强制水印区全透明（兜底）
    rgba[wm_y1:h, wm_x1:w, 3] = 0

    out = Image.fromarray(rgba, mode='RGBA')

    # 裁剪到内容边界（去掉多余白边）
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
        print(f"  cropped: {out.size[0]}x{out.size[1]} (bbox={bbox})")

    out.save(dst_path, optimize=True)
    print(f"  saved: {dst_path} ({len(open(dst_path,'rb').read())//1024}KB)")
    return dst_path


if __name__ == '__main__':
    src = r'D:\Workplace\AISci\output\_brush\Traditional_Chinese_brush_call_2026-08-01T15-05-34.png'
    dst = r'D:\Workplace\AISci\output\_brush\lianbang_zhiyan_brush.png'
    process_brush(src, dst)
