# -*- coding: utf-8 -*-
"""整理 SST-2 DistilBERT 报告格式与参考文献（去除错配引用、中文化指标）。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

REPORT_ID = "d23447c5-57cb-4bd5-a601-9a26bc075ae1"
FILE_ID = "9f44e1b4-7d78-4867-8d84-0824a0f85dbc"
EXPORT_DIR = BACKEND / "storage" / "reports" / FILE_ID

CHART_DIR = ROOT / "shaxiang-main" / "shaxiang-main" / "data" / "charts" / "smoke"

PAPER_TITLE = "基于任务复杂度感知的动态参数预算分配机制研究"

PAPER_ABSTRACT = (
    "基于小样本可行性验证（smoke）：参数高效微调（PEFT）常采用固定秩或均匀参数预算，"
    "难以适应大语言模型在动态任务需求下的微调效率与性能稳定性。"
    "本文围绕任务复杂度感知的动态参数预算分配机制展开研究，"
    "并在 SST-2 情感分类任务上构建可执行的最小代理实验："
    "以冻结 DistilBERT CLS 表征为特征，按文本复杂度映射样本权重与特征维数，对照固定预算策略。"
    "阶段性实测显示：固定策略准确率约 0.808、F1 约 0.822；动态策略准确率约 0.814、F1 约 0.829；"
    "相对增益约 0.67%/0.71%，尚未达到预设 1% 门槛，且高复杂度子集未稳定占优。"
    "现有证据为阶段性结果，尚不足以充分验证假设。"
)

# 仅保留可核对文献：AdaLoRA（arXiv:2303.10512）。其余条目存在题名/作者与 arXiv id 错配，已移除。
VERIFIED_REFS = [
    {
        "document_id": "2303.10512",
        "title": "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
        "paper_title": "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
        "authors": (
            "Qingru Zhang, Minshuo Chen, Alexander Bukharin, Nikos Karampatziakis, "
            "Pengcheng He, Yu Cheng, Weizhu Chen, Tuo Zhao"
        ),
        "year": 2023,
        "doi": "10.48550/arXiv.2303.10512",
        "external_id": "2303.10512",
        "source_url": "https://arxiv.org/abs/2303.10512",
        "journal": "",
    }
]

CHAPTERS = {
    "problem_statement": (
        "**主要矛盾。** 固定参数高效微调策略难以适应多样化任务需求与动态数据分布，"
        "导致微调效率与模型性能之间的冲突。\n\n"
        "**矛盾来源。** 现有 PEFT 方法多采用静态参数分配；在任务复杂度波动或数据分布偏移时，"
        "易出现资源浪费或性能骤降。相关工作如 AdaLoRA\\cite{ref1} 已表明："
        "按重要性动态分配参数预算可改善低预算场景表现，但面向样本/任务复杂度的预算映射仍待检验。\n\n"
        "**研究对象拆解。** 内部：PEFT 模块结构（低秩矩阵/适配器）、样本级预算权重与特征维数分配；"
        "外部：任务类型、文本复杂度分布与算力约束；"
        "边界：限定于文本理解类任务上的单次代理验证窗口，不直接等价于完整大规模语言模型微调部署。"
    ),
    "rationale": (
        "**机制说明。** 先用可解释的文本复杂度代理刻画样本难度，再将复杂度映射为样本权重与特征维数，"
        "使学习资源向高复杂度样本倾斜，并与固定均匀预算形成对照，从而检验「动态预算」是否带来可观测增益。\n\n"
        "**知识空白。**\n"
        "- 动态预算分配在跨任务场景中的泛化与对分布漂移的响应仍不充分；\n"
        "- 合成数据增强场景下，分布偏移与梯度冲突的耦合风险尚未形成可操作约束；\n"
        "- 资源约束下的实时预算重分配缺少与复杂度探针联动的可验证协议。"
    ),
    "technical_details": (
        "验证路径采用冻结 DistilBERT-base-uncased 编码提取 CLS 向量；"
        "以文本长度、词表多样性、否定密度与标点密度构造多维复杂度评分，"
        "经 Sigmoid 映射得到样本级预算权重，并按复杂度动态保留特征维数（约 64–256）。"
        "分类器选用带类别平衡的逻辑回归，采用分层三折交叉验证；"
        "对照设置为均匀样本权重与固定 128 维特征。"
        "本报告生成链路基于通义千问（Qwen）与阿里云百炼接口完成结构化写作与质量控制。"
    ),
    "datasets": (
        "采用 GLUE 基准中的 SST-2 情感分类数据集进行初步验证。"
        "该数据集包含电影评论文本及二分类情感标签，适用于评估短文本情感理解任务中的动态适应能力。"
        "本阶段对编码子集抽样验证（约 1200 条编码样本）；后续可扩展至医疗、法律及新闻等领域语料。"
    ),
    "source": (
        "历史训练数据来源于 SST-2 公开数据集，包含原始文本序列与对应情感标签。"
        "可用字段为 sentence 与 label。"
        "当前验证基于该数据集子集进行抽样编码，用于构建固定预算与动态预算的对比基线。"
    ),
    "target": (
        "目标数据特征需与源数据集同构，重点采集样本级复杂度评分、动态特征维数分配记录、"
        "训练耗时及验证集性能指标。"
        "成功标准设定为：动态策略相比固定策略准确率或 F1 分数提升不低于 1%，"
        "且训练时间效率比不低于 0.83；高复杂度子集性能不低于基线水平。"
        "当前实测尚未达到上述相对增益门槛。"
    ),
    "methods": (
        "本节验证为可执行的最小代理实验，用于检验假设的可操作推论，"
        "而非对该领域终极问题的完整解析证明。证据层级为阶段性小样本，外推需谨慎。"
        "步骤包括：（1）使用预训练编码器提取文本 CLS 向量；（2）计算样本复杂度并映射至动态预算；"
        "（3）对比固定预算（均匀权重+固定 128 维）与动态预算（复杂度感知权重+动态维数）；"
        "（4）分层三折交叉验证评估准确率、F1 与训练时间。"
    ),
    "experiments": json.dumps(
        {
            "experimental_setup": (
                "基于 SST-2，分层三折交叉验证；硬件与早停策略保持一致；"
                "对照动态与固定策略在相同协议下的表现。"
            ),
            "baselines": [
                "fixed budget (uniform sample weights + fixed 128-d features)",
            ],
            "metrics": [
                "accuracy",
                "F1",
                "time efficiency ratio",
                "high-complexity accuracy",
            ],
            "ablation_study": [
                "移除复杂度评分模块",
                "固定预算上限",
                "将特征选择替换为随机截断",
            ],
            "validation_protocol": (
                "比较动态与固定策略的准确率/F1 差异；分别报告高复杂度子集表现；"
                "成功阈值为准确率或 F1 提升不低于 1% 且时间效率比不低于 0.83。"
            ),
        },
        ensure_ascii=False,
    ),
    "results": (
        "### 初步实验验证\n\n"
        "- 执行状态: 成功（smoke / 阶段性）\n\n"
        "**实测指标**\n\n"
        "- fixed accuracy: 0.8075\n"
        "- fixed F1: 0.8223\n"
        "- fixed training time: 0.199\n"
        "- dynamic accuracy: 0.8142\n"
        "- dynamic F1: 0.8294\n"
        "- dynamic training time: 0.106\n"
        "- accuracy improvement: 0.0067 (+0.67%)\n"
        "- F1 improvement: 0.0071 (+0.71%)\n"
        "- time efficiency ratio: 1.88\n"
        "- high complexity fixed accuracy: 0.7629\n"
        "- high complexity dynamic accuracy: 0.7526\n"
        "- high complexity accuracy improvement: -0.0103\n"
        "- fixed feature dims: 128\n"
        "- dynamic feature dims (mean): 162\n"
        "- charts: 3\n\n"
        "#### 图题与核心读图要点\n\n"
        "1. **策略对比柱状图** — 动态策略准确率/F1 略高于固定策略，但差距未达 1% 门槛。\n"
        "2. **复杂度分布直方图** — 展示样本复杂度分布及高/低复杂度划分依据。\n"
        "3. **动态策略混淆矩阵** — 用于诊断假阳性/假阴性结构，解释高复杂度子集未占优的现象。\n\n"
        "> 以下结果以迭代实验验证为准；模拟/预期结果仅作参考。\n\n"
        "### 结果分析与讨论\n\n"
        "**主要发现。** "
        "在当前 DistilBERT 冻结编码 + 线性头的代理协议下，动态策略相对固定策略取得小幅正向增益"
        "（accuracy 约 +0.67%，F1 约 +0.71%），训练耗时约为固定策略的 53%；"
        "但相对增益未达到预设 1% 门槛，且高复杂度子集 accuracy 反而下降约 1.03%。"
        "因此，现有证据更支持「方法边界提示 / 需继续调整」，而非假设已被证实。\n\n"
        "**与科学假设的对照。** "
        "目标假设可概括为：任务复杂度感知的动态参数预算分配可提升微调效率与性能稳定性。"
        "本节为可执行代理实验，并不等同于完整 LoRA/AdaLoRA 微调协议下的直接验证。"
        "结合未达标增益与高复杂度子集回退，当前更宜解读为协议与映射函数仍需修正。\n\n"
        "**局限与后续工作。** "
        "当前为 smoke/小样本可行性验证，证据层级较弱；"
        "后续建议：（1）扩大编码样本量并复验显著性；（2）调整预算映射上界，增强高复杂度样本预算；"
        "（3）在真实 PEFT/LoRA 设定下复现对照后再下结论。"
    ),
    "references": [
        (
            "Qingru Zhang, Minshuo Chen, Alexander Bukharin, et al. "
            "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning[J/OL]. "
            "arXiv:2303.10512, 2023. DOI: 10.48550/arXiv.2303.10512"
        ),
    ],
}


def _collect_plots() -> list:
    plots = []
    mapping = [
        (
            "iter_5000_strategy_compare.png",
            "固定与动态策略的准确率/F1 对比",
            "柱状图显示动态策略两项指标略高，但差距未达预设门槛。",
        ),
        (
            "iter_5000_complexity_hist.png",
            "样本复杂度分布直方图",
            "展示样本复杂度集中趋势及高低复杂度划分依据。",
        ),
        (
            "iter_5000_confusion_matrix.png",
            "动态策略混淆矩阵",
            "用于诊断分类错误分布，辅助解释高复杂度子集表现。",
        ),
    ]
    for name, title, caption in mapping:
        src = CHART_DIR / name
        if not src.exists():
            continue
        plots.append(
            {
                "plot_id": Path(name).stem,
                "title": title,
                "caption": caption,
                "path": str(src),
                "file_path": str(src),
                "is_generated_from_real_data": True,
                "source": "sandbox_execution",
            }
        )
    return plots


def main() -> int:
    from app.core import database as dbmod
    from app.models.project import Report
    from app.services.latex_export_service import export_report_via_latex
    from app.services.report_compliance_service import ensure_technical_details_qwen_disclosure
    from app.services.report_content_sanitizer import sanitize_report_result

    _, Session = dbmod.init_db()
    assert Session is not None
    db = Session()
    try:
        report = db.query(Report).filter(Report.id == REPORT_ID).first()
        if not report:
            print(f"ERROR: report not found: {REPORT_ID}")
            return 1

        chapters = dict(CHAPTERS)
        chapters["technical_details"] = ensure_technical_details_qwen_disclosure(
            chapters["technical_details"]
        )

        plots = _collect_plots()
        result = {
            "title": PAPER_TITLE,
            "paper_title": PAPER_TITLE,
            "paper_abstract": PAPER_ABSTRACT,
            "plots": plots,
            "chapters": chapters,
            "citation_map": VERIFIED_REFS,
            "verified_references": VERIFIED_REFS,
            "results": {"discussion": "见结果章节正文。"},
        }
        sv = {
            "narrative_brief": {"evidence_verdict": "inconclusive"},
            "sandbox_execution": {
                "partial_run": True,
                "metrics": {
                    "run_scope": "smoke",
                    "fixed_accuracy": 0.8075,
                    "dynamic_accuracy": 0.814167,
                    "fixed_f1": 0.822315,
                    "dynamic_f1": 0.829378,
                },
                "iteration_progress": {
                    "current_iteration": 3,
                    "max_iterations": 10,
                },
            },
        }
        result = sanitize_report_result(result, small_validation=sv)

        report.paper_title = PAPER_TITLE
        report.title = PAPER_TITLE
        report.paper_abstract = result["paper_abstract"]
        report.problem_statement = chapters["problem_statement"]
        report.rationale = chapters["rationale"]
        report.technical_details = chapters["technical_details"]
        report.datasets = chapters["datasets"]
        report.source = chapters["source"]
        report.target = chapters["target"]
        report.methods = chapters["methods"]
        report.experiments = chapters["experiments"]
        report.results = chapters["results"]
        report.references = json.dumps(chapters["references"], ensure_ascii=False)
        report.version = int(report.version or 1) + 1
        report.markdown_content = ""
        report.pdf_path = FILE_ID

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        fig_dir = EXPORT_DIR / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        for plot in plots:
            src = Path(plot["path"])
            dst = fig_dir / src.name
            if src.exists():
                shutil.copy2(src, dst)
                plot["relative_path"] = f"figures/{src.name}"

        export_info = export_report_via_latex(
            result,
            str(EXPORT_DIR),
            project_info={
                "name": "面向大语言模型的自适应参数高效微调",
                "research_domain": "自然语言处理 / 参数高效微调",
            },
            citation_map=VERIFIED_REFS,
            verified_references=VERIFIED_REFS,
        )
        result.update(export_info)
        result["report_id"] = REPORT_ID
        (EXPORT_DIR / "report_data.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        db.commit()
        print("OK abstract_len", len(result["paper_abstract"]))
        print("OK refs", len(VERIFIED_REFS))
        print("OK plots", len(plots))
        print("OK pdf", export_info.get("pdf_success"), export_info.get("pdf_path") or export_info.get("pdf_file"))
        return 0 if export_info.get("pdf_success") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
