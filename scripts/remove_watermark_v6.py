"""
谐波修复去水印 v6 —— 加大掩码覆盖完整水印区域。
v5 掩码(y>80%)太小 → 水印上半部分残留。
v6 改为: 右下角大方块 x>54%, y>64%（覆盖即梦水印典型位置 + 余量）。
"""
import os, sys, time
import numpy as np
from PIL import Image
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.ndimage import binary_dilation


def build_laplacian_and_solve(img_arr, mask):
    h, w, c = img_arr.shape
    result = img_arr.copy()
    ys, xs = np.where(mask)
    n = len(ys)
    if n == 0:
        return result

    idx = np.full((h, w), -1, dtype=np.int32)
    idx[ys, xs] = np.arange(n)

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
    print(f"      求解 {n}px × {c}ch: {time.time()-t0:.2f}s")
    return result


def make_mask(h, w):
    """右下角大方块掩码：x > 54%, y > 64%"""
    mask = np.zeros((h, w), dtype=bool)
    mask[int(h*0.64):, int(w*0.54):] = True
    # 膨胀确保边缘覆盖
    kernel = np.ones((12, 12), dtype=bool)
    mask = binary_dilation(mask, structure=kernel, iterations=1)
    return mask


def process_one(src, dst=None):
    if dst is None:
        dst = src
    im = Image.open(src).convert('RGB')
    arr = np.array(im, dtype=np.float64)
    h, w = arr.shape[:2]
    name = os.path.basename(src)[:45]
    print(f"\n  [{name}] {w}x{h}")

    mask = make_mask(h, w)
    n_px = int(mask.sum())
    print(f"    掩码: {n_px}px ({n_px/(h*w)*100:.1f}%)")

    result = build_laplacian_and_solve(arr, mask)

    out = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))
    out.save(dst, optimize=True)

    # 验证：检查修复后亮像素数
    check = np.array(out, dtype=np.float64).mean(axis=2)
    remain = int(((check > 170) & make_mask(h, w)).sum())
    status = '✅' if remain < 200 else f'⚠️({remain})'
    print(f"    残留亮像素: {remain} {status}")
    return True


def main():
    base = r"D:\Workplace\AISci\output\图片"
    folders = sorted([d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))])
    ok = fail = 0
    for fol in folders:
        fdir = os.path.join(base, fol)
        pngs = [f for f in os.listdir(fdir) if f.lower().endswith('.png')]
        if not pngs:
            continue
        try:
            process_one(os.path.join(fdir, pngs[0]))
            ok += 1
        except Exception as e:
            print(f"    ❌ {e}")
            fail += 1
    print(f"\n{'='*50}\n完成: {ok} 成功, {fail} 失败")


if __name__ == '__main__':
    main()
