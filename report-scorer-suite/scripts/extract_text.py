#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report-scientist-scorer 的辅助工具：把目录下每个 PDF 抽取为纯文本 .txt，
便于大模型(扮演人类科学家)逐篇阅读并评分。"""
import os, glob, argparse
import fitz

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="PDF 文件夹")
    ap.add_argument("--out", required=True, help="文本输出目录")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.dir, "*.pdf")))
    if not files:
        sys.exit("未找到 PDF: " + args.dir)
    n = 0
    for f in files:
        name = os.path.basename(f)
        doc = fitz.open(f)
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
        with open(os.path.join(args.out, name.replace(".pdf", ".txt")), "w", encoding="utf-8") as fp:
            fp.write(text)
        n += 1
    print(f"已抽取 {n} 篇文本到 {args.out}")

if __name__ == "__main__":
    import sys
    main()
