"""
谐波修复去水印 v5 —— 固定位置掩码 + 谐波插值。
即梦 AI 水印始终位于右下角固定区域，用固定矩形掩码覆盖，
然后求解 Laplace 方程从周围像素自然填补。
"""
import os, sys, time
import numpy as np
from PIL import Image
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.ndimage import binary_dilation


def build_laplacian_and_solve(img_arr, mask):
    """
    在 mask=True 的区域求解 Laplace 方程 ∇²u=0。
    边界条件：mask 边缘取 img_arr 的已知值。
    返回修复后的完整图像数组。
    """
    h, w, c = img_arr.shape
    result = img_arr.copy()

    ys, xs = np.where(mask)
    n = len(ys)
    if n == 0:
        return result

    # 像素 -> 系统行号的映射
    idx = np.full((h, w), -1, dtype=np.int32)
    idx[ys, xs] = np.arange(n)

    # 构建稀疏矩阵 (每个内部像素: 4*u[i] - sum(neighbors) = boundary_sum)
    row_list, col_list, data_list = [], [], []
    b = np.zeros((n, c))

    for k in range(n):
        y, x = ys[k], xs[k]
        row_list.append(k); col_list.append(k); data_list.append(4.0)

        bnd_sum = np.zeros(c)
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx_ = y+dy, x+dx
            if 0 <= ny < h and 0 <= nx_ < w:
                if mask[ny, nx_]:
                    ni = idx[ny, nx_]
                    row_list.append(k); col_list.append(ni); data_list.append(-1.0)
                else:
                    bnd_sum += img_arr[ny, nx_, :]
        b[k] = bnd_sum

    A = sparse.csr_matrix((data_list, (row_list, col_list)), shape=(n, n))

    t0 = time.time()
    for ch in range(c):
        result[ys, xs, ch] = np.clip(spsolve(A, b[:, ch]), 0, 255)

    print(f"      求解 {n} 像素 × {c} 通道: {time.time()-t0:.2f}s")
    return result


def make_watermark_mask(h, w,
                         x_start_frac=0.62,
                         y_start_frac=0.80):
    """
    创建右下角固定矩形掩码（覆盖即梦水印典型区域）。
    即梦水印通常在右下角约 38%宽 × 20%高的区域。
    """
    mask = np.zeros((h, w), dtype=bool)
    x1 = int(w * x_start_frac)
    y1 = int(h * y_start_frac)
    mask[y1:h, x1:w] = True

    # 轻微膨胀确保覆盖边缘
    kernel = np.ones((15, 15), dtype=bool)
    mask = binary_dilation(mask, structure=kernel, iterations=1)

    return mask


def process_one(src, dst=None):
    """处理单张图"""
    if dst is None:
        dst = src
    im = Image.open(src).convert('RGB')
    arr = np.array(im, dtype=np.float64)
    h, w = arr.shape[:2]

    name = os.path.basename(src)[:50]
    print(f"\n  [{name}]")
    print(f"    尺寸: {w}x{h}")

    mask = make_watermark_mask(h, w)
    n_px = int(mask.sum())
    print(f"    掩码: {n_px} 像素 ({n_px/(h*w)*100:.1f}%)")

    result = build_laplacian_and_solve(arr, mask)

    out = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    out.save(dst, optimize=True)
    print(f"    ✅ 保存 ({os.path.getsize(dst)/1024:.0f} KB)")
    return True


def main():
    base = r"D:\Workplace\AISci\output\图片"
    folders = sorted([d for d in os.listdir(base)
                      if os.path.isdir(os.path.join(base, d))])

    ok = fail = 0
    for fol in folders:
        fdir = os.path.join(base, fol)
        pngs = [f for f in os.listdir(fdir) if f.lower().endswith('.png')]
        if not pngs:
            continue
        fpath = os.path.join(fdir, pngs[0])
        try:
            process_one(fpath)
            ok += 1
        except Exception as e:
            print(f"    ❌ 错误: {e}")
            fail += 1

    print(f"\n{'='*50}")
    print(f"完成: {ok} 成功, {fail} 失败, 共 {ok+fail} 张")


if __name__ == '__main__':
    main()
