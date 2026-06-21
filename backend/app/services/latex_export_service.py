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


def get_latex_template_dir() -> Path:
    env_path = os.environ.get("LATEX_TEMPLATE_DIR", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_TEMPLATE_DIR


def escape_latex(text: Any) -> str:
    """转义 LaTeX 特殊字符，保留已有 LaTeX 命令的简单文本。"""
    if text is None:
        return ""
    s = str(text)
    if not s.strip():
        return ""

    out: List[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1].isalpha():
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
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
            out.append(s[i:j])
            i = j
            continue
        out.append(_LATEX_SPECIAL_CHARS.get(ch, ch))
        i += 1
    return "".join(out)


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
    return [text] if text else []


def _format_itemize(lines: List[str]) -> str:
    if not lines:
        return ""
    body = "\n".join(f"    \\item {escape_latex(line)}" for line in lines)
    return f"\\begin{{itemize}}\n{body}\n\\end{{itemize}}\n"


def _format_paragraph(value: Any) -> str:
    lines = _normalize_lines(value)
    if not lines:
        return ""
    if len(lines) == 1 and "###" not in lines[0]:
        return f"{escape_latex(lines[0])}\n\n"
    return _format_chapter_body(value)


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
        lines = _normalize_lines(text)
        if len(lines) == 1:
            return f"{escape_latex(lines[0])}\n\n"
        return _format_itemize(lines)

    parts: List[str] = []
    blocks = re.split(r"(?m)^###\s+", text)
    if blocks and blocks[0].strip():
        intro = blocks[0].strip()
        if intro:
            parts.append(f"{escape_latex(intro)}\n\n")
    for block in blocks[1:]:
        if not block.strip():
            continue
        lines = block.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        parts.append(f"\\subsection{{{escape_latex(title)}}}\n\n")
        if body:
            body_lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
            if len(body_lines) == 1 and not body_lines[0].startswith("- "):
                parts.append(f"{escape_latex(body_lines[0])}\n\n")
            else:
                items = []
                for ln in body_lines:
                    if ln.startswith("- "):
                        items.append(ln[2:].strip())
                    else:
                        items.append(ln)
                if all(ln.startswith("**") or ":" in ln for ln in items):
                    parts.append(_format_itemize(items))
                else:
                    parts.append(_format_itemize(items))
    return "".join(parts)


def _format_experiments(value: Any) -> str:
    if isinstance(value, str):
        return _format_paragraph(value)

    if not isinstance(value, dict):
        return _format_paragraph(value)

    parts: List[str] = []
    setup = value.get("experimental_setup", "")
    if setup:
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
        parts.append(_format_paragraph(protocol))

    return "".join(parts) if parts else _format_paragraph(str(value))


def _format_results(value: Any) -> str:
    if isinstance(value, str):
        return _format_paragraph(value)

    if not isinstance(value, dict):
        return _format_paragraph(value)

    parts: List[str] = []
    mapping = [
        ("actual_results", "实际结果"),
        ("simulated_results", "模拟结果"),
        ("expected_results", "预期结果"),
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

    return "".join(parts) if parts else _format_paragraph(str(value))


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
    return preamble + "\n"


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

    def add_entry(key: str, fields: Dict[str, str]) -> None:
        base_key = key
        suffix = 1
        while key in seen_keys:
            suffix += 1
            key = f"{base_key}{suffix}"
        seen_keys.add(key)
        keys.append(key)
        field_lines = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items() if v)
        entries.append(f"@misc{{{key},\n  {field_lines}\n}}")

    idx = 1
    for cit in (citation_map or []):
        title = cit.get("paper_title") or cit.get("title") or ""
        if not title:
            continue
        key = _make_bib_key(idx, cit.get("external_id") or cit.get("doi") or title[:20])
        fields = {
            "title": escape_latex(title).replace("\\", ""),
            "author": escape_latex(cit.get("authors", "Unknown")).replace("\\", ""),
            "year": str(cit.get("year", "")),
            "doi": escape_latex(cit.get("doi", "")).replace("\\", ""),
            "url": escape_latex(cit.get("source_url", "")).replace("\\", ""),
            "note": escape_latex(cit.get("journal", "")).replace("\\", ""),
        }
        add_entry(key, {k: v for k, v in fields.items() if v})
        idx += 1

    for vr in (verified_references or []):
        title = vr.get("title") or ""
        if not title:
            continue
        key = _make_bib_key(idx, vr.get("external_id") or vr.get("doi") or title[:20])
        fields = {
            "title": escape_latex(title).replace("\\", ""),
            "author": escape_latex(vr.get("authors", "Unknown")).replace("\\", ""),
            "year": str(vr.get("year", "")),
            "doi": escape_latex(vr.get("doi", "")).replace("\\", ""),
        }
        add_entry(key, {k: v for k, v in fields.items() if v})
        idx += 1

    refs = chapters.get("references", [])
    if isinstance(refs, list):
        for ref in refs:
            if not ref or not isinstance(ref, str):
                continue
            key = _make_bib_key(idx, ref[:24])
            add_entry(key, {"note": escape_latex(ref).replace("\\", "")})
            idx += 1

    bib_content = "\n\n".join(entries)
    return bib_content, keys


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

        src_path = plot.get("path") or plot.get("file_path") or ""
        if src_path and os.path.exists(src_path):
            shutil.copy2(src_path, target)
        elif plot.get("base64"):
            try:
                raw = base64.b64decode(plot["base64"])
                target.write_bytes(raw)
            except Exception as exc:
                logger.warning(f"图表 Base64 解码失败 [{plot_id}]: {exc}")
                continue
        else:
            continue

        prepared.append(
            {
                "relative_path": f"figures/{filename}",
                "title": plot.get("title") or f"Chart {i + 1}",
                "label": f"fig:{safe_id}",
            }
        )

    return prepared


def _build_figures_section(figures: List[Dict[str, str]]) -> str:
    if not figures:
        return ""
    parts = ["\\subsection{数据图表}\n\n"]
    for fig in figures:
        parts.append(
            "\\begin{figure}[H]\n"
            "    \\centering\n"
            f"    \\includegraphics[width=0.85\\textwidth]{{{fig['relative_path']}}}\n"
            f"    \\caption{{{escape_latex(fig['title'])}}}\n"
            f"    \\label{{{fig['label']}}}\n"
            "\\end{figure}\n\n"
        )
    return "".join(parts)


def build_latex_document(
    result: Dict[str, Any],
    project_info: Optional[Dict[str, Any]] = None,
    plots: Optional[List[Dict[str, Any]]] = None,
    figure_files: Optional[List[Dict[str, str]]] = None,
    template_dir: Optional[Path] = None,
) -> str:
    """从结构化报告结果生成完整 LaTeX 源码。"""
    template_dir = template_dir or get_latex_template_dir()
    preamble = _load_template_preamble(template_dir)

    project_info = project_info or {}
    chapters = result.get("chapters", {}) or {}

    title = escape_latex(result.get("paper_title") or result.get("title") or "科学假设与研究计划")
    abstract = escape_latex(result.get("paper_abstract") or "")
    author = _build_author_block(project_info)

    body_parts: List[str] = [
        "\\maketitle\n\n",
        "\\begin{abstract}\n",
        abstract,
        "\n\\end{abstract}\n\n",
        "\\section{待研究问题}\n\n",
        _format_paragraph(chapters.get("problem_statement", "")),
        "\\section{解决思路}\n\n",
        _format_paragraph(chapters.get("rationale", "")),
        "\\section{必要的技术手段}\n\n",
        _format_paragraph(chapters.get("technical_details", "")),
        "\\section{数据集}\n\n",
        _format_paragraph(chapters.get("datasets", "")),
        "\\subsection{历史数据}\n\n",
        _format_paragraph(chapters.get("source", "")),
        "\\subsection{目标数据}\n\n",
        _format_paragraph(chapters.get("target", "")),
        "\\section{方法论}\n\n",
        _format_paragraph(chapters.get("methods", "")),
        "\\section{实验设计}\n\n",
        _format_experiments(chapters.get("experiments", "")),
        "\\section{实验结果}\n\n",
        _format_results(chapters.get("results", "")),
    ]

    if figure_files:
        body_parts.append(_build_figures_section(figure_files))
    elif plots:
        body_parts.append(
            "\\subsection{数据图表}\n\n"
            "当前图表尚未写入 LaTeX 目录，请重新导出 PDF 以嵌入图表。\n\n"
        )

    refs = chapters.get("references", [])
    if refs:
        body_parts.append("\\nocite{*}\n\\bibliography{references}\n")
    else:
        body_parts.append("\\section{参考文献}\n\n")
        body_parts.append("暂无已验证参考文献。\n")

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


def _find_xelatex() -> Optional[str]:
    cmd = os.environ.get("XELATEX_COMMAND", "xelatex")
    path = shutil.which(cmd)
    if path:
        return path
    common = [
        r"C:\texlive\2024\bin\windows\xelatex.exe",
        r"C:\texlive\2023\bin\windows\xelatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
    ]
    for candidate in common:
        if os.path.exists(candidate):
            return candidate
    return None


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

    bibtex = shutil.which("bibtex")
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
    if (work_dir / "references.bib").exists() and bibtex:
        commands.extend(
            [
                [bibtex, "report"],
                [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_filename],
            ]
        )
    commands.append([xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_filename])

    log_chunks: List[str] = []
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
    fallback_markdown_pdf: bool = True,
) -> Dict[str, Any]:
    """
    生成 LaTeX 源码并编译 PDF。

    Returns:
        {
            "success": bool,
            "latex_content": str,
            "tex_file": str,
            "bib_file": str | None,
            "pdf_path": str | None,
            "pdf_success": bool,
            "warning": str | None,
            "export_method": "latex" | "markdown_fallback",
        }
    """
    work_dir = Path(output_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    template_dir = get_latex_template_dir()
    copy_template_assets(work_dir, template_dir)

    chapters = result.get("chapters", {}) or {}
    bib_content, _ = _build_references_bib(chapters, citation_map, verified_references)
    bib_file: Optional[str] = None
    if bib_content.strip():
        bib_path = work_dir / "references.bib"
        bib_path.write_text(bib_content, encoding="utf-8")
        bib_file = str(bib_path)

    figure_files = _prepare_figure_files(result.get("plots"), work_dir)
    latex_content = build_latex_document(
        result=result,
        project_info=project_info,
        plots=result.get("plots"),
        figure_files=figure_files,
        template_dir=template_dir,
    )

    tex_path = work_dir / "report.tex"
    tex_path.write_text(latex_content, encoding="utf-8")

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

    if fallback_markdown_pdf:
        from app.services.pdf_export_service import export_markdown_to_pdf

        pdf_path = work_dir / "report.pdf"
        md_result = export_markdown_to_pdf(
            markdown_content=result.get("markdown_content", ""),
            output_path=str(pdf_path),
        )
        if md_result.get("success"):
            return {
                "success": True,
                "latex_content": latex_content,
                "tex_file": str(tex_path),
                "bib_file": bib_file,
                "pdf_path": md_result.get("pdf_path"),
                "pdf_success": True,
                "warning": f"LaTeX 编译失败，已回退 Markdown PDF：{warning}",
                "export_method": "markdown_fallback",
            }

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
