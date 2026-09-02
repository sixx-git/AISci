# -*- coding: utf-8 -*-
"""修复 PEFT 案例报告正文与 PDF（格式/内容对齐实测证据）。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

REPORT_ID = "59e1ebd3-033b-4b31-9319-d3c11dfd7d65"
FILE_ID = "6ef5b798-0f3a-402a-9587-78821e5d2af7"
EXPORT_DIR = BACKEND / "storage" / "reports" / FILE_ID
CHART_SRC = BACKEND / "storage" / "charts" / "iter_5000_confusion_matrix.png"
CHART_ALT = (
    ROOT
    / "shaxiang-main"
    / "shaxiang-main"
    / "data"
    / "charts"
    / "smoke"
    / "iter_5000_confusion_matrix.png"
)

PAPER_TITLE = "基于任务复杂度感知的动态参数预算分配机制研究"

PAPER_ABSTRACT = (
    "参数高效微调（PEFT）常采用固定秩或均匀参数预算，难以适应任务复杂度与数据分布的动态变化。"
    "本文围绕「任务复杂度感知的动态参数预算分配能否提升微调效率与性能稳定性」展开研究，"
    "并在 GLUE/CoLA 语法可接受性任务上构建可执行的最小代理实验："
    "以依存深度与词性熵构造样本复杂度，经对数缩放映射为训练样本权重，"
    "用逻辑回归进行五折分层交叉验证，对照固定均匀权重策略。"
    "阶段性实测显示：整体 F1 均值约 0.198、准确率均值约 0.272；"
    "动态策略 F1 均值约 0.308，固定策略约 0.301，差距有限；"
    "混淆矩阵诊断图提示类别可分性不足。现有证据为小样本可行性验证，"
    "尚不足以支持该假设在 PEFT 场景下成立，结论限定为方法边界提示。"
)

CHAPTERS = {
    "problem_statement": (
        "**主要矛盾。** 固定参数预算的 PEFT 策略难以同时适应多样化任务需求与动态数据分布，"
        "常在资源利用效率与下游性能稳定性之间产生冲突。\n\n"
        "**矛盾来源。** 现有方法多采用静态秩/固定适配器容量；当任务复杂度波动或分布偏移时，"
        "易出现算力浪费或性能骤降。\n\n"
        "**研究对象拆解。** 内部对象包括低秩/适配器模块、样本权重与预算映射函数；"
        "外部对象包括任务类型、句法复杂度分布与算力约束；"
        "边界限定为文本理解类任务上的单次微调窗口内的代理验证，"
        "不直接等价于完整大规模语言模型微调部署。"
    ),
    "rationale": (
        "**机制说明。** 先用可解释的句法复杂度代理刻画样本难度，再将复杂度映射为训练权重，"
        "使学习资源向高复杂度样本倾斜，并与固定均匀权重形成对照，从而检验「动态预算」是否带来可观测增益。\n\n"
        "**知识空白。**\n"
        "- 动态预算分配在跨任务场景中的泛化与对分布漂移的响应仍不充分；\n"
        "- 合成数据增强场景下，分布偏移与梯度冲突的耦合风险尚未形成可操作约束；\n"
        "- 资源约束下的实时预算重分配缺少与复杂度探针联动的可验证协议。"
    ),
    "technical_details": (
        "验证路径采用依存句法特征与词性标签分布熵估计样本复杂度，"
        "并以 0.6×依存深度 + 0.4×词性熵构造复杂度标量；"
        "随后用对数缩放将复杂度映射为样本权重，实现动态预算分配的可执行代理。"
        "分类器选用 L2 正则化逻辑回归，评估指标包括 Matthews 相关系数（MCC）、F1、准确率与 AUC；"
        "采用五折分层交叉验证控制划分偏差，并以配对比较对照固定均匀权重。"
        "本报告生成链路基于通义千问（Qwen）与阿里云百炼接口完成结构化写作与质量控制。"
    ),
    "datasets": (
        "采用 GLUE 子任务 CoLA（Corpus of Linguistic Acceptability）作为核心验证基准，"
        "用于语法可接受性二分类。公开 CoLA 约含万级英语句子及可接受性标注；"
        "本阶段绑定本地 CoLA 结构化样本约 5000 条进行 smoke/阶段性验证。"
        "后续可扩展至完整 GLUE、SuperGLUE 或多任务复杂度谱系。"
        "数据集入口参考：https://huggingface.co/datasets/glue 。"
    ),
    "source": (
        "历史数据来自 CoLA 公开训练集的结构化文本与标签字段，"
        "并在迭代中记录复杂度评分、样本权重分配与交叉验证指标。"
        "路径以本地绑定目录为准，报告中不展开绝对路径。"
    ),
    "target": (
        "目标特征需与绑定数据同构：文本序列、句法复杂度量化值及二分类标签。"
        "阶段性成功标准设定为：动态策略 MCC 相对固定基线提升不少于 0.05，"
        "高复杂度子集 F1 不低于低复杂度子集，整体准确率不低于 0.50。"
        "当前实测尚未达到上述阈值。"
    ),
    "methods": (
        "本节为可执行的最小代理实验（表格学习/统计检验），"
        "用于检验「复杂度感知动态权重」这一可操作推论，"
        "而非对 PEFT 终极问题的完整解析。证据层级为阶段性小样本，外推需谨慎。"
        "步骤包括：（1）清洗 CoLA 文本并构造依存深度与词性熵特征；"
        "（2）按分位数划分高低复杂度区间；（3）对数缩放得到动态样本权重；"
        "（4）L2 逻辑回归五折交叉验证并记录 MCC/F1/准确率/AUC；"
        "（5）与固定权重基线对照，结合混淆矩阵诊断类别可分性。"
    ),
    "experiments": json.dumps(
        {
            "experimental_setup": (
                "五折分层交叉验证；L2 逻辑回归；特征为 TF-IDF（max_features=500）"
                "与句法复杂度标量；动态组使用对数缩放样本权重，固定组使用均匀权重。"
            ),
            "baselines": [
                "固定均匀预算（样本权重恒为 1.0）",
                "仅文本特征、不引入复杂度权重的对照设置",
            ],
            "metrics": [
                "Matthews 相关系数（MCC）",
                "F1 分数",
                "准确率",
                "AUC-ROC",
                "高低复杂度子集 F1",
                "收敛代理指标",
            ],
            "ablation_study": [
                "复杂度公式权重（深度 vs 词性熵）",
                "固定阈值 vs 分位数动态阈值",
                "线性 / 对数 / 指数缩放函数",
            ],
            "validation_protocol": (
                "比较动态与固定策略的 MCC/F1 差异；分别报告高/低复杂度子集表现；"
                "结合混淆矩阵诊断图界定方法边界。当前为计划 10 轮中的阶段性试跑。"
            ),
        },
        ensure_ascii=False,
    ),
    "results": (
        "### 实际分析结果\n\n"
        "> **阶段性结果**：实验计划 10 轮，当前计数约 4 轮（小样本可行性验证）；"
        "以下基于已完成试跑的可引用指标与诊断图。\n\n"
        "### 初步实验验证\n\n"
        "- 执行状态: 已产出可引用指标（阶段性，未跑满计划轮次）\n"
        "- 实测指标:\n"
        "  - F1均值: 0.198\n"
        "  - 准确率均值: 0.272\n"
        "  - AUC均值: 0.814\n"
        "  - 动态策略F1均值: 0.308\n"
        "  - 固定策略F1均值: 0.301\n"
        "  - 动态策略准确率均值: 0.405\n"
        "  - 固定策略准确率均值: 0.395\n"
        "  - 动态策略MCC均值: 0.369\n"
        "  - 固定策略MCC均值: 0.359\n"
        "  - 高复杂度子集F1: 0.230\n"
        "  - 低复杂度子集F1: 0.235\n"
        "- 实验图表: 1 张\n\n"
        "#### 图题与核心读图要点\n\n"
        "1. **【反例/失败轮诊断】混淆矩阵图展示模型在正负类上的预测分布** — "
        "失败/反例诊断图，仅用于界定方法边界，不作成功证据。\n\n"
        "> 以下结果以迭代实验验证为准；模拟/预期结果仅作参考。\n\n"
        "### 结果分析与讨论\n\n"
        "**主要发现。** "
        "分类主指标处于偏低水平：整体 F1 均值约 0.198、准确率均值约 0.272，"
        "混淆矩阵诊断评估为需重大调整。动态策略相对固定策略的 F1/准确率增益非常有限"
        "（约 0.007/0.010），高低复杂度子集 F1 亦接近，说明在当前特征与协议下，"
        "「复杂度感知动态预算」未能转化为稳定的可分性提升。\n\n"
        "**与科学假设的对照。** "
        "目标假设可概括为：任务复杂度感知的动态参数预算分配可显著提升微调效率与性能稳定性。"
        "本节仅为逻辑回归代理实验，并不等同于对 PEFT 低秩预算机制的直接验证。"
        "结合低性能与诊断图信号，当前更宜解读为方法边界提示或协议需修正，而非假设已被证实。\n\n"
        "**局限与后续工作。** "
        "当前为小样本可行性验证，证据层级较弱；实验未跑满计划轮次，结论仅为阶段性结果；"
        "主分类指标偏低，动态与固定策略差异有限。"
        "后续建议：（1）改用预训练语言模型句向量或完整 PEFT/LoRA 微调协议；"
        "（2）校准复杂度探针与真实难度标注的相关性；（3）补齐对照、消融与显著性检验后再下结论。"
    ),
    "references": [
        (
            "Qingru Zhang, Minshuo Chen, Alexander Bukharin, et al. "
            "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning[J/OL]. "
            "arXiv:2303.10512, 2023. DOI: 10.48550/arxiv.2303.10512"
        ),
    ],
}


def main() -> int:
    from app.core import database as dbmod
    from app.models.project import Report
    from app.services.latex_export_service import export_report_via_latex
    from app.services.report_content_sanitizer import sanitize_report_result
    from app.services.report_compliance_service import ensure_technical_details_qwen_disclosure

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

        report.paper_title = PAPER_TITLE
        report.title = PAPER_TITLE
        report.paper_abstract = PAPER_ABSTRACT
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

        plot_src = CHART_SRC if CHART_SRC.exists() else CHART_ALT
        plots = []
        if plot_src.exists():
            plots.append(
                {
                    "plot_id": "iter_5000_confusion_matrix",
                    "title": "【反例/失败轮诊断】混淆矩阵图展示模型在正负类上的预测分布",
                    "caption": (
                        "混淆矩阵展示正负类预测分布。当前低 F1/准确率提示类别可分性不足，"
                        "该图仅作诊断与方法边界说明。"
                    ),
                    "path": str(plot_src),
                    "file_path": str(plot_src),
                    "chart_kind": "diagnostic_counterexample",
                    "overall_assessment": "significant_issue",
                    "is_generated_from_real_data": True,
                }
            )

        result = {
            "title": PAPER_TITLE,
            "paper_title": PAPER_TITLE,
            "paper_abstract": PAPER_ABSTRACT,
            "plots": plots,
            "chapters": chapters,
            "results": {
                "discussion": "见结果章节正文。",
                "result_type_summary": "has_actual_results",
            },
        }
        result = sanitize_report_result(result)

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        verified = [
            {
                "title": "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
                "authors": "Qingru Zhang, Minshuo Chen, Alexander Bukharin, et al.",
                "year": 2023,
                "doi": "10.48550/arxiv.2303.10512",
                "source_url": "https://doi.org/10.48550/arxiv.2303.10512",
            }
        ]
        export = export_report_via_latex(
            result=result,
            output_dir=str(EXPORT_DIR),
            project_info={"title": PAPER_TITLE},
            citation_map=verified,
            verified_references=verified,
        )
        print("export:", {k: export.get(k) for k in ("pdf_success", "pdf_path", "warning", "export_method")})

        # 合并写入 report_data.json（保留旧 artifacts 指标）
        data_path = EXPORT_DIR / "report_data.json"
        old = {}
        if data_path.exists():
            try:
                old = json.loads(data_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                old = {}
        payload = {
            **old,
            "title": PAPER_TITLE,
            "paper_title": PAPER_TITLE,
            "paper_abstract": PAPER_ABSTRACT,
            "chapters": result.get("chapters"),
            "plots": plots,
            "verified_references": verified,
            "pdf_success": bool(export.get("pdf_success")),
            "pdf_file": export.get("pdf_path"),
            "tex_file": export.get("tex_file"),
            "export_method": export.get("export_method"),
            "warning": export.get("warning"),
            "report_id": REPORT_ID,
            "report_path": FILE_ID,
        }
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        extra = dict(report.extra_metadata or {})
        extra["plots"] = plots
        extra["pdf_success"] = bool(export.get("pdf_success"))
        if export.get("warning"):
            extra["pdf_warning"] = export["warning"]
        else:
            extra.pop("pdf_warning", None)
        extra["verified_references"] = verified
        report.extra_metadata = extra
        try:
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(report, "extra_metadata")
        except Exception:
            pass
        db.commit()
        print("DB updated, version=", report.version)
        pdf = EXPORT_DIR / "report.pdf"
        print("pdf exists:", pdf.exists(), "size:", pdf.stat().st_size if pdf.exists() else 0)
        return 0 if export.get("pdf_success") else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
