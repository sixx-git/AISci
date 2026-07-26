"""
报告正文净化：移除与具体科学问题无关的平台/大模型/智能体描述，
以及 Pipeline 回填的【】运维记录块；并提供迭代实验证据对齐工具。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_BRACKET_SECTION = re.compile(r"^【[^】]+】")

# Pipeline / data_finder 回填块内的续行，或独立的运维行
_OPERATIONAL_LINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^【[^】]+】",
        r"^[-*•]\s.*\[\$pending_download\$",
        r"^[-*•]\s.*\(Zenodo\).*\[merged\]",
        r"^<p>",
        r"^DataSpec\s",
        r"数据发现完备性得分",
        r"DataSpec\s*字段覆盖率",
        r"^已合并\s*CSV",
        r"^从\s*\d+\s*个\s*PDF",
        r"^待补充：",
        r"page=None",
        r"quality=\d",
        r"method=\$?user_upload",
        r"cite=\$?tbl_",
        r"\[\$user_upload",
        r"data_finder",
        r"用户上传/.*解析表",
        r"未从 PDF 抽取",
        r"未抽取到结构化",
        r"小样验证未执行",
        r"图表 extraction manifest",
        r"^\['小样验证",
        r"^\[\'小样验证",
        r"含用户上传解析表",
        r"Table page None",
        r"\$tbl_[a-f0-9]+",
        # 迭代实验 / 沙箱调试痕迹
        r"\[smoke[_\s-]?only[^\]]*\]",
        r"\brun[_\s-]?scope\s*:",
        r"\bsmoke[_\s-]?only\b",
        r"dummy_accuracy",
        r"AISCI_RUN_DIR|AISCI_PLOTS_DIR",
        r"Traceback \(most recent call last\)",
        r"File \"[A-Za-z]:\\",
        r"数据集路径\s*[:：]\s*[A-Za-z]:\\",
        r"\b[A-Za-z]:\\(?:浏览器|Users|Workplace)\\",
    ]
]

# 整行删除：明显属于系统实现而非科学内容
_DROP_LINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"qwen|千问|通义|百炼|dashscope",
        r"大语言模型|大模型|llm\b|gpt-?[34]",
        # 仅拦截平台/流水线语境；保留「多智能体系统」等科研表述
        r"(?:报告|假设|文献|评审|生成)智能体|智能体(?:平台|流水线)|ai\s*智能体",
        r"\bRAG\b|向量检索|faiss|embedding",
        r"AI[\s-]?Scientist|ai scientist",
        r"多智能体\s*(?:Pipeline|流水线)|pipeline\s*阶段|prompt\s*版本",
        r"multi-?agent\s*pipeline|agent\s*pipeline",
        r"人在回路|human[\s-]?in[\s-]?the[\s-]?loop",
        r"文献事实抽取|假设生成与筛选|假设生成与评审",
        r"api\s*调用|结构化输出|token",
        r"^analysis_script\s*:",
        r"^run_mode\s*:",
        r"^provider\s*:\s*shaxiang",
    ]
]

# 短语替换：保留句子但去掉平台措辞（勿误伤「多智能体系统」）
_PHRASE_REPLACEMENTS = [
    (re.compile(r"LLM\s*生成的?", re.I), ""),
    (re.compile(r"大模型生成的?", re.I), ""),
    (re.compile(r"由\s*智能体\s*", re.I), "通过"),
    (re.compile(r"智能体\s*(?:平台|流水线|Pipeline)", re.I), ""),
    (re.compile(r"多智能体\s*Pipeline", re.I), "研究流程"),
    (re.compile(r"AI[\s-]?Scientist\s*(平台|系统|Pipeline)?", re.I), ""),
    (re.compile(r"沙箱实测", re.I), "初步实验验证"),
    (re.compile(r"沙箱执行", re.I), "实验执行"),
    (re.compile(r"sandbox\s*execution", re.I), "pilot experiment"),
    (re.compile(r"产物目录\s*[:：]\s*`[^`]+`", re.I), ""),
    (re.compile(r"运行\s*ID\s*[:：|｜]\s*\S+", re.I), ""),
    (re.compile(r"\[smoke[_\s-]?only[^\]]*\]\s*", re.I), ""),
    (re.compile(r"run[_\s-]?scope\s*[:=]\s*\w+\s*", re.I), ""),
    (re.compile(r"(?i)\b[A-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*"), "[本地数据集]"),
]

_SCIENCE_FACING_CHAPTER_KEYS = (
    "problem_statement",
    "rationale",
    "technical_details",
    "datasets",
    "source",
    "target",
    "methods",
    "experiments",
    "results",
)

_METRIC_DROP_KEYS = frozenset(
    {
        "stdout_preview",
        "note",
        "dataset_rows",
        "dataset_columns",
        "error",
        "run_scope",
        "run_mode",
        "script_log",
        "traceback",
        "sample_size",
        "smoke",
    }
)

_METRIC_LABEL_MAP = {
    "dummy_accuracy_mean": "随机基线准确率均值",
    "dummy_accuracy": "随机基线准确率",
    "rf_accuracy_mean": "随机森林准确率均值",
    "rf_accuracy": "随机森林准确率",
    "rf_f1_macro_mean": "随机森林宏平均F1均值",
    "rf_f1_macro": "随机森林宏平均F1",
    "accuracy": "准确率",
    "accuracy_mean": "准确率均值",
    "f1": "F1分数",
    "f1_macro": "宏平均F1",
    "f1_macro_mean": "宏平均F1均值",
    "primary_metric": "主指标",
    "r2": "决定系数R²",
    "mae": "平均绝对误差",
    "rmse": "均方根误差",
}

_POSITIVE_CLAIM_PAT = re.compile(
    r"(显著提升|充分验证|成功验证|证实了(?:假设)?|模型决定系数达|改善率超|达到预期|高度吻合)",
)

_STAGE_CLAIM_DUP = re.compile(
    r"(?:现有证据为阶段性结果[，,]?\s*)?(?:尚不足以)?(?:尚待进一步验证|充分验证)假设?[。．]?\s*"
)
_BOUNDARY_BOILERPLATE = re.compile(
    r"(本节(?:验证)?为可执行的最小代理实验[^。]*。)\s*"
    r"(?:当前证据层级为阶段性[/／]?小样本[，,]?结论外推需谨慎。)?"
)
_ENGLISH_BLEED_LINE = re.compile(
    r"^[A-Za-z][A-Za-z0-9 ,.;:'\"()\[\]/%+\-]{40,}$"
)
_ENGLISH_BLEED_BLOCK = re.compile(
    r"(?ms)(?:^|\n)\s*(?:Quantum systems have an exponentially[\s\S]{20,800}?)(?=\n\s*-|\n\s*[^\sA-Za-z]|\Z)"
)

_UNPRINTABLE_RE = re.compile(r"[\ufffd\u0000-\u0008\u000b\u000c\u000e-\u001f]")


def strip_unprintable(text: str) -> str:
    if not text:
        return text
    return _UNPRINTABLE_RE.sub("", text)


def dedupe_repeated_sentences(text: str) -> str:
    """按句去重，保留首次出现；修复护栏叠句。"""
    if not text:
        return text
    s = str(text)
    # 修正常见病句
    s = s.replace("尚不足以尚待进一步验证", "尚不足以充分验证")
    s = s.replace("不得外推为尚待进一步验证", "不得外推为充分验证")
    s = s.replace("初步尚待进一步验证", "初步提示尚待进一步验证")
    s = re.sub(r"(现有证据为阶段性结果[，,]?\s*尚不足以充分验证假设。[。．]?\s*){2,}", r"\1", s)
    s = re.sub(
        r"(当前证据层级为阶段性[/／]?小样本[，,]?结论外推需谨慎。[。．]?\s*){2,}",
        r"\1",
        s,
    )
    s = re.sub(
        r"(本节(?:验证)?为可执行的最小代理实验[^。]{10,120}。[。．]?\s*){2,}",
        r"\1",
        s,
    )
    # 按中文句号切分去重
    parts = re.split(r"(?<=[。！？；\n])", s)
    seen: set[str] = set()
    out: List[str] = []
    for part in parts:
        key = re.sub(r"\s+", "", part.strip())
        if not key:
            out.append(part)
            continue
        if key in seen and len(key) >= 12:
            continue
        seen.add(key)
        out.append(part)
    return "".join(out).strip()


def strip_english_literature_bleed(text: str) -> str:
    """剔除中文章节中误混入的英文文献摘要行。"""
    if not text:
        return text
    s = _ENGLISH_BLEED_BLOCK.sub("\n", str(text))
    lines: List[str] = []
    for line in s.splitlines():
        stripped = line.strip()
        if _ENGLISH_BLEED_LINE.match(stripped) and not re.search(
            r"(accuracy|baseline|metric|dataset|figure|DOI|http)", stripped, re.I
        ):
            continue
        # 标题式英文文献行：以 " - Name: English..." 形式混入
        if re.match(r"^-\s+[A-Za-z].{10,}:\s*[A-Za-z]", stripped) and len(stripped) > 80:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def annotate_preprint_references(refs: Any, *, current_year: Optional[int] = None) -> Any:
    """对近年在线优先 / 预印本条目标注状态。"""
    if not isinstance(refs, list):
        return refs
    if current_year is None:
        from datetime import datetime

        current_year = datetime.now().year
    out: List[Any] = []
    for item in refs:
        if not isinstance(item, str):
            out.append(item)
            continue
        text = item
        year_m = re.search(r"\b(20\d{2})\b", text)
        needs = False
        if re.search(r"(?i)\b(preprint|arxiv|biorxiv|medrxiv)\b", text):
            needs = True
        if year_m:
            year = int(year_m.group(1))
            # 当年及以后，或近一年且为 EB/OL 在线文献
            if year >= current_year:
                needs = True
            elif year >= current_year - 1 and re.search(r"EB/?OL|online", text, re.I):
                needs = True
        if needs and "预印本" not in text and "在线优先" not in text:
            text = text.rstrip("。.;； ") + "（预印本/在线优先，引用时请核对正式出版信息）。"
        out.append(text)
    return out


def collapse_method_boundary_duplicates(text: str) -> str:
    """同一章节内验证边界声明只保留一次。"""
    if not text:
        return text
    s = str(text)
    # 多个【验证边界】块只留第一个
    blocks = list(re.finditer(r"【验证边界】[^\n【]*", s))
    if len(blocks) > 1:
        keep = blocks[0].group(0)
        s = re.sub(r"\n*\s*【验证边界】[^\n【]*", "", s)
        s = s.rstrip() + "\n\n" + keep
    # 正文里重复的「最小代理实验…外推需谨慎」
    first = True

    def _keep_once(m: re.Match) -> str:
        nonlocal first
        if first:
            first = False
            return m.group(0)
        return ""

    s = re.sub(
        r"本节(?:验证)?为可执行的最小代理实验[^。]{8,160}。"
        r"(?:\s*当前证据层级为阶段性[/／]?小样本[，,]?结论外推需谨慎。)?",
        _keep_once,
        s,
    )
    return dedupe_repeated_sentences(s)


def display_path_for_report(path: Any) -> str:
    """报告中只保留文件名，避免本地绝对路径。"""
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        name = Path(raw.replace("\\", "/")).name
    except Exception:
        name = raw.split("/")[-1].split("\\")[-1]
    return name or "[本地数据集]"


def clean_iteration_summary(text: Any) -> str:
    """去掉 smoke 前缀与调试串，保留可读摘要。"""
    s = strip_unprintable(str(text or ""))
    s = re.sub(r"\[smoke[_\s-]?only[^\]]*\]\s*", "", s, flags=re.I)
    s = re.sub(r"run[_\s-]?scope\s*[:=]\s*\w+\s*", "", s, flags=re.I)
    s = re.sub(r"(?i)\b[A-Z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*", "[本地数据集]", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def humanize_error_message(text: Any, *, max_len: int = 240) -> str:
    """失败信息只保留科学可读原因，截断堆栈。"""
    s = clean_iteration_summary(text)
    if not s:
        return ""
    if "Traceback" in s:
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        for ln in reversed(lines):
            if not ln.startswith("File ") and "Traceback" not in ln:
                s = ln
                break
    s = re.sub(r'File "[^"]+",\s*line\s*\d+.*', "", s)
    return s[:max_len].strip()


def academic_chart_title(
    *,
    name: str = "",
    note: str = "",
    iteration_number: int = 0,
    iteration_status: str = "",
) -> str:
    """将调试 note 转为学术图表标题。"""
    raw = clean_iteration_summary(note or name)
    debugish = bool(
        re.search(
            r"(?i)smoke|debug|tmp|test|确[证实]了数据|单类别问题|confusion|stdout",
            raw,
        )
    )
    stem = Path(str(name or "result")).stem.replace("_", " ").strip() or "实验结果"
    if not raw or debugish:
        title = f"第{iteration_number}轮实验结果：{stem}" if iteration_number else f"实验结果：{stem}"
    else:
        title = raw[:120]
    if str(iteration_status).lower() in {"failed", "error"}:
        title = f"[失败轮次{iteration_number}] {title}"
    return title


def filter_report_metrics(metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """供报告展示的指标子集（去掉 run_scope 等运维键）。"""
    out: Dict[str, Any] = {}
    if not isinstance(metrics, dict):
        return out
    for key, val in metrics.items():
        k = str(key)
        if k in _METRIC_DROP_KEYS:
            continue
        if k.startswith("failed_iter"):
            continue
        if k.lower().endswith("_path") or "traceback" in k.lower():
            continue
        out[k] = val
    return out


def format_metric_label(key: str) -> str:
    k = str(key or "").strip()
    if k in _METRIC_LABEL_MAP:
        return _METRIC_LABEL_MAP[k]
    low = k.lower()
    if low in _METRIC_LABEL_MAP:
        return _METRIC_LABEL_MAP[low]
    pretty = k.replace("_", " ")
    pretty = re.sub(r"\brf\b", "随机森林", pretty, flags=re.I)
    pretty = re.sub(r"\bdummy\b", "随机基线", pretty, flags=re.I)
    return pretty.strip() or k


def evidence_flags_from_small_validation(sv: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 small_validation 抽取证据层级与否定性信号。"""
    sv = sv or {}
    sandbox = sv.get("sandbox_execution") if isinstance(sv.get("sandbox_execution"), dict) else {}
    artifacts = sv.get("artifacts") if isinstance(sv.get("artifacts"), dict) else {}
    results = sv.get("results") if isinstance(sv.get("results"), dict) else {}
    actual = results.get("actual_results") if isinstance(results.get("actual_results"), dict) else {}
    brief = sv.get("narrative_brief") if isinstance(sv.get("narrative_brief"), dict) else {}
    narr = sv.get("iteration_narrative") if isinstance(sv.get("iteration_narrative"), dict) else {}
    raw_metrics = sandbox.get("metrics") or artifacts.get("metrics") or actual.get("sandbox_metrics") or {}
    metrics = filter_report_metrics(raw_metrics if isinstance(raw_metrics, dict) else {})
    progress = (
        sandbox.get("iteration_progress")
        or (actual.get("iteration_evidence") or {}).get("progress")
        or brief.get("progress")
        or {}
    )
    partial = bool(
        sandbox.get("partial_run")
        or sandbox.get("sandbox_incomplete")
        or (progress and not progress.get("completed_full_plan"))
    )
    raw_scope = ""
    if isinstance(raw_metrics, dict):
        raw_scope = str(raw_metrics.get("run_scope") or raw_metrics.get("run_mode") or "")
    smoke = "smoke" in raw_scope.lower() or bool(
        re.search(r"smoke", str(actual.get("summary") or ""), re.I)
    )

    trivial = False
    negative_fit = False
    for k, v in metrics.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        kl = str(k).lower()
        if "r2" in kl or "r²" in kl or kl.endswith("_r2"):
            if fv < 0:
                negative_fit = True
        if "accuracy" in kl and fv >= 0.999:
            trivial = True
        if "importance" in kl and abs(fv) < 1e-12:
            trivial = True

    vals = []
    for k, v in metrics.items():
        if "accuracy" in str(k).lower():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    if vals and all(abs(x - 1.0) < 1e-9 for x in vals) and len(vals) >= 2:
        trivial = True

    failed = bool(
        actual.get("failed_iterations")
        or actual.get("counterexamples")
        or (actual.get("iteration_evidence") or {}).get("failed_rounds")
    )
    verdict = str(
        narr.get("evidence_verdict") or brief.get("evidence_verdict") or ""
    ).strip()
    return {
        "partial_run": partial,
        "smoke": smoke,
        "trivial_solution": trivial,
        "negative_fit": negative_fit,
        "has_failures": failed,
        "metrics": metrics,
        "progress": progress,
        "result_type": results.get("result_type_summary") or "",
        "evidence_verdict": verdict,
    }


def align_paper_abstract(abstract: Any, sv: Optional[Dict[str, Any]] = None) -> str:
    """摘要与实测证据对齐：阶段性/否定性结果不得过度包装（幂等、不叠句）。"""
    text = strip_unprintable(str(abstract or "")).strip()
    flags = evidence_flags_from_small_validation(sv)
    prefixes: List[str] = []
    verdict = str(flags.get("evidence_verdict") or "").strip()
    if flags.get("smoke"):
        prefixes.append("基于小样本可行性验证（smoke）")
    elif flags.get("partial_run"):
        prog = flags.get("progress") or {}
        cur = prog.get("current_iteration")
        mx = prog.get("max_iterations")
        if cur is not None or mx is not None:
            prefixes.append(f"基于阶段性实验（约 {cur or '?'}/{mx or '?'} 轮）")
        else:
            prefixes.append("基于阶段性实验验证")

    weak_verdict = verdict in {"contradicted", "inconclusive", "blocked"}
    if (
        flags.get("trivial_solution")
        or flags.get("negative_fit")
        or flags.get("has_failures")
        or weak_verdict
    ):
        text = _POSITIVE_CLAIM_PAT.sub("尚待进一步验证", text)
        if flags.get("trivial_solution") and "平凡解" not in text:
            text = (text.rstrip("。") + "。") if text else ""
            text += (
                "实测表明当前设定下出现平凡解或无效分裂风险，结论仅作方法边界提示，"
                "不得外推为稳健验证。"
            )
        if flags.get("negative_fit") and "拟合" not in text[-80:]:
            text = (text.rstrip("。") + "。") if text else ""
            text += " 拟合与关联检验未达到预期，当前证据更支持假设在该协议下难以成立或需修正。"
        has_stage_claim = bool(
            re.search(r"阶段性结果|尚不足以|充分验证假设|未能稳定支持|试探性", text)
        )
        if verdict == "contradicted" and "未能稳定" not in text and not has_stage_claim:
            text = (text.rstrip("。") + "。") if text else ""
            text += " 试探性代理实验未能稳定支持假设，失败轮次提示当前方法边界。"
        elif verdict == "inconclusive" and not has_stage_claim:
            text = (text.rstrip("。") + "。") if text else ""
            text += " 现有证据为阶段性结果，尚不足以充分验证假设。"
        elif verdict == "blocked" and "尚不完整" not in text:
            text = (text.rstrip("。") + "。") if text else ""
            text += " 实验证据尚不完整，正文以预期路径为主。"

    if prefixes:
        lead = "；".join(prefixes) + "："
        if not text.startswith("基于") and "阶段性" not in text[:40] and "小样本" not in text[:40]:
            text = lead + text

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"。{2,}", "。", text)
    return dedupe_repeated_sentences(text.strip())


def method_boundary_note(sv: Optional[Dict[str, Any]] = None, ed: Optional[Dict[str, Any]] = None) -> str:
    """方法/问题错位时的诚实边界声明。"""
    flags = evidence_flags_from_small_validation(sv)
    bits = [
        "本节验证为可执行的最小代理实验（如表格学习/统计检验），"
        "用于检验假设的可操作推论，而非对该领域终极问题的完整解析证明或全物理模拟。"
    ]
    if flags.get("smoke") or flags.get("partial_run"):
        bits.append("当前证据层级为阶段性/小样本，结论外推需谨慎。")
    ed = ed or {}
    spec = ed.get("experiment_spec") if isinstance(ed.get("experiment_spec"), dict) else {}
    cols = list(spec.get("feature_columns") or [])[:8]
    if cols:
        bits.append(f"实际使用特征包括：{', '.join(str(c) for c in cols)}。")
    return "".join(bits)


def _is_operational_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _OPERATIONAL_LINE_PATTERNS)


def _is_operational_block_continuation(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if _BRACKET_SECTION.match(stripped):
        return True
    if stripped.startswith(("-", "*", "•")):
        return True
    return _is_operational_line(line)


def strip_operational_bracket_sections(text: str) -> str:
    """移除【运维标题】及其下属 Pipeline / data_finder 运行记录。"""
    if not text:
        return text

    out_lines: List[str] = []
    skipping = False

    for line in text.replace("\\n", "\n").splitlines():
        stripped = line.strip()
        if _BRACKET_SECTION.match(stripped):
            # 保留科学声明块，仅跳过运维回填块
            if re.search(r"验证边界|可复现参数|方法边界", stripped):
                skipping = False
                out_lines.append(line)
                continue
            skipping = True
            continue
        if skipping:
            if _is_operational_block_continuation(line):
                continue
            skipping = False
        if _is_operational_line(line):
            continue
        out_lines.append(line)

    collapsed: List[str] = []
    prev_blank = False
    for line in out_lines:
        blank = not line.strip()
        if blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = blank
    return "\n".join(collapsed).strip()


_ACTUAL_RESULTS_HEADING = re.compile(
    r"(?im)^#{2,3}\s*(?:Actual\s*Results(?:\s*[（(]实际分析结果[）)])?|实际分析结果)\s*$"
)
_ACTUAL_PLACEHOLDER_LINE = re.compile(
    r"(?i)^(暂无|待补充|信息不足|无实测|无实际|尚未|待完成|n/?a|none|null|"
    r"实验图待补全|待完成实验后补充).*"
)


def strip_empty_actual_results_section(text: Any) -> str:
    """无实测内容时删除空的 Actual Results / 实际分析结果 小节标题。"""
    if text is None:
        return ""
    raw = str(text).replace("\\n", "\n")
    if not raw.strip():
        return ""
    if not _ACTUAL_RESULTS_HEADING.search(raw):
        return raw

    lines = raw.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _ACTUAL_RESULTS_HEADING.match(line.strip()):
            j = i + 1
            body_lines: List[str] = []
            while j < len(lines):
                nxt = lines[j]
                if re.match(r"^#{2,3}\s+\S", nxt.strip()):
                    break
                body_lines.append(nxt)
                j += 1
            substantial = [
                ln.strip()
                for ln in body_lines
                if ln.strip() and not _ACTUAL_PLACEHOLDER_LINE.match(ln.strip())
            ]
            if substantial:
                out.append(line)
                out.extend(body_lines)
            i = j
            continue
        out.append(line)
        i += 1

    collapsed: List[str] = []
    prev_blank = False
    for line in out:
        blank = not line.strip()
        if blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = blank
    return "\n".join(collapsed).strip()


def _sanitize_results_chapter(results: Any) -> Any:
    if not isinstance(results, dict):
        text = strip_operational_bracket_sections(sanitize_text(results))
        return strip_empty_actual_results_section(text)

    cleaned: Dict[str, Any] = {}
    for key, val in results.items():
        if isinstance(val, list):
            items: List[Any] = []
            seen: set[str] = set()
            for item in val:
                text = strip_operational_bracket_sections(
                    sanitize_text(item, preserve_platform_terms=False)
                ).strip()
                if not text or _is_operational_line(text):
                    continue
                if text in seen:
                    continue
                seen.add(text)
                items.append(text)
            if key == "actual_results" and not items:
                continue
            cleaned[key] = items
        elif isinstance(val, str):
            text = strip_operational_bracket_sections(
                sanitize_text(val, preserve_platform_terms=False)
            ).strip()
            if key == "actual_results":
                text = strip_empty_actual_results_section(text)
                if not text:
                    continue
            cleaned[key] = text if text and not _is_operational_line(text) else []
        else:
            if key == "actual_results" and val in (None, "", {}, []):
                continue
            cleaned[key] = val
    return cleaned


def _clean_line(line: str, *, preserve_platform_terms: bool = False) -> Optional[str]:
    stripped = line.strip()
    if not stripped:
        return ""
    for pat in _DROP_LINE_PATTERNS:
        if preserve_platform_terms and "qwen" in pat.pattern.lower():
            continue
        if pat.search(stripped):
            return None
    text = line
    for pat, repl in _PHRASE_REPLACEMENTS:
        text = pat.sub(repl, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;，。；])", r"\1", text)
    text = strip_unprintable(text)
    if re.fullmatch(r"[A-Za-z0-9 ,.;:'\"()/-]{1,40}", text.strip()) and len(text.strip()) < 24:
        if not re.search(r"(accuracy|baseline|metric|dataset|figure|table)", text, re.I):
            return None
    return text.rstrip()


def sanitize_text(text: Any, *, preserve_platform_terms: bool = False) -> str:
    """净化单段文本或保留结构的列表项。"""
    if text is None:
        return ""
    if isinstance(text, list):
        cleaned_items: List[str] = []
        for item in text:
            part = sanitize_text(item, preserve_platform_terms=preserve_platform_terms)
            if part.strip():
                cleaned_items.append(part.strip())
        return "\n".join(f"- {item}" if not item.startswith("-") else item for item in cleaned_items)
    if isinstance(text, dict):
        parts = []
        for key, val in text.items():
            if val in (None, "", [], {}):
                continue
            val_str = sanitize_text(val, preserve_platform_terms=preserve_platform_terms)
            if val_str.strip():
                parts.append(f"{key}: {val_str}")
        return "\n".join(parts)

    raw = strip_unprintable(str(text).replace("\\n", "\n"))
    raw = strip_operational_bracket_sections(raw)
    out_lines: List[str] = []
    for line in raw.splitlines():
        cleaned = _clean_line(line, preserve_platform_terms=preserve_platform_terms)
        if cleaned is None:
            continue
        out_lines.append(cleaned)
    return "\n".join(out_lines).strip()


def sanitize_chapters(chapters: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(chapters, dict):
        return chapters
    cleaned = dict(chapters)
    for key in _SCIENCE_FACING_CHAPTER_KEYS:
        if key not in cleaned:
            continue
        val = cleaned[key]
        if key == "results":
            cleaned[key] = _sanitize_results_chapter(val)
        elif isinstance(val, dict):
            cleaned[key] = {k: sanitize_text(v) for k, v in val.items()}
        elif key == "technical_details":
            cleaned[key] = sanitize_text(val, preserve_platform_terms=True)
        else:
            cleaned[key] = sanitize_text(val)

        # 章节级二次净化
        cur = cleaned.get(key)
        if key == "source" and isinstance(cur, str):
            cleaned[key] = strip_english_literature_bleed(cur)
        if key in {"methods", "experiments", "results", "problem_statement", "rationale"} and isinstance(
            cur, str
        ):
            cleaned[key] = collapse_method_boundary_duplicates(str(cleaned[key]))
        if key == "results" and isinstance(cleaned.get(key), str):
            cleaned[key] = dedupe_repeated_sentences(str(cleaned[key]))

    # references 不在正文科学章节键中，需单独清洗 HTML / 重复类型标，并标注预印本
    if "references" in cleaned:
        from app.services.latex_export_service import clean_reference_text

        refs = cleaned.get("references")
        if isinstance(refs, list):
            cleaned_refs: List[Any] = []
            for item in refs:
                if isinstance(item, str):
                    cleaned_refs.append(clean_reference_text(item))
                elif isinstance(item, dict):
                    row = dict(item)
                    for field in ("title", "paper_title", "journal", "note", "authors"):
                        if field in row and isinstance(row[field], str):
                            row[field] = clean_reference_text(row[field])
                    cleaned_refs.append(row)
                else:
                    cleaned_refs.append(item)
            cleaned["references"] = annotate_preprint_references(cleaned_refs)
        else:
            cleaned["references"] = annotate_preprint_references(refs)
    return cleaned


def sanitize_report_result(
    result: Dict[str, Any],
    *,
    small_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """净化结构化报告，供 Markdown 与 LaTeX 导出使用。"""
    out = dict(result)
    chapters = out.get("chapters")
    if isinstance(chapters, dict):
        out["chapters"] = sanitize_chapters(chapters)
        out["markdown_content"] = ""
    sv = small_validation or out.get("_small_validation")
    if out.get("paper_abstract"):
        out["paper_abstract"] = align_paper_abstract(
            sanitize_text(out["paper_abstract"]),
            sv if isinstance(sv, dict) else None,
        )
        out["paper_abstract"] = dedupe_repeated_sentences(out["paper_abstract"])
    elif out.get("markdown_content"):
        out["markdown_content"] = sanitize_markdown_document(out["markdown_content"])
    # 讨论字段同步去重
    if isinstance(out.get("results"), dict) and out["results"].get("discussion"):
        out["results"] = {
            **out["results"],
            "discussion": collapse_method_boundary_duplicates(
                dedupe_repeated_sentences(str(out["results"]["discussion"]))
            ),
        }
    return out


def sanitize_markdown_document(markdown: str) -> str:
    if not markdown:
        return markdown

    skip_sections = {"运行摘要", "参考文献提醒", "图表数据提醒", "Figures"}
    out: List[str] = []
    in_skip = False

    for line in markdown.splitlines():
        heading = re.match(r"^#{1,3}\s+(.+)", line.strip())
        if heading:
            title = heading.group(1).strip()
            in_skip = any(title.startswith(s) for s in skip_sections)
        if in_skip:
            out.append(line)
            continue
        cleaned = _clean_line(line)
        if cleaned is None:
            continue
        out.append(cleaned)

    return "\n".join(out).strip()
