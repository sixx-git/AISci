"""
LaTeX 报告导出服务

流程:
  1. 基于 latex_template/scientific_plan_template.tex 的 ICLR 中文样式
  2. 将 12 字段结构化报告内容填充为 report.tex + references.bib
  3. 使用 XeLaTeX + BibTeX 编译为 PDF
  4. 若 XeLaTeX 不可用，可选回退到 Markdown → PDF（Playwright）
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "latex_template"
TEMPLATE_TEX = "scientific_plan_template.tex"
TEMPLATE_ASSETS = (
    "iclr2024_conference.sty",
    "iclr2024_conference.bst",
    "fancyhdr.sty",
    "natbib.sty",
)

_INVALID_REFERENCE_MARKERS = (
    "缺少真实引用",
    "证据链不足",
    "禁止虚构",
    "暂无已验证",
    "需先导入",
)

_LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# Unicode 希腊字母 / 常用数学符号 → LaTeX（避免 ζ 等丢失或乱码）
_UNICODE_MATH_TO_LATEX = {
    "α": r"$\alpha$",
    "β": r"$\beta$",
    "γ": r"$\gamma$",
    "δ": r"$\delta$",
    "ε": r"$\epsilon$",
    "ζ": r"$\zeta$",
    "η": r"$\eta$",
    "θ": r"$\theta$",
    "ι": r"$\iota$",
    "κ": r"$\kappa$",
    "λ": r"$\lambda$",
    "μ": r"$\mu$",
    "ν": r"$\nu$",
    "ξ": r"$\xi$",
    "π": r"$\pi$",
    "ρ": r"$\rho$",
    "σ": r"$\sigma$",
    "τ": r"$\tau$",
    "φ": r"$\phi$",
    "χ": r"$\chi$",
    "ψ": r"$\psi$",
    "ω": r"$\omega$",
    "Γ": r"$\Gamma$",
    "Δ": r"$\Delta$",
    "Θ": r"$\Theta$",
    "Λ": r"$\Lambda$",
    "Ξ": r"$\Xi$",
    "Π": r"$\Pi$",
    "Σ": r"$\Sigma$",
    "Φ": r"$\Phi$",
    "Ψ": r"$\Psi$",
    "Ω": r"$\Omega$",
    "²": r"$^{2}$",
    "³": r"$^{3}$",
    "±": r"$\pm$",
    "×": r"$\times$",
    "≤": r"$\leq$",
    "≥": r"$\geq$",
    "≠": r"$\neq$",
    "≈": r"$\approx$",
    "∞": r"$\infty$",
    "·": r"$\cdot$",
}

# 允许在正文中保留的「无参数」LaTeX 命令（避免把 Windows 路径 \Users \allgaps 当命令）
_SAFE_BARE_LATEX_CMDS = frozenset(
    {
        "Omega",
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "theta",
        "lambda",
        "mu",
        "nu",
        "pi",
        "rho",
        "sigma",
        "tau",
        "phi",
        "chi",
        "psi",
        "omega",
        "Delta",
        "Gamma",
        "Lambda",
        "Sigma",
        "Phi",
        "Psi",
        "ldots",
        "cdots",
        "dots",
        "times",
        "cdot",
        "pm",
        "mp",
        "infty",
        "leq",
        "geq",
        "neq",
        "approx",
        "equiv",
        "rightarrow",
        "leftarrow",
        "Rightarrow",
        "to",
        "partial",
        "nabla",
        "sum",
        "int",
        "prod",
        "sqrt",
        "frac",
    }
)


def _is_ascii_letter(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _normalize_windows_paths_for_latex(s: str) -> str:
    """把正文中的 Windows 路径反斜杠改为正斜杠，避免被 TeX 当成控制序列。"""
    if not s or "\\" not in s:
        return s

    def _repl(match: re.Match[str]) -> str:
        return match.group(0).replace("\\", "/")

    # D:\foo\bar 或 \\server\share\path
    s = re.sub(r"(?i)\b[A-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*", _repl, s)
    s = re.sub(r"\\\\[^\\/:*?\"<>|\r\n]+(?:\\[^\\/:*?\"<>|\r\n]+)+", _repl, s)
    return s



def get_latex_template_dir() -> Path:
    env_path = os.environ.get("LATEX_TEMPLATE_DIR", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_TEMPLATE_DIR


def _find_braced_group_end(text: str, open_brace_idx: int) -> int:
    """open_brace_idx 指向 '{'，返回闭合 '}' 之后的下标；失败返回 -1。"""
    if open_brace_idx < 0 or open_brace_idx >= len(text) or text[open_brace_idx] != "{":
        return -1
    depth = 0
    i = open_brace_idx
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _normalize_ensuremath_to_inline_math(text: str) -> str:
    """
    将 \\ensuremath{...} 规范为 $...$，避免后续按 $ 切分时拆破花括号，
    产生 \\ensuremath{$\\Lambda$\\} 这类非法源码。
    """
    if not text or "\\ensuremath" not in text:
        return text
    out: List[str] = []
    i = 0
    token = "\\ensuremath"
    while i < len(text):
        if text.startswith(token, i):
            j = i + len(token)
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == "{":
                end = _find_braced_group_end(text, j)
                if end > j:
                    inner = text[j + 1 : end - 1].strip()
                    # 去掉已有外层 $...$
                    while (
                        len(inner) >= 2
                        and inner.startswith("$")
                        and inner.endswith("$")
                        and inner.count("$") == 2
                    ):
                        inner = inner[1:-1].strip()
                    # 残留未配对 $ 会再次破坏切分，直接去掉
                    if "$" in inner:
                        inner = inner.replace("$", "")
                    out.append(f"${inner}$" if inner else "")
                    i = end
                    continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _promote_inline_math_segment(text: str) -> str:
    """在不含 $...$ 的文本段内提升伪 LaTeX 数学片段。"""
    if not text:
        return text

    def _wrap(match: re.Match[str]) -> str:
        token = match.group(0)
        plain = token.replace("\\_", "_")
        # significant_issue / feature_columns 等长 snake_case 标识符不是数学量
        if re.fullmatch(r"[A-Za-z]{4,}_[A-Za-z]{3,}(?:_[A-Za-z0-9]+)*", plain):
            return plain.replace("_", " ")
        inner = plain
        return f"${inner}$"

    greek_cmd = (
        r"\\(?:Omega|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|nu|pi|rho|sigma|tau|"
        r"phi|chi|psi|omega|Delta|Gamma|Lambda|Sigma|Phi|Psi|frac|sqrt|partial|nabla|cdot|"
        r"times|leq|geq|neq|approx|equiv|infty|pm|mp|sum|int|prod)"
        r"(?:\\_[A-Za-z0-9]+|_\{[^}]+\}|_[A-Za-z0-9]+|\{[^}]*\})*"
    )
    # 仅提升短物理量：已转义 H\_0，或单一下标 H_0 / n_s / k_B。
    # 禁止匹配列名中部片段（如 k_W_per_mK 里的 per_mK），否则会 Double subscript。
    var_cmd = (
        r"(?<![\\$A-Za-z0-9_])"
        r"(?:"
        r"[A-Za-z]{1,4}\\_(?:[0-9]{1,4}|[A-Za-z]{1,3})(?![A-Za-z0-9\\_])|"
        r"[A-Za-z]{1,3}_(?:[0-9]{1,4}|[A-Za-z]{1,2})(?![A-Za-z0-9_])"
        r")"
    )
    text = re.sub(greek_cmd, _wrap, text)
    parts = re.split(r"(\$[^$\n]+\$)", text)
    rebuilt: List[str] = []
    for part in parts:
        if part.startswith("$") and part.endswith("$"):
            rebuilt.append(part)
        else:
            rebuilt.append(re.sub(var_cmd, _wrap, part))
    return "".join(rebuilt)


def _promote_inline_math(text: str) -> str:
    """将正文中的伪 LaTeX 数学片段（如 H\\_0、\\Omega\\_m）包裹为 $...$。"""
    if not text:
        return text
    if "$" not in text:
        return _promote_inline_math_segment(text)
    parts = re.split(r"(\$[^$\n]+\$)", text)
    return "".join(
        part if part.startswith("$") and part.endswith("$") else _promote_inline_math_segment(part)
        for part in parts
    )


def _escape_plain_latex(s: str) -> str:
    """转义 LaTeX 特殊字符（不含 $...$ 数学片段）。"""
    if not s:
        return ""
    out: List[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        # 仅保留 ASCII 命令名，避免中文路径「\浏览器」被当成控制序列
        if ch == "\\" and i + 1 < len(s) and _is_ascii_letter(s[i + 1]):
            j = i + 1
            while j < len(s) and _is_ascii_letter(s[j]):
                j += 1
            cmd = s[i + 1 : j]
            if j < len(s) and s[j] == "{":
                depth = 0
                k = j
                while k < len(s):
                    if s[k] == "{":
                        depth += 1
                    elif s[k] == "}":
                        depth -= 1
                        if depth == 0:
                            k += 1
                            break
                    k += 1
                out.append(s[i:k])
                i = k
                continue
            # 无参数命令：仅白名单保留（防止 \Users \allgaps 等路径片段）
            if cmd in _SAFE_BARE_LATEX_CMDS:
                out.append(s[i:j])
                i = j
                continue
            out.append(_LATEX_SPECIAL_CHARS["\\"])
            i += 1
            continue
        out.append(_LATEX_SPECIAL_CHARS.get(ch, ch))
        i += 1
    return "".join(out)


def _unescape_math_inner(inner: str) -> str:
    return (
        inner.replace("\\_", "_")
        .replace("\\{", "{")
        .replace("\\}", "}")
        .replace("\\textbackslash{}", "\\")
    )


def _replace_unicode_math(text: str) -> str:
    if not text:
        return text
    out: List[str] = []
    for ch in text:
        out.append(_UNICODE_MATH_TO_LATEX.get(ch, ch))
    return "".join(out)


def _normalize_scientific_notation(text: str) -> str:
    """将 3·10^12 / 3x10^12 等写成行内公式，避免 ^ 被转成 \\textasciicircum{}。"""
    if not text:
        return text
    s = text
    s = re.sub(
        r"(?<!\$)(\d+)\s*[·⋅•×xX]\s*10\^(\d+)(?!\$)",
        r"$\1\\cdot 10^{\2}$",
        s,
    )
    s = re.sub(r"(?<![\w$])10\^(\d+)(?!\$)", r"$10^{\1}$", s)
    return s


def escape_latex(text: Any) -> str:
    """转义 LaTeX 特殊字符，保留 $...$ 行内公式与已有安全 LaTeX 命令。"""
    if text is None:
        return ""
    s = str(text).replace("\\$", "$")
    if not s.strip():
        return ""
    # 去掉替换字符与控制符
    s = re.sub(r"[\ufffd\u0000-\u0008\u000b\u000c\u000e-\u001f]", "", s)
    s = _normalize_windows_paths_for_latex(s)
    # 必须先规范化 ensuremath，再做 Unicode/$ 提升，否则会拆出 \\ensuremath{$...$\\}
    s = _normalize_ensuremath_to_inline_math(s)
    # 科学计数法须在 · → $\\cdot$ 之前处理，否则会变成 3$\\cdot$10\\textasciicircum{}12
    s = _normalize_scientific_notation(s)
    s = _replace_unicode_math(s)
    # 指标名中的下划线：在非数学片段中由 _escape_plain_latex 转义为 \_
    s = _promote_inline_math(s)
    if "$" not in s:
        return _escape_plain_latex(s)
    parts = re.split(r"(\$[^$\n]+\$)", s)
    return "".join(
        (
            f"${_unescape_math_inner(part[1:-1])}$"
            if part.startswith("$") and part.endswith("$")
            else _escape_plain_latex(part)
        )
        for part in parts
    )


def _normalize_lines(value: Any) -> List[str]:
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                parts = [f"{k}: {v}" for k, v in item.items() if v]
                lines.append("; ".join(parts) if parts else str(item))
            else:
                text = str(item).strip()
                if text:
                    lines.append(text)
        return lines
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            if val in (None, "", [], {}):
                continue
            if isinstance(val, (list, dict)):
                lines.append(f"{key}: {val}")
            else:
                lines.append(f"{key}: {val}")
        return lines
    text = str(value).strip() if value is not None else ""
    if not text:
        return []
    # 多行 markdown / 纯文本需按行拆分，才能识别 - / 1. 列表
    if "\n" in text:
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [text]


def _is_valid_reference_text(ref: str) -> bool:
    text = (ref or "").strip()
    if len(text) < 12:
        return False
    if any(marker in text for marker in _INVALID_REFERENCE_MARKERS):
        return False
    # 拒收「期刊名, 卷 (年), 页码」这类被当成题名的碎片（非论文标题）
    if re.match(
        r"^[A-Za-z][A-Za-z\s.&'\-]+,\s*\d+\s*\(\d{4}\)\s*,\s*\d+",
        text,
    ):
        return False
    return True


def _workflow_figure_block() -> str:
    """方法论章节：与模板一致的方法流程图占位。"""
    return (
        "\\begin{figure}[H]\n"
        "    \\centering\n"
        "    \\fbox{\n"
        "        \\parbox{0.8\\textwidth}{\n"
        "        \\centering\n"
        "        科学假设验证与研究计划构建流程示意图\n"
        "        }\n"
        "    }\n"
        "    \\caption{科学假设生成与研究计划构建流程示意图}\n"
        "    \\label{fig:workflow}\n"
        "\\end{figure}\n\n"
    )


def _experiment_design_table_block() -> str:
    """实验设计章节：与模板一致的 booktabs 表格。"""
    return (
        "\\begin{table}[H]\n"
        "\\centering\n"
        "\\caption{实验设计与评价指标}\n"
        "\\begin{tabular}{lccc}\n"
        "\\toprule\n"
        "方法 & 科学合理性 & 可验证性 & 数据支撑度 \\\\\n"
        "\\midrule\n"
        "基线方法 & 中 & 中 & 中 \\\\\n"
        "本文方法 & 高 & 高 & 高 \\\\\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\label{tab:experiment_design}\n"
        "\\end{table}\n\n"
    )


def _results_scaffold_block() -> str:
    """实验结果章节：与模板一致的公式与图表占位。"""
    return (
        "本部分通过可行性评分说明实验具有进一步验证价值：\n\n"
        "\\begin{equation}\n"
        "S = \\alpha S_{data} + \\beta S_{literature} + \\gamma S_{feasibility},\n"
        "\\end{equation}\n\n"
        "其中，$S_{data}$ 表示数据支撑度，$S_{literature}$ 表示文献支持度，"
        "$S_{feasibility}$ 表示实验可行性。当 $S > \\tau$ 时，认为该科学假设具备进一步实验验证价值。\n\n"
        "\\begin{figure}[H]\n"
        "    \\centering\n"
        "    \\fbox{\n"
        "        \\parbox{0.8\\textwidth}{\n"
        "        \\centering\n"
        "        实验结果或多模态分析结果示意图\n"
        "        }\n"
        "    }\n"
        "    \\caption{实验结果或多模态分析结果示意图}\n"
        "    \\label{fig:results}\n"
        "\\end{figure}\n\n"
        "\\begin{figure}[H]\n"
        "    \\centering\n"
        "    \\begin{subfigure}{0.45\\textwidth}\n"
        "        \\centering\n"
        "        \\fbox{\\parbox{0.9\\textwidth}{\\centering 文献图表}}\n"
        "        \\caption{原始论文图表}\n"
        "        \\label{fig:paper_a}\n"
        "    \\end{subfigure}\n"
        "    \\hfill\n"
        "    \\begin{subfigure}{0.45\\textwidth}\n"
        "        \\centering\n"
        "        \\fbox{\\parbox{0.9\\textwidth}{\\centering 图表解析结果}}\n"
        "        \\caption{图表结构化解析结果}\n"
        "        \\label{fig:paper_b}\n"
        "    \\end{subfigure}\n"
        "    \\caption{多模态文献图表信息展示}\n"
        "    \\label{fig:multimodal_paper_figures}\n"
        "\\end{figure}\n\n"
    )


def _parse_experiments_text(text: str) -> Dict[str, Any]:
    """将 Markdown/纯文本实验设计解析为结构化字段。"""
    parsed: Dict[str, Any] = {}
    if not text or not str(text).strip():
        return parsed
    raw = str(text)
    patterns = [
        ("baselines", r"(?i)(?:\*\*)?(?:baselines?|基线(?:对比|方法)?)(?:\*\*)?\s*[:：]\s*"),
        ("metrics", r"(?i)(?:\*\*)?(?:metrics?|评估指标)(?:\*\*)?\s*[:：]\s*"),
        ("experimental_setup", r"(?i)(?:\*\*)?(?:experimental\s*setup|实验(?:设置|条件))(?:\*\*)?\s*[:：]\s*"),
        ("ablation_study", r"(?i)(?:\*\*)?(?:ablation\s*study|消融实验)(?:\*\*)?\s*[:：]\s*"),
        ("validation_protocol", r"(?i)(?:\*\*)?(?:validation\s*protocol|验证方案)(?:\*\*)?\s*[:：]\s*"),
    ]
    for key, pattern in patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        start = match.end()
        next_start = len(raw)
        for _, other_pat in patterns:
            if other_pat == pattern:
                continue
            other = re.search(other_pat, raw[start:])
            if other:
                next_start = min(next_start, start + other.start())
        chunk = raw[start:next_start].strip()
        items = []
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:].strip())
            elif line.startswith("* "):
                items.append(line[2:].strip())
            elif line:
                items.append(line)
        parsed[key] = items if key in ("baselines", "metrics", "ablation_study") else chunk
    if not parsed:
        parsed["experimental_setup"] = raw
    return parsed


def _normalize_experiments_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    """若 baselines/metrics 等为空但 experimental_setup 含标签块，则拆分为结构化字段。"""
    exp = dict(value or {})
    setup = str(exp.get("experimental_setup") or "").strip()
    structured_empty = not any(
        str(exp.get(k) or "").strip()
        for k in ("baselines", "metrics", "ablation_study", "validation_protocol")
    )
    if setup and structured_empty and re.search(
        r"(?i)(?:baselines?|metrics?|experimental\s*setup|ablation|validation|基线|评估指标|消融|验证方案)\s*[:：]",
        setup,
    ):
        parsed = _parse_experiments_text(setup)
        for key, val in parsed.items():
            if val and not str(exp.get(key) or "").strip():
                exp[key] = val
        # setup 已拆出后，避免整段重复粘贴；保留纯 setup 段
        if parsed.get("experimental_setup"):
            exp["experimental_setup"] = parsed["experimental_setup"]
    return exp


def _format_itemize(lines: List[str]) -> str:
    if not lines:
        return ""
    body = "\n".join(
        f"    \\item {_markdown_to_latex_body(line) if '**' in line else escape_latex(line)}"
        for line in lines
    )
    return f"\\begin{{itemize}}\n{body}\n\\end{{itemize}}\n"


def _format_chapter_field(value: Any) -> str:
    """格式化普通章节字段，兼容 list / JSON 字符串。"""
    value = _coerce_chapter_json(value)
    if isinstance(value, list):
        return _format_itemize(_normalize_lines(value))
    if isinstance(value, dict):
        return _format_paragraph(value)
    text = str(value or "").replace("\\n", "\n")
    if text.strip().startswith("[") and text.strip().endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return _format_itemize(_normalize_lines(parsed))
        except json.JSONDecodeError:
            pass
    return _format_paragraph(text)


def _markdown_to_latex_body(text: str) -> str:
    """Markdown 行内 **粗体** → \\textbf{}，并转义其余 LaTeX 特殊字符。"""

    parts: List[str] = []
    i = 0
    while i < len(text):
        start = text.find("**", i)
        if start == -1:
            parts.append(escape_latex(text[i:]))
            break
        if start > i:
            parts.append(escape_latex(text[i:start]))
        end = text.find("**", start + 2)
        if end == -1:
            parts.append(escape_latex(text[start:]))
            break
        inner = text[start + 2 : end]
        parts.append(f"\\textbf{{{escape_latex(inner)}}}")
        i = end + 2
    return "".join(parts)


def _format_enumerate(lines: List[str]) -> str:
    items: List[str] = []
    for raw in lines:
        line = re.sub(r"^\d+\.\s*", "", raw.strip())
        if not line:
            continue
        body = _markdown_to_latex_body(line) if "**" in line else escape_latex(line)
        items.append(f"    \\item {body}")
    if not items:
        return ""
    return "\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n"


_BULLET_LINE_RE = re.compile(r"^[-*]\s+")
_NUMBERED_LINE_RE = re.compile(r"^\d+\.\s+")
_MD_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+")
_BLOCKQUOTE_LINE_RE = re.compile(r"^>\s?")


def _line_kind(line: str) -> str:
    """区分列表项 / 标题 / 引用 / 普通段落，避免散文被误标成 itemize。"""
    s = (line or "").strip()
    if not s:
        return "empty"
    if _MD_HEADING_LINE_RE.match(s):
        return "heading"
    if _BLOCKQUOTE_LINE_RE.match(s):
        return "quote"
    if _BULLET_LINE_RE.match(s):
        return "bullet"
    if _NUMBERED_LINE_RE.match(s):
        return "numbered"
    return "prose"


def _format_inline_line(line: str) -> str:
    return _markdown_to_latex_body(line) if "**" in line else escape_latex(line)


def _format_paragraph(value: Any) -> str:
    lines = _normalize_lines(value)
    if not lines:
        return ""
    if len(lines) == 1 and "###" not in lines[0]:
        return f"{_format_inline_line(lines[0])}\n\n"
    return _format_chapter_body(value)


def _format_text_block(text: str) -> str:
    """将一段纯文本格式化为段落 / itemize / enumerate。

    仅真实 `-`/`*` 列表与 `1.` 编号列表使用条目符号；普通多行散文保持段落，
    避免「每行一个圆点」的阅读体验。
    """
    lines = _normalize_lines(text)
    if not lines:
        return ""

    parts: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        kind = _line_kind(lines[i])
        if kind == "bullet":
            group: List[str] = []
            while i < n and _line_kind(lines[i]) == "bullet":
                group.append(_BULLET_LINE_RE.sub("", lines[i], count=1).strip())
                i += 1
            parts.append(_format_itemize(group))
        elif kind == "numbered":
            group = []
            while i < n and _line_kind(lines[i]) == "numbered":
                group.append(lines[i])
                i += 1
            parts.append(_format_enumerate(group))
        elif kind == "heading":
            title = _MD_HEADING_LINE_RE.sub("", lines[i]).strip()
            if title:
                parts.append(f"\\paragraph{{{escape_latex(title)}}}\n\n")
            i += 1
        elif kind == "quote":
            body = _BLOCKQUOTE_LINE_RE.sub("", lines[i]).strip()
            if body:
                parts.append(f"\\textit{{{_format_inline_line(body)}}}\n\n")
            i += 1
        else:
            while i < n and _line_kind(lines[i]) == "prose":
                parts.append(f"{_format_inline_line(lines[i])}\n\n")
                i += 1
    return "".join(parts)


def _format_chapter_body(value: Any) -> str:
    """章节正文：支持 ### 小节标题 → LaTeX \\subsection（不改变主 section 结构）。"""
    if value is None:
        return ""
    if isinstance(value, dict):
        parts: List[str] = []
        body = value.get("body") or value.get("content") or ""
        if body:
            parts.append(_format_chapter_body(body))
        for sub in value.get("subsections") or []:
            if isinstance(sub, dict):
                title = sub.get("title") or sub.get("name") or "小节"
                content = sub.get("content") or sub.get("body") or ""
                parts.append(f"\\subsection{{{escape_latex(title)}}}\n\n")
                parts.append(_format_chapter_body(content))
        return "".join(parts) if parts else _format_itemize(_normalize_lines(value))

    text = str(value).strip()
    if not text:
        return ""

    if "###" not in text:
        return _format_text_block(text)

    parts: List[str] = []
    blocks = re.split(r"(?m)^###\s+", text)
    if blocks and blocks[0].strip():
        intro = blocks[0].strip()
        if intro:
            parts.append(_format_text_block(intro))
    for block in blocks[1:]:
        if not block.strip():
            continue
        lines = block.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        parts.append(f"\\subsection{{{escape_latex(title)}}}\n\n")
        if body:
            parts.append(_format_text_block(body))
    return "".join(parts)


def _format_experiments(value: Any) -> str:
    value = _coerce_chapter_json(value)
    if isinstance(value, str):
        value = _parse_experiments_text(value)

    if not isinstance(value, dict):
        return _format_paragraph(value)

    value = _normalize_experiments_dict(value)

    parts: List[str] = []
    setup = value.get("experimental_setup", "")
    if setup:
        if isinstance(setup, list):
            parts.append(_format_itemize(_normalize_lines(setup)))
        else:
            parts.append(_format_paragraph(setup))

    baselines = value.get("baselines", [])
    if baselines:
        parts.append("\\subsection{基线对比}\n\n")
        parts.append(_format_itemize(_normalize_lines(baselines)))

    metrics = value.get("metrics", [])
    if metrics:
        parts.append("\\subsection{评估指标}\n\n")
        parts.append(_format_itemize(_normalize_lines(metrics)))

    ablation = value.get("ablation_study", [])
    if ablation:
        parts.append("\\subsection{消融实验}\n\n")
        parts.append(_format_itemize(_normalize_lines(ablation)))

    protocol = value.get("validation_protocol", "")
    if protocol:
        parts.append("\\subsection{验证方案}\n\n")
        if isinstance(protocol, list):
            parts.append(_format_itemize(_normalize_lines(protocol)))
        else:
            parts.append(_format_paragraph(protocol))

    if parts:
        return "".join(parts)
    return _format_paragraph(str(value))


def _format_results(value: Any, *, include_scaffold: bool = False) -> str:
    """格式化实验结果章节。

    include_scaffold=False（默认）：不再注入模板公式/\\fbox 占位图；
    真实图表由后续 figures 节的沙箱/实验图承担。
    """
    value = _coerce_chapter_json(value)
    if isinstance(value, str):
        body = _format_paragraph(value)
        return body + (_results_scaffold_block() if include_scaffold else "")

    if not isinstance(value, dict):
        body = _format_paragraph(value)
        return body + (_results_scaffold_block() if include_scaffold else "")

    parts: List[str] = []
    mapping = [
        ("actual_results", "实际结果"),
        ("simulated_results", "模拟结果"),
        ("expected_results", "预期结果"),
        ("discussion", "结果分析与讨论"),
        ("limitations", "局限性"),
    ]
    for key, label in mapping:
        content = value.get(key)
        if not content:
            continue
        parts.append(f"\\subsection{{{label}}}\n\n")
        parts.append(_format_paragraph(content))

    warnings = value.get("warnings", [])
    if warnings:
        parts.append("\\subsection{结果说明}\n\n")
        parts.append(_format_itemize(_normalize_lines(warnings)))

    if parts:
        body = "".join(parts)
    else:
        body = _format_paragraph("暂无实验结果，待完成实验后补充。")
    if include_scaffold:
        body += _results_scaffold_block()
    return body


def _load_template_preamble(template_dir: Path) -> str:
    template_path = template_dir / TEMPLATE_TEX
    if not template_path.exists():
        raise FileNotFoundError(f"LaTeX 模板不存在: {template_path}")

    content = template_path.read_text(encoding="utf-8")
    marker = r"\begin{document}"
    idx = content.find(marker)
    if idx == -1:
        raise ValueError(f"模板缺少 \\begin{{document}}: {template_path}")

    preamble = content[:idx].rstrip()
    preamble = re.sub(
        r"\\title\{[\s\S]*?\}\s*\\author\{[\s\S]*?\}\s*$",
        "",
        preamble,
        count=1,
    ).rstrip()
    preamble = preamble.replace(
        r"\usepackage[UTF8]{ctex}",
        r"\usepackage[UTF8,fontset=fandol]{ctex}",
    )
    if r"\PassOptionsToPackage{numbers,sort&compress}{natbib}" not in preamble:
        preamble = preamble.replace(
            r"\usepackage{iclr2024_conference,times}",
            r"\PassOptionsToPackage{numbers,sort&compress}{natbib}"
            "\n\\usepackage{iclr2024_conference,times}"
            "\n\\setcitestyle{numbers,square,sort&compress}",
        )
    elif r"\setcitestyle{numbers" not in preamble:
        preamble = preamble.replace(
            r"\usepackage{iclr2024_conference,times}",
            r"\usepackage{iclr2024_conference,times}"
            "\n\\setcitestyle{numbers,square,sort&compress}",
        )
    return preamble + "\n"


def _coerce_chapter_json(value: Any) -> Any:
    """将 DB 中 JSON 字符串章节还原为 dict/list。"""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _bibtex_field_value(text: Any) -> str:
    """BibTeX 字段值：去除错误 LaTeX 转义，保护花括号。"""
    s = str(text or "").strip()
    if not s:
        return ""
    for old, new in (
        (r"\textbackslash{}", "\\"),
        (r"\_", "_"),
        (r"\&", "&"),
        (r"\%", "%"),
        (r"\#", "#"),
        (r"\$", "$"),
    ):
        s = s.replace(old, new)
    return s.replace("{", "\\{").replace("}", "\\}")


def _is_author_initial(part: str) -> bool:
    p = part.strip().rstrip(".")
    return len(p) <= 2 and p.isalpha()


def _split_comma_separated_authors(raw: str) -> List[str]:
    """拆分逗号分隔作者，保留「姓, 名缩写」为一位作者。"""
    bits = [p.strip() for p in raw.split(",") if p.strip()]
    if len(bits) <= 1:
        return bits
    merged: List[str] = []
    i = 0
    while i < len(bits):
        if i + 1 < len(bits) and _is_author_initial(bits[i + 1]):
            merged.append(f"{bits[i]}, {bits[i + 1]}")
            i += 2
        else:
            merged.append(bits[i])
            i += 1
    return merged


def _normalize_bib_authors(authors: Any) -> str:
    """BibTeX author 字段：Author1 and Author2。"""
    if isinstance(authors, list):
        parts = [str(a).strip() for a in authors if str(a).strip()]
    else:
        raw = str(authors or "").strip()
        if not raw or raw.lower() in ("unknown", "未知作者"):
            return ""
        if re.search(r"\s+and\s+", raw, flags=re.I):
            parts = [p.strip() for p in re.split(r"\s+and\s+", raw, flags=re.I) if p.strip()]
        elif ";" in raw:
            parts = [p.strip() for p in raw.split(";") if p.strip()]
        else:
            parts = _split_comma_separated_authors(raw)
    if not parts:
        return ""
    return " and ".join(_bibtex_field_value(p) for p in parts)


def clean_reference_text(text: Any) -> str:
    """去掉 HTML / 多余空白，避免 <i>Planck</i> 等脏标题进入书目。"""
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"(?i)</?(i|em|b|strong|u|sup|sub|span|font|a|p|br|div)[^>]*>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    # 去掉误重复的类型标记 {[J]} / [J][J]
    s = re.sub(r"(?:\{\[([A-Z](?:/[A-Z]+)?)\]\}\s*)+", r"[\1]", s)
    s = re.sub(r"(?:\[([A-Z](?:/[A-Z]+)?)\]\s*){2,}", r"[\1]", s)
    return s


def parse_reference_line_to_item(line: str) -> Dict[str, str]:
    """将参考文献行解析为结构化字段（兼容 GB/T 与 Authors. Title (year)）。"""
    text = clean_reference_text(line)
    if not text:
        return {}

    doi = ""
    m_doi = re.search(r"\.?\s*DOI:\s*(\S+)\s*$", text, flags=re.I)
    if m_doi:
        doi = m_doi.group(1).rstrip(".")
        text = text[: m_doi.start()].strip()

    url = ""
    m_url = re.search(r"\.?\s*(https?://\S+)\s*$", text)
    if m_url:
        url = m_url.group(1).rstrip(".")
        text = text[: m_url.start()].strip()

    year = ""
    m_year = re.search(r"\((\d{4})\)\s*$", text)
    if not m_year:
        # GB/T: Journal, 2020. 或 北京: 出版社, 2018.
        m_year = re.search(r",\s*(\d{4})\.?\s*$", text)
    if m_year:
        year = m_year.group(1)
        text = text[: m_year.start()].strip().rstrip(".,;；")

    # 去掉末尾类型标 [J] / {[J]}
    text = re.sub(r"(?:\{\[([A-Z](?:/[A-Z]+)?)]\}|\[([A-Z](?:/[A-Z]+)?)])\s*$", "", text).strip()

    authors = ""
    title = text
    if ". " in text:
        head, tail = text.split(". ", 1)
        if tail and len(tail) >= 8:
            authors = head.strip()
            title = tail.strip()

    title = clean_reference_text(title)
    out = {"title": title, "authors": authors, "year": year, "doi": doi, "url": url}
    return {k: v for k, v in out.items() if v}


def _reference_item_key(item: Dict[str, Any]) -> str:
    doi = str(item.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = clean_reference_text(item.get("title") or item.get("paper_title") or "").lower()
    year = str(item.get("year") or item.get("publication_year") or "").strip()
    if title:
        return f"title:{title}|{year}" if year else f"title:{title}"
    return ""


def _structured_reference_items(
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """合并 citation_map / verified_references 并去重。"""
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(verified_references or []) + list(citation_map or []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["title"] = clean_reference_text(item.get("title") or item.get("paper_title") or "")
        if item.get("paper_title"):
            item["paper_title"] = clean_reference_text(item.get("paper_title"))
        if item.get("journal"):
            item["journal"] = clean_reference_text(item.get("journal"))
        if isinstance(item.get("authors"), str):
            item["authors"] = clean_reference_text(item.get("authors"))
        elif isinstance(item.get("authors"), list):
            item["authors"] = [clean_reference_text(a) for a in item["authors"] if clean_reference_text(a)]
        if not item["title"] or not _is_valid_reference_text(item["title"]):
            continue
        key = _reference_item_key(item)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(item)
    return merged


def format_reference_items_as_gbt7714_lines(
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """统一出口：结构化文献 → GB/T 7714 文本行（报告注入/合规回填共用）。"""
    refs: List[str] = []
    seen_line: set[str] = set()
    for item in _structured_reference_items(citation_map, verified_references):
        line = _format_reference_gbt7714(item)
        if not line:
            continue
        key = line.lower()
        if key in seen_line:
            continue
        seen_line.add(key)
        refs.append(line)
    return refs


def _reference_item_to_bib_fields(item: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """结构化文献 → BibTeX entry 类型与字段。"""
    title = _bibtex_field_value(item.get("title") or item.get("paper_title") or "")
    authors = _normalize_bib_authors(item.get("authors"))
    url = str(item.get("source_url") or item.get("url") or "").strip()
    year = str(item.get("year") or item.get("publication_year") or "").strip()
    doi = _bibtex_field_value(item.get("doi") or "")
    journal = _bibtex_field_value(item.get("journal") or "")

    fields: Dict[str, str] = {"title": title}
    if authors:
        fields["author"] = authors
    if year:
        fields["year"] = year
    if doi:
        fields["doi"] = doi
    if url:
        fields["url"] = _bibtex_field_value(url)
    if journal:
        fields["journal"] = journal

    is_arxiv = "arxiv" in url.lower() or str(item.get("source") or "").lower() == "arxiv"
    if is_arxiv:
        eprint = str(item.get("external_id") or url.rstrip("/").split("/")[-1] or "").strip()
        if eprint:
            fields["eprint"] = _bibtex_field_value(eprint)
            fields["archivePrefix"] = "arXiv"
        if not journal:
            fields["journal"] = "arXiv preprint"

    entry_type = "article" if journal or is_arxiv or doi else "misc"
    if entry_type == "misc" and not fields.get("journal"):
        how = journal or ("arXiv preprint" if is_arxiv else "")
        if how:
            fields["howpublished"] = how
    return entry_type, fields

def _build_author_block(project_info: Dict[str, Any]) -> str:
    project_name = escape_latex(project_info.get("title") or project_info.get("name") or "AI Scientist 科研项目")
    domain = escape_latex(project_info.get("research_domain") or "智能科研助手")
    return (
        "AI Scientist 系统 \\\\\n"
        f"{project_name} \\\\\n"
        f"{domain} \\\\\n"
        "\\texttt{generated@aisci.local}"
    )


def _make_bib_key(index: int, hint: str = "") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", hint or "")
    if cleaned:
        return cleaned[:40]
    return f"ref{index}"


def _build_references_bib(
    chapters: Dict[str, Any],
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[str]]:
    entries: List[str] = []
    keys: List[str] = []
    seen_keys: set[str] = set()
    seen_item_keys: set[str] = set()

    def add_entry(entry_type: str, key: str, fields: Dict[str, str]) -> None:
        if not fields.get("title") and not fields.get("note"):
            return
        base_key = key
        suffix = 1
        while key in seen_keys:
            suffix += 1
            key = f"{base_key}{suffix}"
        seen_keys.add(key)
        keys.append(key)
        field_lines = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items() if v)
        entries.append(f"@{entry_type}{{{key},\n  {field_lines}\n}}")

    idx = 1
    structured = _structured_reference_items(citation_map, verified_references)
    for item in structured:
        item_key = _reference_item_key(item)
        if item_key:
            seen_item_keys.add(item_key)
        key = _make_bib_key(idx, item.get("external_id") or item.get("doi") or item.get("title", "")[:20])
        entry_type, fields = _reference_item_to_bib_fields(item)
        add_entry(entry_type, key, fields)
        idx += 1

    # 仅当无结构化文献时，尝试从 chapters.references 文本行解析
    if not structured:
        refs = chapters.get("references", [])
        if isinstance(refs, list):
            for ref in refs:
                if not ref or not isinstance(ref, str) or not _is_valid_reference_text(ref):
                    continue
                parsed = parse_reference_line_to_item(ref)
                if parsed.get("title"):
                    item_key = _reference_item_key(parsed)
                    if item_key and item_key in seen_item_keys:
                        continue
                    if item_key:
                        seen_item_keys.add(item_key)
                    key = _make_bib_key(idx, parsed.get("doi") or parsed.get("title", "")[:20])
                    entry_type, fields = _reference_item_to_bib_fields(parsed)
                    add_entry(entry_type, key, fields)
                    idx += 1
                else:
                    key = _make_bib_key(idx, ref[:24])
                    add_entry("misc", key, {"note": _bibtex_field_value(ref)})
                    idx += 1

    bib_content = "\n\n".join(entries)
    return bib_content, keys


def _format_authors_for_citation(authors: Any) -> str:
    """GB/T 7714 作者列：3 人以内全列，超过 3 人加「等」/ et al."""
    if isinstance(authors, list):
        parts = [str(a).strip() for a in authors if str(a).strip()]
    else:
        raw = str(authors or "").strip()
        if not raw or raw.lower() in ("unknown", "未知作者"):
            return ""
        if re.search(r"\s+and\s+", raw, flags=re.I):
            parts = [p.strip() for p in re.split(r"\s+and\s+", raw, flags=re.I) if p.strip()]
        elif ";" in raw:
            parts = [p.strip() for p in raw.split(";") if p.strip()]
        else:
            parts = _split_comma_separated_authors(raw)
    if not parts:
        return ""
    has_cjk = any(re.search(r"[\u4e00-\u9fff]", p) for p in parts)
    if len(parts) > 3:
        parts = parts[:3] + (["等"] if has_cjk else ["et al."])
    return ", ".join(parts)


def _reference_type_marker(item: Dict[str, Any]) -> str:
    """文献类型标识：M 专著 / J 期刊 / J/OL 电子期刊 / EB/OL 电子资源。

    注意：有 DOI 或 doi.org 链接的正式论文应标 [J]，不能仅因存在网页 URL
    就误标为 [EB/OL]（检索源常把期刊论文的 landing page 填进 source_url）。
    """
    if item.get("publisher") or item.get("publisher_location"):
        return "M"
    url = str(item.get("source_url") or item.get("url") or "").lower()
    source = str(item.get("source") or "").lower()
    doi = str(item.get("doi") or "").strip()
    if "arxiv" in url or source == "arxiv":
        return "J/OL"
    if item.get("journal") or doi or "doi.org/" in url:
        return "J"
    if url:
        return "EB/OL"
    return "J"


def _format_reference_gbt7714(item: Dict[str, Any]) -> str:
    """
    格式化为 GB/T 7714 参考文献条目（用于 \\bibitem 正文）。
    示例：姜启源, 谢金星, 叶俊. 数学模型[M]. 北京: 高等教育出版社, 2018.
    类型标使用 [M]/[J]（不用花括号），以便 escape_latex 后仍可读。
    """
    note = clean_reference_text(item.get("note") or "")
    title = clean_reference_text(item.get("title") or item.get("paper_title") or "").rstrip(".")
    if not title:
        return note

    authors = _format_authors_for_citation(item.get("authors"))
    marker = _reference_type_marker(item)
    year = str(item.get("year") or item.get("publication_year") or "").strip()
    journal = clean_reference_text(item.get("journal") or "")
    publisher = clean_reference_text(item.get("publisher") or "")
    pub_place = clean_reference_text(item.get("publisher_location") or item.get("address") or "")
    doi = str(item.get("doi") or "").strip()
    url = str(item.get("source_url") or item.get("url") or "").strip()

    segments: List[str] = []
    if authors:
        authors = authors.rstrip().rstrip(".")
        segments.append(f"{authors}. ")
    # 不用 {[M]}：经 escape_latex 会变成 \{[M]\}
    segments.append(f"{title}[{marker}]")

    if marker == "M" and (pub_place or publisher):
        place_pub = pub_place
        if publisher:
            place_pub = f"{pub_place}: {publisher}" if pub_place else publisher
        if year:
            place_pub = f"{place_pub}, {year}" if place_pub else year
        if place_pub:
            segments.append(f". {place_pub}")
    else:
        source = journal
        if not source and "arxiv" in url.lower():
            eprint = str(item.get("external_id") or url.rstrip("/").split("/")[-1] or "").strip()
            source = f"arXiv:{eprint}" if eprint else "arXiv preprint"
        if source:
            segments.append(f". {source}" + (f", {year}" if year else ""))
        elif year:
            segments.append(f". {year}")

    if doi:
        segments.append(f". DOI: {doi}")
    elif url and marker in ("J/OL", "EB/OL"):
        segments.append(f". {url}")

    return "".join(segments)


def _collect_bibliography_items(
    chapters: Dict[str, Any],
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """合并结构化文献与 chapters.references；有 structured 时不再二次解析文本行。"""
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add(item: Dict[str, Any]) -> None:
        if not item.get("title") and not item.get("paper_title") and not item.get("note"):
            return
        title = clean_reference_text(item.get("title") or item.get("paper_title") or "")
        if title:
            item = dict(item)
            item["title"] = title
            if not _is_valid_reference_text(title):
                return
        key = _reference_item_key(item) if title else f"note:{clean_reference_text(item.get('note'))}"
        if key:
            if key in seen:
                return
            seen.add(key)
        items.append(item)

    structured = _structured_reference_items(citation_map, verified_references)
    for item in structured:
        _add(dict(item))

    # 与 _build_references_bib 对齐：已有结构化文献时，不再 parse 章节文本（避免 GB/T 二次解析出重复坏条目）
    if structured:
        return items

    refs = chapters.get("references", [])
    if isinstance(refs, list):
        for ref in refs:
            if not ref or not isinstance(ref, str) or not _is_valid_reference_text(ref):
                continue
            parsed = parse_reference_line_to_item(ref)
            if parsed.get("title"):
                _add(parsed)
            else:
                _add({"note": clean_reference_text(ref)})

    return items


def _build_thebibliography_section(items: List[Dict[str, Any]]) -> str:
    """生成 \\begin{thebibliography}…\\bibitem{refN}…\\end{thebibliography}。"""
    if not items:
        return (
            "\\begin{thebibliography}{99}\n"
            "\\bibitem{ref1} 暂无已验证参考文献。\n"
            "\\end{thebibliography}\n"
        )
    label_width = str(min(max(len(items), 9), 99))
    lines = [f"\\begin{{thebibliography}}{{{label_width}}}"]
    for idx, item in enumerate(items, start=1):
        body = escape_latex(_format_reference_gbt7714(item))
        lines.append(f"\\bibitem{{ref{idx}}} {body}")
    lines.append("\\end{thebibliography}\n")
    return "\n".join(lines)


def _resolve_plot_source_path(plot: Dict[str, Any], output_dir: Path, target: Path) -> Optional[Path]:
    """解析图表源文件：绝对路径 / 相对路径 / /storage/charts URL / 已复制到 figures/。"""
    candidates: List[Path] = []
    for key in ("path", "file_path"):
        raw = str(plot.get(key) or "").strip()
        if raw:
            candidates.append(Path(raw))
    rel = str(plot.get("relative_path") or "").strip().replace("\\", "/")
    if rel:
        candidates.append(output_dir / rel)
        candidates.append(Path(rel))
    url = str(plot.get("url") or "").strip().replace("\\", "/")
    if url.startswith("/storage/charts/"):
        name = url.rsplit("/", 1)[-1]
        if name:
            try:
                from app.services.report_charts_service import get_public_charts_dir

                candidates.append(get_public_charts_dir() / name)
            except Exception:
                candidates.append(Path(__file__).resolve().parents[2] / "storage" / "charts" / name)
    # 报告目录里已有同名图（上次复制残留）也可直接用
    candidates.append(target)

    for cand in candidates:
        try:
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
        except OSError:
            continue
    return None


def _prepare_figure_files(
    plots: Optional[List[Dict[str, Any]]],
    output_dir: Path,
) -> List[Dict[str, str]]:
    if not plots:
        return []

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    prepared: List[Dict[str, str]] = []

    for i, plot in enumerate(plots):
        plot_id = plot.get("plot_id") or f"chart_{i + 1}"
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(plot_id))
        filename = f"{safe_id}.png"
        target = figures_dir / filename

        if plot.get("base64") and not _resolve_plot_source_path(plot, output_dir, target):
            try:
                raw = base64.b64decode(plot["base64"])
                target.write_bytes(raw)
            except Exception as exc:
                logger.warning(f"图表 Base64 解码失败 [{plot_id}]: {exc}")
                continue
        else:
            src = _resolve_plot_source_path(plot, output_dir, target)
            if src is None:
                logger.warning("跳过缺失图表文件 [%s]", plot_id)
                continue
            if src.resolve() != target.resolve():
                shutil.copy2(src, target)

        if not target.is_file() or target.stat().st_size <= 0:
            continue

        prepared.append(
            {
                "relative_path": f"figures/{filename}",
                "title": plot.get("caption") or plot.get("description") or plot.get("title") or f"Chart {i + 1}",
                "label": f"fig:{safe_id}",
            }
        )

    return prepared


def _build_figures_section(figures: List[Dict[str, str]]) -> str:
    """紧凑输出实验图表，避免 figure[H] + 大图导致半页空白。"""
    if not figures:
        return ""

    parts = [
        "\\subsection{实验图表}\n\n",
        "% 使用 minipage + captionof，避免 float[H] 在页末强行推图造成大片留白\n",
        "\\begingroup\\captionsetup{font=small,skip=4pt}\n",
    ]

    def _one_panel(fig: Dict[str, str], width: str, max_h: str) -> str:
        return (
            f"\\begin{{minipage}}[t]{{{width}}}\n"
            "    \\centering\n"
            f"    \\includegraphics[width=\\linewidth,height={max_h},keepaspectratio]"
            f"{{{fig['relative_path']}}}\n"
            f"    \\captionof{{figure}}{{{escape_latex(fig['title'])}}}\n"
            f"    \\label{{{fig['label']}}}\n"
            "\\end{minipage}\n"
        )

    i = 0
    n = len(figures)
    while i < n:
        left = figures[i]
        # 两张并排；最后一张单独时略加宽但仍限高
        if i + 1 < n:
            right = figures[i + 1]
            parts.append("\\noindent\n")
            parts.append(_one_panel(left, "0.48\\textwidth", "0.30\\textheight"))
            parts.append("\\hfill\n")
            parts.append(_one_panel(right, "0.48\\textwidth", "0.30\\textheight"))
            parts.append("\\par\\vspace{0.8em}\n\n")
            i += 2
        else:
            parts.append("\\noindent\n")
            parts.append(_one_panel(left, "0.72\\textwidth", "0.32\\textheight"))
            parts.append("\\par\\vspace{0.6em}\n\n")
            i += 1

    parts.append("\\endgroup\n\n")
    return "".join(parts)


def build_latex_document(
    result: Dict[str, Any],
    project_info: Optional[Dict[str, Any]] = None,
    plots: Optional[List[Dict[str, Any]]] = None,
    figure_files: Optional[List[Dict[str, str]]] = None,
    template_dir: Optional[Path] = None,
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """从结构化报告结果生成完整 LaTeX 源码。"""
    template_dir = template_dir or get_latex_template_dir()
    preamble = _load_template_preamble(template_dir)

    project_info = project_info or {}
    chapters = result.get("chapters", {}) or {}

    title = escape_latex(result.get("paper_title") or result.get("title") or "科学假设与研究计划")
    abstract = escape_latex(result.get("paper_abstract") or "")
    author = _build_author_block(project_info)

    # 模板中的 \\fbox / 公式脚手架仅为写法示意，导出时不注入；真实图见 figures 节
    body_parts: List[str] = [
        "\\maketitle\n\n",
        "\\begin{abstract}\n",
        abstract,
        "\n\\end{abstract}\n\n",
        "\\section{待研究问题}\n\n",
        _format_chapter_field(chapters.get("problem_statement", "")),
        "\\section{解决思路}\n\n",
        _format_chapter_field(chapters.get("rationale", "")),
        "\\section{必要的技术手段}\n\n",
        _format_chapter_field(chapters.get("technical_details", "")),
        "\\section{数据集}\n\n",
        _format_chapter_field(chapters.get("datasets", "")),
        "\\subsection{历史数据}\n\n",
        _format_chapter_field(chapters.get("source", "")),
        "\\subsection{目标数据}\n\n",
        _format_chapter_field(chapters.get("target", "")),
        "\\section{方法论}\n\n",
        _format_chapter_field(chapters.get("methods", "")),
        "\\section{实验设计}\n\n",
        _format_experiments(chapters.get("experiments", "")),
        "\\section{实验结果}\n\n",
        _format_results(chapters.get("results", ""), include_scaffold=False),
    ]

    if figure_files:
        body_parts.append(_build_figures_section(figure_files))

    bib_items = _collect_bibliography_items(chapters, citation_map, verified_references)
    body_parts.append(_build_thebibliography_section(bib_items))

    body = "".join(body_parts)
    return (
        f"{preamble}\n"
        f"\\title{{{title}}}\n\n"
        f"\\author{{\n{author}\n}}\n\n"
        f"\\begin{{document}}\n\n"
        f"{body}\n"
        f"\\end{{document}}\n"
    )


def copy_template_assets(output_dir: Path, template_dir: Optional[Path] = None) -> None:
    template_dir = template_dir or get_latex_template_dir()
    for name in TEMPLATE_ASSETS:
        src = template_dir / name
        if src.exists():
            shutil.copy2(src, output_dir / name)


def _texlive_xelatex_candidates() -> List[str]:
    """枚举常见 TeX Live / MiKTeX 安装路径下的 xelatex。"""
    candidates: List[str] = []

    explicit = os.environ.get("XELATEX_PATH", "").strip()
    if explicit:
        candidates.append(explicit)

    texlive_roots = [
        os.environ.get("TEXLIVE_ROOT", "").strip(),
        r"C:\texlive",
        r"D:\texlive",
        r"D:\Software\texlive",
        os.path.expanduser(r"~\texlive"),
    ]
    for root in texlive_roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            year_dirs = sorted(
                (p for p in Path(root).iterdir() if p.is_dir()),
                key=lambda p: p.name,
                reverse=True,
            )
        except OSError:
            continue
        for year_dir in year_dirs:
            candidates.append(str(year_dir / "bin" / "windows" / "xelatex.exe"))

    candidates.extend(
        [
            r"C:\texlive\2026\bin\windows\xelatex.exe",
            r"C:\texlive\2025\bin\windows\xelatex.exe",
            r"C:\texlive\2024\bin\windows\xelatex.exe",
            r"C:\texlive\2023\bin\windows\xelatex.exe",
            r"D:\Software\texlive\2026\bin\windows\xelatex.exe",
            r"D:\Software\texlive\2025\bin\windows\xelatex.exe",
            r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
            r"C:\Program Files (x86)\MiKTeX\miktex\bin\x64\xelatex.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe"),
        ]
    )

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TeXLive2026",
            ) as key:
                uninstall, _ = winreg.QueryValueEx(key, "UninstallString")
                # e.g. "D:\Software\texlive\2026\tlpkg\installer\uninst.bat"
                tex_root = Path(uninstall.strip('"')).parents[2]
                candidates.append(str(tex_root / "bin" / "windows" / "xelatex.exe"))
        except OSError:
            pass

    return candidates


def _find_xelatex() -> Optional[str]:
    cmd = os.environ.get("XELATEX_COMMAND", "xelatex")
    path = shutil.which(cmd)
    if path:
        return path
    for candidate in _texlive_xelatex_candidates():
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _find_bibtex(xelatex_path: Optional[str] = None) -> Optional[str]:
    path = shutil.which("bibtex")
    if path:
        return path
    if xelatex_path:
        sibling = Path(xelatex_path).with_name("bibtex.exe")
        if sibling.exists():
            return str(sibling)
    return None


def _texlive_subprocess_env(xelatex_path: str) -> Dict[str, str]:
    """为 TeX Live 子进程准备环境变量（修复 Windows fontconfig/kpathsea）。"""
    env = os.environ.copy()
    tex_root = Path(xelatex_path).resolve().parents[2]
    texmf_var = tex_root / "texmf-var"
    texmf_var.mkdir(parents=True, exist_ok=True)
    (texmf_var / "fonts" / "cache").mkdir(parents=True, exist_ok=True)
    env["TEXMFVAR"] = str(texmf_var)
    env["TEXMFSYSVAR"] = str(texmf_var)
    return env


def compile_latex_to_pdf(
    work_dir: Path,
    tex_filename: str = "report.tex",
    timeout: int = 120,
) -> Dict[str, Any]:
    xelatex = _find_xelatex()
    if not xelatex:
        return {
            "success": False,
            "pdf_path": None,
            "warning": "未找到 XeLaTeX，请安装 TeX Live 或 MiKTeX 并将 xelatex 加入 PATH",
        }

    bibtex = _find_bibtex(xelatex)
    tex_path = work_dir / tex_filename
    pdf_path = work_dir / "report.pdf"

    if not tex_path.exists():
        return {
            "success": False,
            "pdf_path": None,
            "warning": f"LaTeX 源文件不存在: {tex_path}",
        }

    commands: List[List[str]] = [
        [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_filename],
    ]
    tex_source = tex_path.read_text(encoding="utf-8", errors="replace")
    use_bibtex = (
        bibtex
        and (work_dir / "references.bib").exists()
        and "\\bibliography{" in tex_source
    )
    if use_bibtex:
        commands.extend(
            [
                [bibtex, "report"],
                [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_filename],
            ]
        )
    commands.append([xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_filename])

    log_chunks: List[str] = []
    tex_env = _texlive_subprocess_env(xelatex)
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=tex_env,
            )
            log_chunks.append(f"$ {' '.join(cmd)}\n{proc.stdout}\n{proc.stderr}")
            if proc.returncode != 0:
                log_file = work_dir / "latex_compile.log"
                log_file.write_text("\n\n".join(log_chunks), encoding="utf-8")
                return {
                    "success": False,
                    "pdf_path": None,
                    "warning": f"LaTeX 编译失败（{' '.join(cmd)}），详见 {log_file}",
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "pdf_path": None,
                "warning": f"LaTeX 编译超时（>{timeout}s）",
            }
        except Exception as exc:
            return {
                "success": False,
                "pdf_path": None,
                "warning": f"LaTeX 编译异常: {exc}",
            }

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        return {"success": True, "pdf_path": str(pdf_path), "warning": None}

    return {
        "success": False,
        "pdf_path": None,
        "warning": "LaTeX 编译完成但未生成 report.pdf",
    }


def export_report_via_latex(
    result: Dict[str, Any],
    output_dir: str,
    project_info: Optional[Dict[str, Any]] = None,
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    生成 LaTeX 源码并编译 PDF（仅 latex_template，无 Markdown 回退）。
    """
    work_dir = Path(output_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    template_dir = get_latex_template_dir()
    copy_template_assets(work_dir, template_dir)

    chapters = result.get("chapters", {}) or {}
    bib_file: Optional[str] = None

    figure_files = _prepare_figure_files(result.get("plots"), work_dir)
    latex_content = build_latex_document(
        result=result,
        project_info=project_info,
        plots=result.get("plots"),
        figure_files=figure_files,
        template_dir=template_dir,
        citation_map=citation_map,
        verified_references=verified_references,
    )

    tex_path = work_dir / "report.tex"
    tex_path.write_text(latex_content, encoding="utf-8")

    stale_bib = work_dir / "references.bib"
    if stale_bib.exists() and "\\bibliography{" not in latex_content:
        try:
            stale_bib.unlink()
        except OSError:
            pass

    compile_result = compile_latex_to_pdf(work_dir)
    if compile_result.get("success"):
        return {
            "success": True,
            "latex_content": latex_content,
            "tex_file": str(tex_path),
            "bib_file": bib_file,
            "pdf_path": compile_result.get("pdf_path"),
            "pdf_success": True,
            "warning": None,
            "export_method": "latex",
        }

    warning = compile_result.get("warning") or "LaTeX PDF 生成失败"
    logger.warning(warning)

    return {
        "success": False,
        "latex_content": latex_content,
        "tex_file": str(tex_path),
        "bib_file": bib_file,
        "pdf_path": None,
        "pdf_success": False,
        "warning": warning,
        "export_method": "latex",
    }


def get_reports_storage_dir() -> Path:
    """报告文件根目录 backend/storage/reports。"""
    return Path(__file__).resolve().parents[2] / "storage" / "reports"
