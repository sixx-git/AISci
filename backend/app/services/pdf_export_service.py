"""
PDF 导出服务

优先级:
  1. Playwright Chromium  → 将 Markdown 渲染为 HTML 后导出 PDF
  2. WeasyPrint          → 备用方案
  3. 两者都失败           → 返回 warning，Markdown/JSON 照常保存
"""

import logging
import os
import tempfile
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def export_markdown_to_pdf(
    markdown_content: str,
    output_path: str,
    css_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将 Markdown 内容导出为 PDF 文件。

    Args:
        markdown_content: Markdown 文本
        output_path:      PDF 输出路径（如 /path/to/report.pdf）
        css_path:         可选的 CSS 样式文件路径

    Returns:
        {
            "success":  bool,
            "pdf_path": str | None,
            "warning":  str | None,
        }
    """
    if not markdown_content or not markdown_content.strip():
        return {
            "success": False,
            "pdf_path": None,
            "warning": "Markdown 内容为空，跳过 PDF 生成",
        }

    # 1. Markdown → HTML
    html_body = _markdown_to_html(markdown_content)

    # 2. 构建完整 HTML 文档
    full_html = _build_html_document(html_body, css_path)

    # 3. 尝试 Playwright → WeasyPrint
    for method_name, method_fn in [
        ("Playwright", _export_via_playwright),
        ("WeasyPrint", _export_via_weasyprint),
    ]:
        try:
            logger.info(f"尝试使用 {method_name} 生成 PDF → {output_path}")
            method_fn(full_html, output_path)
            logger.info(f"{method_name} PDF 生成成功: {output_path}")
            return {"success": True, "pdf_path": output_path, "warning": None}
        except Exception as e:
            logger.warning(f"{method_name} PDF 生成失败: {e}")

    # 4. 全部失败 — 仍然视为非致命错误
    return {
        "success": False,
        "pdf_path": None,
        "warning": "PDF 生成失败，但 Markdown/JSON 已保存。"
                   "请安装 Playwright 或 WeasyPrint 后重试。",
    }


# ── 内部工具函数 ──────────────────────────────────────────────

def _markdown_to_html(md_text: str) -> str:
    """将 Markdown 文本转为 HTML（优先 markdown-it-py，回退 mistune / markdown）"""
    # 1) markdown-it-py（推荐，与 Python-Markdown 扩展兼容性好）
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt("commonmark", {"typographer": True})
        md.enable(["table", "strikethrough", "linkify"])
        # 启用代码高亮
        md.options["highlight"] = None  # 后续可换 highlight.js
        return md.render(md_text)
    except ImportError:
        logger.debug("markdown-it-py 不可用，尝试 mistune")
    except Exception as e:
        logger.warning(f"markdown-it-py 渲染失败: {e}")

    # 2) mistune
    try:
        import mistune
        return mistune.html(md_text)
    except ImportError:
        logger.debug("mistune 不可用，尝试 markdown")
    except Exception as e:
        logger.warning(f"mistune 渲染失败: {e}")

    # 3) markdown（Python-Markdown）
    try:
        import markdown as md_lib
        return md_lib.markdown(
            md_text,
            extensions=["extra", "tables", "toc", "codehilite", "fenced_code"],
        )
    except Exception as e:
        logger.error(f"所有 Markdown 渲染器均失败: {e}")
        # 最差情况：直接包裹在 <pre> 中
        return f"<pre>{md_text}</pre>"


def _build_html_document(html_body: str, css_path: Optional[str] = None) -> str:
    """构建完整 HTML 文档，注入 CSS 和中文友好样式"""
    css_tag = ""
    if css_path and os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        css_tag = f"<style>\n{css_content}\n</style>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>科学假设与研究计划</title>
    {css_tag}
    <style>
        /* 打印友好的基础样式（CSS 未覆盖时的回退） */
        body {{
            font-family: 'Microsoft YaHei', 'PingFang SC', 'SimHei', 'Noto Sans SC', sans-serif;
            font-size: 12pt;
            line-height: 1.7;
            color: #222;
            max-width: 210mm;
            margin: 0 auto;
            padding: 15mm 20mm;
        }}
        h1 {{ font-size: 20pt; border-bottom: 2px solid #1a365d; padding-bottom: 6px; }}
        h2 {{ font-size: 15pt; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
        h3 {{ font-size: 13pt; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
        th {{ background: #f0f4f8; }}
        code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 10pt; }}
        pre {{ background: #f8f9fa; padding: 12px; border: 1px solid #e2e8f0; overflow-x: auto; }}
        blockquote {{ border-left: 4px solid #2b6cb0; margin-left: 0; padding-left: 16px; color: #555; }}
        @page {{ size: A4; margin: 15mm 20mm; }}
        @media print {{ body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""


# ── Playwright 导出 ───────────────────────────────────────────

def _launch_playwright_browser(playwright):
    """优先使用系统 Chrome/Edge，回退到 Playwright 自带 Chromium。"""
    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]
    env_channel = os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL", "").strip()
    channels = [env_channel] if env_channel else []
    channels.extend(["chrome", "msedge", None])

    last_error: Optional[Exception] = None
    for channel in channels:
        try:
            if channel:
                return playwright.chromium.launch(channel=channel, args=launch_args)
            return playwright.chromium.launch(args=launch_args)
        except Exception as exc:
            last_error = exc
            logger.debug("Playwright 启动失败 channel=%s: %s", channel, exc)
    raise RuntimeError(
        "无法启动浏览器生成 PDF。"
        "请安装 Google Chrome / Microsoft Edge，或执行: python -m playwright install chromium"
    ) from last_error


def _export_via_playwright(full_html: str, output_path: str) -> None:
    """
    使用 Playwright 将 HTML 渲染为 PDF（优先系统 Chrome/Edge）。
    若均不可用，可执行: python -m playwright install chromium
    """
    from playwright.sync_api import sync_playwright

    tmp_html: Optional[str] = None
    with sync_playwright() as p:
        browser = _launch_playwright_browser(p)
        try:
            page = browser.new_page()
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as f:
                f.write(full_html)
                tmp_html = f.name

            file_url = f"file:///{tmp_html.replace(os.sep, '/')}"
            page.goto(file_url, wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "20mm", "right": "20mm"},
            )
        finally:
            browser.close()
            if tmp_html and os.path.exists(tmp_html):
                os.unlink(tmp_html)


# ── WeasyPrint 导出（备用）────────────────────────────────────

def _export_via_weasyprint(full_html: str, output_path: str) -> None:
    """使用 WeasyPrint 将 HTML 渲染为 PDF。"""
    from weasyprint import HTML

    HTML(string=full_html).write_pdf(output_path)