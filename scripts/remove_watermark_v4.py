"""
谐波修复去水印 v4 —— 基于 Poisson/Laplace 方程的内容感知修复。
对每张图的右下角水印区域做数学插值填充，使修复区与周围背景无缝融合。

原理：在掩码区域求解 ∇²u = 0（Laplace 方程），
边界条件取自周围已知像素 → 结果是周围颜色的平滑延拓，
完美适配渐变/星空等抽象背景。
"""
import os, sys, time
import numpy as np
from PIL import Image
from scipy import sparse
from scipy.sparse.linalg import spsolve


def harmonic_inpaint(img_arr, mask):
    """
    img_arr: HxWxC float64 [0,255]
    mask:   HxW bool (True = 需要修复的区域)
    返回修复后的数组（原地修改副本）
    """
    h, w, c = img_arr.shape
    result = img_arr.copy()

    # 找到所有需要填充的像素坐标
    ys, xs = np.where(mask)
    n_fill = len(ys)
    if n_fill == 0:
        return result

    print(f"    掩码区域: {n_fill} 像素 ({n_fill/(h*w)*100:.1f}%)")

    # 构建稀疏 Laplacian 矩阵 (N_fill × N_fill)
    # 每个内部像素的方程: u[i] - mean(4邻居) = 0
    # 如果邻居在外部(已知)，则移到右边项 b
    # 建立索引映射: (y,x) -> row index in the system
    idx_map = np.full((h, w), -1, dtype=np.int32)
    idx_map[ys, xs] = np.arange(n_fill)

    rows = []
    cols = []
    data = []
    b_vals = np.zeros((n_fill, c))

    for k in range(n_fill):
        y, x = ys[k], xs[k]
        rows.append(k)
        cols.append(k)
        data.append(4.0)  # 对角线系数

        neighbor_sum = np.zeros(c)
        valid_neighbors = 0
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx_ = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx_ < w:
                if mask[ny, nx_]:
                    # 邻居也在掩码内 -> 加到矩阵
                    ni = idx_map[ny, nx_]
                    rows.append(k)
                    cols.append(ni)
                    data.append(-1.0)
                else:
                    # 邻居已知 -> 加到右边项
                    neighbor_sum += img_arr[ny, nx_, :]
                valid_neighbors += 1

        b_vals[k, :] = neighbor_sum

    # 构建稀疏矩阵并求解
    A = sparse.csr_matrix(
        (data, (rows, cols)), shape=(n_fill, n_fill)
    )

    t0 = time.time()
    for ch in range(c):
        filled = spsolve(A, b_vals[:, ch])
        result[ys, xs, ch] = np.clip(filled, 0, 255)

    dt = time.time() - t0
    print(f"    求解耗时 {dt:.2f}s")
    return result


def detect_watermark_mask(img_arr, margin_x=0.55, margin_y=0.80):
    """
    自动检测右下角水印区域：
    1) 在右下角矩形区域内找高亮度像素（白色水印）
    2) 用形态学膨胀扩展覆盖整个水印（包括半透明部分）
    """
    h, w = img_arr.shape[:2]
    gray = np.mean(img_arr[:, :, :3], axis=2)

    # 右下角 ROI
    roi_y1 = int(h * margin_y)
    roi_x1 = int(w * margin_x)
    roi = gray[roi_y1:, roi_x1:].copy()

    # 高亮度阈值检测（水印通常是白色/浅灰）
    brightness_thresh = np.percentile(roi, 75)
    bright_mask = roi > brightness_thresh

    # 膨胀以覆盖半透明边缘
    from scipy.ndimage import binary_dilation, binary_closing
    kernel_size = max(roi.shape) // 8
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones((kernel_size, kernel_size), dtype=bool)

    dilated = binary_dilation(bright_mask, structure=kernel, iterations=3)
    closed = binary_closing(dilated, structure=kernel, iterations=2)

    # 构建全图尺寸的 mask
    full_mask = np.zeros((h, w), dtype=bool)
    full_mask[roi_y1:, roi_x1:] = closed

    return full_mask


def process_image(src_path, dst_path=None):
    """处理单张图片：检测水印 -> 谐波修复 -> 保存"""
    if dst_path is None:
        dst_path = src_path  # 原地覆盖

    im = Image.open(src_path).convert('RGB')
    arr = np.array(im, dtype=np.float64)
    h, w = arr.shape[:2]
    print(f"\n  [{os.path.basename(src_path)[:40]}] {w}x{h}")

    # 检测水印掩码
    mask = detect_watermark_mask(arr)

    # 统计
    n_masked = int(np.sum(mask))
    print(f"    检测到水印区域: {n_masked} 像素")

    if n_masked < 500:
        print("    ⚠️ 水印区域太小，跳过")
        im.save(dst_path)
        return False

    # 谐波修复
    result = harmonic_inpaint(arr, mask)

    out_im = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    out_im.save(dst_path, optimize=True)
    sz = os.path.getsize(dst_path) / 1024
    print(f"    ✅ 完成 ({sz:.0f} KB)")
    return True


def main():
    base = r"D:\Workplace\AISci\output\图片"
    processed = 0
    skipped = 0

    # 收集所有子文件夹中的 PNG
    folders = sorted([d for d in os.listdir(base)
                      if os.path.isdir(os.path.join(base, d))])

    for folder in folders:
        fdir = os.path.join(base, folder)
        files = [f for f in os.listdir(fdir) if f.lower().endswith('.png')]
        if not files:
            continue
        fpath = os.path.join(fdir, files[0])  # 每个子文件夹只有一张图
        try:
            ok = process_image(fpath)
            if ok:
                processed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ {folder}: {e}")
            skipped += 1

    print(f"\n{'='*50}")
    print(f"总计: 处理 {processed} 张, 跳过 {skipped} 张")


if __name__ == '__main__':
    main()
