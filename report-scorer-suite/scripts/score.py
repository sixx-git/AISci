#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report-weighted-scorer —— 批量评论文档的七层加权评分器
用法:
  python score.py --dir <PDF文件夹> [--target-mean 85] [--out <输出目录>]

依赖: pymupdf (fitz)。建议在受管 Python 的 venv 中安装后运行。
输出:
  <out>/weighted_scores.csv   逐篇明细（含 composite 校准分、composite_raw 未校准分、L0-L6、原始信号）
  <out>/评分卡.md             评分卡（权重表/子指标口径/排名/公正性说明）
"""
import os, sys, glob, re, csv, argparse, statistics

# ===================== 加权模型（七层）=====================
# 科研四层 L2+L3+L4+L5 合计 85%；降权层 L0/L1/L6 合计 15%
WEIGHTS = {
    "L0_类型识别": 0.05,
    "L1_形式合规": 0.05,
    "L2_选题与问题": 0.20,
    "L3_方法学": 0.25,
    "L4_证据强度": 0.25,
    "L5_诚实度": 0.15,
    "L6_可用性": 0.05,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

# 学科桶（跨学科拼接判定；启发式，需领域专家终审）
BUCKETS = {
    "数理": ["素数","ζ","黎曼","Navier","弦","量子","引力","黑洞","暗","宇宙","QCD","超导体","相变","热力学","冷聚变"],
    "生命医学": ["基因","细胞","蛋白","神经","脑","免疫","疫苗","移植","衰老","微生物","DNA","血","fMRI","成瘾","睡眠","肺炎","肠","代谢"],
    "AI计算": ["神经网络","生成式","深度","图神经","强化","机器学习","数据增强","V2X","机器人","芯片","联邦","注意力","时序"],
    "材料化学": ["电池","聚合物","材料","催化","氢能","CO2","颜料","热电","超材料","纳米"],
    "地学环境": ["气候","生态","地球","物种","塑料","土壤","固废","碳汇","恐龙","热液"],
    "航天": ["火星","深空","脉冲星","系外","恒星","引力波","银河","地外","空间站","行星"],
    "社科心理": ["心理","文明","爱情","依恋","责任","伦理","博弈","孤独","情感"],
}
# 宏大命题关键词（代理实验-命题匹配度惩罚）
GRAND = ["宇宙","命运","素数","黎曼","文明","冷聚变","弦","量子引力","终极","黑洞","暗能量","时空","因果","意识","演化"]

def bucket_count(title):
    return sum(1 for b, kws in BUCKETS.items() if any(k in title for k in kws))


def score_file(name, text):
    title = name.replace(".pdf", "")
    refs = len(re.findall(r"\[\d+\]", text))
    gap_lang = bool(re.search(r"研究缺口|知识缺口|缺乏|尚未|缺口|gap|空缺", text, re.I))
    buckets = bucket_count(title)
    sig_test = bool(re.search(r"显著性|p值|p-value|Kruskal|t检验|χ²|卡方|bootstrap|置信区间", text, re.I))
    leakage = len(re.findall(r"泄漏|平凡解|标签泄漏|无效分裂", text))
    concrete = bool(re.search(r"R2|MAE|AUC|MSE|准确率|宏平均F1|轮廓系数|决定系数", text))
    ds = re.findall(r"(\d[\d,]{2,})\s*(行|样本|条|例)", text)
    ds_size = max([int(m.replace(",","")) for m, _ in ds], default=0)
    m = re.search(r"已跑\s*约?\s*(\d+)\s*轮（计划\s*(\d+)", text)
    runs_done, runs_plan = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    extrap_lim = bool(re.search(r"不得外推|不可外推|外推需谨慎|不构成为|不构成为稳健", text))
    lim_stmt = bool(re.search(r"局限|边界|待验证|后续工作|需进一步|谨慎", text))
    neg_ret = bool(re.search(r"需调整|失败|反例|未达标|负向|平凡解|泄漏|修正", text))
    uncert = bool(re.search(r"不确定性|置信区间|标准差|误差棒|bootstrap|方差|误差", text))
    grand = any(k in title for k in GRAND)
    generic_ml = bool(re.search(r"随机森林|XGBoost|KMeans|逻辑回归|岭回归|表格学习", text))
    proxy_match = not (grand and generic_ml)

    # L0 类型识别（上下文层）
    l0 = 100 if ("AI-Scientist" in text and "smoke" in text and "代理" in text) else 50
    # L1 形式合规
    sec = sum(1 for s in ["摘要","方法","结果","讨论","参考文献"] if re.search(s, text))
    l1 = sec/5*60 + (20 if re.search(r"结论", text) else 0) + (20 if re.search(r"待研究问题|引言|背景", text) else 0)
    # L2 选题与问题
    prob = 100 if (gap_lang and refs >= 4) else 60
    cross = 100 if buckets <= 1 else (60 if buckets == 2 else 30)
    l2 = 0.5*prob + 0.5*cross
    # L3 方法学
    s_check = 25 if concrete else 5
    s_leak = max(0, 25 - 8*min(leakage, 3))
    s_sig = 25 if sig_test else 5
    s_match = 25 if proxy_match else 10
    l3 = 0.25*s_check + 0.25*s_leak + 0.25*s_sig + 0.25*s_match
    # L4 证据强度（已删 轮次完成度/效应量/是否外推；仅样本量+结论自我限定，层内归一化）
    s_size = 50 if ds_size>=1000 else (36 if ds_size>=500 else (24 if ds_size>=100 else 10))
    s_selflim = 50 if lim_stmt else 10
    l4 = s_size + s_selflim
    # L5 诚实度
    l5 = (40 if lim_stmt else 0) + (35 if neg_ret else 0) + (25 if uncert else 0)
    # L6 可用性
    l6 = (40 if ds_size>0 else 10) + (30 if refs>=5 else 10) + (30 if concrete else 5)

    comp = (WEIGHTS["L0_类型识别"]*l0 + WEIGHTS["L1_形式合规"]*l1 +
            WEIGHTS["L2_选题与问题"]*l2 + WEIGHTS["L3_方法学"]*l3 +
            WEIGHTS["L4_证据强度"]*l4 + WEIGHTS["L5_诚实度"]*l5 +
            WEIGHTS["L6_可用性"]*l6)
    return {
        "L0":l0,"L1":l1,"L2":l2,"L3":l3,"L4":l4,"L5":l5,"L6":l6,
        "composite_raw": comp,
        "refs":refs,"buckets":buckets,"ds_size":ds_size,
        "runs":f"{runs_done}/{runs_plan}","sig_test":sig_test,
        "leakage_flags":leakage,"extrap_lim":extrap_lim,
        "proxy_match":proxy_match,"grand_claim":grand,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="PDF 文件夹")
    ap.add_argument("--target-mean", type=float, default=85.0, help="校准后目标均值（默认85）")
    ap.add_argument("--out", default=None, help="输出目录（默认 <dir>/_analysis）")
    args = ap.parse_args()

    pdf_dir = args.dir
    out_dir = args.out or os.path.join(pdf_dir, "_analysis")
    os.makedirs(out_dir, exist_ok=True)

    try:
        import fitz
    except ImportError:
        sys.exit("缺少 pymupdf，请先: pip install pymupdf")

    files = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
    if not files:
        sys.exit("未找到 PDF 文件: " + pdf_dir)
    print(f"共 {len(files)} 篇")

    rows = []
    for f in files:
        name = os.path.basename(f)
        doc = fitz.open(f)
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
        d = score_file(name, text)
        d["file"] = name
        rows.append(d)

    # 量尺校准：平移使均值达到 target-mean
    base_mean = statistics.mean(r["composite_raw"] for r in rows)
    offset = round(args.target_mean - base_mean, 2)
    for r in rows:
        r["composite"] = round(r["composite_raw"] + offset, 1)
    rows.sort(key=lambda r: r["composite"], reverse=True)

    # 输出 CSV
    cols = ["file","composite","composite_raw","L0","L1","L2","L3","L4","L5","L6",
            "refs","buckets","ds_size","runs","sig_test","leakage_flags","extrap_lim","proxy_match","grand_claim"]
    csv_path = os.path.join(out_dir, "weighted_scores.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow(r)

    # 生成 评分卡.md
    comps = [r["composite"] for r in rows]
    md = []
    md.append("# 加权评分卡（七层模型 · 已校准）\n")
    md.append(f"> 输入目录：{pdf_dir} ｜ 篇数：{len(files)} ｜ 校准目标均值：{args.target_mean}（平移 +{offset}，原均值 {base_mean:.2f}）\n")
    md.append("\n## 一、权重（合计100%，科研四层 L2-L5 合计85%）\n")
    md.append("| 层 | 维度 | 权重 |\n|---|---|---|")
    md.append("| L0 | 类型识别 | 5%（降权） |")
    md.append("| L1 | 形式合规 | 5%（降权） |")
    md.append("| L2 | 选题与问题 | 20% |")
    md.append("| L3 | 方法学 | 25% |")
    md.append("| L4 | 证据强度（样本量+结论自我限定；已删轮次/效应量/外推） | 25% |")
    md.append("| L5 | 诚实度 | 15% |")
    md.append("| L6 | 可用性 | 5%（降权） |")
    md.append("\n## 二、结果摘要\n")
    md.append(f"- 加权总分：均值 **{statistics.mean(comps):.1f}**，中位 {statistics.median(comps):.1f}，区间 **{min(comps):.1f} – {max(comps):.1f}**")
    for L in ["L0","L1","L2","L3","L4","L5","L6"]:
        md.append(f"- {L} 均分 {statistics.mean(r[L] for r in rows):.1f}")
    md.append("\n**TOP5**")
    for i, r in enumerate(rows[:5], 1):
        md.append(f"{i}. {r['file']} — {r['composite']}")
    md.append("\n**BOTTOM5**")
    for i, r in enumerate(rows[-5:], 1):
        md.append(f"{i}. {r['file']} — {r['composite']}")
    md.append("\n## 三、公正性红线\n")
    md.append("1. 自动评分=初筛非终审：L2跨学科牵强、L3命题匹配度为定性判断，须领域专家复核。\n")
    md.append("2. 信号可回溯：CSV 保留原始信号列，每条分层分可追到文本证据。\n")
    md.append("3. 不双重惩罚：如实披露泄漏拉低L3但抬高L5，净效应中性偏正。\n")
    md.append("4. 基准统一：同基准、同权重、同口径，无个案特判。\n")
    md_path = os.path.join(out_dir, "评分卡.md")
    with open(md_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(md))

    print(f"校准平移 OFFSET = +{offset} （原均值 {base_mean:.2f}）")
    print(f"均值 {statistics.mean(comps):.1f} | 中位 {statistics.median(comps):.1f} | 最高 {max(comps):.1f} | 最低 {min(comps):.1f}")
    print("CSV  ->", csv_path)
    print("MD   ->", md_path)

if __name__ == "__main__":
    main()
