"""报告正文净化测试。"""
from app.services.report_content_sanitizer import (
    sanitize_chapters,
    sanitize_report_result,
    strip_empty_actual_results_section,
    strip_operational_bracket_sections,
)


def test_sanitize_chapters_cleans_references_html():
    chapters = sanitize_chapters(
        {
            "references": [
                "Planck Collaboration. <i>Planck</i> 2018 results{[J]}. Astron. Astrophys., 2020.",
                "Smith et al. arXiv preprint study. 2026. DOI: 10.48550/arXiv.2601.00001",
            ]
        }
    )
    refs = chapters["references"]
    assert "<i>" not in refs[0]
    assert "Planck 2018 results" in refs[0]
    assert "{[J]}" not in refs[0]
    assert "预印本" in refs[1]


def test_sanitize_removes_llm_agent_from_technical_details():
    chapters = sanitize_chapters(
        {
            "technical_details": (
                "采用 Qwen 大模型与多智能体 Pipeline 进行文献 RAG 检索。\n"
                "使用 DNA 折纸自组装与流式细胞术评估免疫逃逸。"
            ),
            "methods": "1. 文献事实抽取\n2. 假设生成与筛选\n3. 微流控实验",
        }
    )
    tech = chapters["technical_details"]
    assert "Qwen" not in tech
    assert "Pipeline" not in tech
    assert "DNA 折纸" in tech
    methods = chapters["methods"]
    assert "文献事实抽取" not in methods
    assert "微流控实验" in methods


def test_sanitize_keeps_scientific_multiagent_wording():
    """科研正文中的「多智能体系统」不得被整行删除。"""
    from app.services.report_content_sanitizer import sanitize_text

    text = (
        "在多智能体系统中，个体局部规则如何导致全局涌现。\n"
        "围绕假设「利用可微物理仿真实现多智能体涌现行为逆向求解」，开展验证。"
    )
    cleaned = sanitize_text(text)
    assert "多智能体系统" in cleaned
    assert "围绕假设" in cleaned
    assert "涌现行为逆向求解" in cleaned


def test_sanitize_report_result():
    result = sanitize_report_result(
        {
            "paper_abstract": "本研究结合千问大模型与智能体生成纳米机器人假设。",
            "chapters": {"technical_details": "向量检索 + FAISS 索引"},
            "markdown_content": "## 必要的技术手段\n\n使用 LLM 生成假设。",
        }
    )
    assert "千问" not in result["paper_abstract"]
    assert "向量检索" not in result["chapters"]["technical_details"]
    assert "LLM" not in result["markdown_content"]


def test_strip_operational_bracket_sections():
    raw = (
        "主要使用 NASA Exoplanet Archive。\n\n"
        "【推荐外部数据库/数据集】\n"
        "- Zenodo dataset [$pending_download$]: html snippet\n\n"
        "【多源数据查找与整合】\n"
        "DataSpec 场景=general；已合并 CSV：3813 行。\n"
        "数据发现完备性得分：83.3/100。\n\n"
        "科学数据来源包括 TESS 光变曲线。"
    )
    cleaned = strip_operational_bracket_sections(raw)
    assert "【" not in cleaned
    assert "DataSpec" not in cleaned
    assert "pending_download" not in cleaned
    assert "NASA Exoplanet Archive" in cleaned
    assert "TESS 光变曲线" in cleaned


def test_sanitize_results_removes_pipeline_notes():
    chapters = sanitize_chapters(
        {
            "results": {
                "simulated_results": [
                    "【整合数据集】data_finder 合并 CSV：3813 行；清洗 3813→3813 行。",
                ],
                "expected_results": [
                    "小样验证未执行；上列为已上传/合并数据的描述性统计。",
                    "预期通过 MCMC 获得 w 的后验约束。",
                ],
                "actual_results": [],
            }
        }
    )
    results = chapters["results"]
    assert results["simulated_results"] == []
    assert len(results["expected_results"]) == 1
    assert "MCMC" in results["expected_results"][0]
    assert "小样验证未执行" not in str(results)
    assert "actual_results" not in results


def test_strip_empty_actual_results_section():
    text = (
        "### Actual Results（实际分析结果）\n\n"
        "### Expected Results（预期结果）\n\n"
        "预期通过对照实验验证假设。"
    )
    cleaned = strip_empty_actual_results_section(text)
    assert "Actual Results" not in cleaned
    assert "实际分析结果" not in cleaned
    assert "Expected Results" in cleaned
    assert "对照实验" in cleaned


def test_keep_nonempty_actual_results_section():
    text = (
        "### Actual Results（实际分析结果）\n\n"
        "- accuracy: 0.82\n\n"
        "### Expected Results（预期结果）\n\n"
        "预期提升。"
    )
    cleaned = strip_empty_actual_results_section(text)
    assert "Actual Results" in cleaned
    assert "0.82" in cleaned


def test_sanitize_chapters_drops_empty_actual_heading():
    chapters = sanitize_chapters(
        {
            "results": (
                "### Actual Results（实际分析结果）\n\n"
                "暂无实测结果。\n\n"
                "### Expected Results（预期结果）\n\n"
                "预期在固定协议下得到可重复指标。"
            )
        }
    )
    results = chapters["results"]
    assert "Actual Results" not in results
    assert "Expected Results" in results


def test_strip_smoke_and_paths():
    from app.services.report_content_sanitizer import (
        academic_chart_caption,
        academic_chart_title,
        clean_iteration_summary,
        display_path_for_report,
        filter_report_metrics,
        format_metric_label,
    )

    assert "smoke" not in clean_iteration_summary("[smoke only] accuracy ok").lower() or "accuracy" in clean_iteration_summary(
        "[smoke only] accuracy ok"
    )
    cleaned = clean_iteration_summary("[smoke only] run_scope:smoke 结果可用")
    assert "run_scope" not in cleaned
    assert "[" not in cleaned or "smoke only" not in cleaned.lower()
    assert display_path_for_report(r"D:\Workplace\data\foo.csv") == "foo.csv"
    filtered = filter_report_metrics(
        {"run_scope": "smoke", "rf_accuracy_mean": 0.9, "stdout_preview": "x"}
    )
    assert "run_scope" not in filtered
    assert filtered["rf_accuracy_mean"] == 0.9
    assert "随机森林" in format_metric_label("rf_accuracy_mean")
    title = academic_chart_title(
        name="confusion.png", note="确认了数据是单类别问题", iteration_number=2
    )
    assert "确认了" not in title
    assert "第2轮" in title

    long_note = (
        "环境参数分布热力图（对数尺度），展示10个深部生物圈环境参数在min/median/max三个统计维度下的数值分布。"
        "由于输入数据仅1行，各参数min=median=max，热力图实际呈现的是单一值的对数变换，无法反映真实分布特征。"
        "应关注各参数的绝对数值量级差异。"
    )
    short_title = academic_chart_title(name="iter_1_parameter_heatmap.png", note=long_note)
    caption = academic_chart_caption(long_note)
    assert len(short_title) < 120
    assert "应关注各参" not in short_title or short_title.endswith(("。", "…"))
    assert caption == long_note
    assert "应关注各参数的绝对数值量级差异" in caption
    assert not caption.endswith("应关注各参")


def test_align_abstract_blocks_positive_on_trivial():
    from app.services.report_content_sanitizer import align_paper_abstract

    sv = {
        "sandbox_execution": {
            "partial_run": True,
            "metrics": {
                "run_scope": "smoke",
                "dummy_accuracy_mean": 1.0,
                "rf_accuracy_mean": 1.0,
            },
            "iteration_progress": {"current_iteration": 1, "max_iterations": 10},
        },
        "results": {"actual_results": {"summary": "smoke"}},
    }
    out = align_paper_abstract(
        "本研究充分验证了方法有效性，准确率显著提升至满分。",
        sv,
    )
    assert "充分验证" not in out
    assert "平凡" in out or "尚待" in out or "边界" in out
    assert "阶段性" in out or "小样本" in out or "smoke" in out.lower()


def test_escape_latex_greek():
    from app.services.latex_export_service import escape_latex

    out = escape_latex("参数ζ与rf_accuracy_mean")
    assert r"\zeta" in out
    assert r"\_" in out or "rf" in out
    assert "\ufffd" not in out


def test_dedupe_stage_claim_and_align_idempotent():
    from app.services.report_content_sanitizer import (
        align_paper_abstract,
        dedupe_repeated_sentences,
        strip_english_literature_bleed,
        annotate_preprint_references,
    )

    messy = (
        "基于小样本可行性验证（smoke）：研究表明模型具有优势。"
        "现有证据为阶段性结果，尚不足以尚待进一步验证假设。"
        "现有证据为阶段性结果，尚不足以尚待进一步验证假设。"
        "现有证据为阶段性结果，尚不足以充分验证假设。"
    )
    cleaned = dedupe_repeated_sentences(messy)
    assert cleaned.count("现有证据为阶段性结果") == 1
    assert "尚不足以尚待" not in cleaned

    sv = {"narrative_brief": {"evidence_verdict": "inconclusive"}, "sandbox_execution": {"partial_run": True}}
    once = align_paper_abstract(cleaned, sv)
    twice = align_paper_abstract(once, sv)
    assert twice.count("尚不足以充分验证假设") <= 1
    assert twice == align_paper_abstract(twice, sv)

    src = (
        "历史数据来源于 Steingroever 等人（2014）。\n"
        "Quantum systems have an exponentially large degree of freedom in the number of particles and hence provide a\n"
        "- Quantum Reservoir Computing: A Reservoir Approach Toward Quantum Machine Learning on Near-Term Quantum Devices: Quantum systems have an exponentially large degree of freedom\n"
        "There are three major ingredients. The ﬁrst is Szemer´edi’s theorem, which as-\n"
        "We present spectral and photometric observations of 10 Type Ia supernovae (SNe Ia) in the redshift range 0.16 z 0.62.\n"
        "We derive Hα fluxes for a large spectroscopic sample of sources over GOODS-North and South.\n"
    )
    src_c = strip_english_literature_bleed(src)
    assert "Steingroever" in src_c
    assert "Quantum systems have an exponentially" not in src_c
    assert "Szemer" not in src_c
    assert "three major ingredients" not in src_c
    assert "photometric observations" not in src_c
    assert "Hα fluxes" not in src_c and "Hα" not in src_c

    refs = annotate_preprint_references(
        ["Jiaqi Huang et al..An overview{[EB/OL]}. 2025. DOI: 10.3758/xxx"]
    )
    assert "预印本" in refs[0]
