"""
报告生成智能体 (ReportGenerationAgent)
根据所有研究环节生成《科学假设与研究计划》Markdown 报告和 PDF
"""
import logging
import json
import os
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

import markdown
# weasyprint is imported lazily in _generate_pdf method

from app.core.config import get_settings
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)

settings = get_settings()


class ReportGenerationAgent:
    """
    报告生成智能体
    根据所有研究环节生成《科学假设与研究计划》报告
    """
    
    def __init__(self):
        # 确保存储目录存在
        self.reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "storage", "reports")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_report(
        self,
        project_info: Dict[str, Any],
        problem_understanding: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        knowledge_gaps: Dict[str, Any],
        final_hypothesis: Dict[str, Any],
        experiment_design: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]] = None,
        pipeline_run_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成研究报告
        
        Args:
            project_info: 项目基本信息
            problem_understanding: 问题理解结果
            literature_facts: 文献事实列表
            citation_map: 引用映射列表
            knowledge_gaps: 知识缺口结果
            final_hypothesis: 最终假设
            experiment_design: 实验设计
            small_validation: 小样验证结果（可选）
            pipeline_run_info: Pipeline 运行信息（可选）
            
        Returns:
            报告生成结果
        """
        try:
            logger.info(f"开始生成研究报告，项目: {project_info.get('title', 'Unknown')}")
            
            # 格式化输入信息
            formatted_input = self._format_input(
                project_info,
                problem_understanding,
                literature_facts,
                citation_map,
                knowledge_gaps,
                final_hypothesis,
                experiment_design,
                small_validation
            )
            
            # 构建提示
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "report_generation",
                formatted_input
            )
            
            # 定义 schema 示例
            schema_example = {
                "title": "科学假设与研究计划",
                "paper_title": "基于混合模型的医学图像分类研究",
                "paper_abstract": "本文提出一种...",
                "markdown_content": "# 科学假设与研究计划...",
                "chapters": {
                    "problem_statement": "...",
                    "rationale": "...",
                    "technical_details": "...",
                    "datasets": "...",
                    "source": "...",
                    "target": "...",
                    "methods": "...",
                    "experiments": "...",
                    "results": "...",
                    "references": ["..."]
                }
            }
            
            # 调用 LLM
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="report_generation"
            )
            
            # 验证和标准化结果
            result = self._validate_and_normalize_result(result_dict)
            
            # 添加运行摘要到报告
            if pipeline_run_info:
                result = self._append_run_summary_to_report(result, pipeline_run_info)
            
            # 保存报告文件
            file_info = self._save_report_files(result, project_info)
            
            # 合并文件信息到结果
            result.update(file_info)
            
            logger.info("研究报告生成完成")
            
            return result
            
        except Exception as e:
            logger.error(f"生成研究报告时出错: {e}", exc_info=True)
            raise
    
    def _append_run_summary_to_report(self, result: Dict[str, Any], run_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        将运行摘要附加到报告
        
        Args:
            result: 原始报告结果
            run_info: 运行信息
            
        Returns:
            更新后的结果
        """
        try:
            # 构建运行摘要部分
            summary_content = self._build_run_summary_content(run_info)
            
            # 附加到 markdown 内容
            original_markdown = result.get("markdown_content", "")
            result["markdown_content"] = original_markdown + "\n" + summary_content
            
            return result
            
        except Exception as e:
            logger.error(f"添加运行摘要时出错: {e}", exc_info=True)
            # 出错时不影响主报告
            return result
    
    def _build_run_summary_content(self, run_info: Dict[str, Any]) -> str:
        """
        构建运行摘要的 Markdown 内容
        
        Args:
            run_info: 运行信息
            
        Returns:
            Markdown 内容
        """
        # 从运行信息中提取关键数据
        run_id = run_info.get("run_id", "N/A")
        started_at = run_info.get("started_at")
        completed_at = run_info.get("completed_at")
        total_duration_ms = run_info.get("total_duration_ms", 0)
        status = run_info.get("status", "unknown")
        stages = run_info.get("stages", [])
        
        # 格式化时间
        def format_datetime(dt_str):
            if isinstance(dt_str, str):
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return str(dt_str)
            elif isinstance(dt_str, datetime):
                return dt_str.strftime("%Y-%m-%d %H:%M:%S")
            return "N/A"
        
        # 格式化耗时
        def format_duration(ms):
            if not ms:
                return "N/A"
            total_sec = ms // 1000
            min = total_sec // 60
            sec = total_sec % 60
            if min > 0:
                return f"{min}分钟{sec}秒"
            return f"{sec}秒"
        
        # 构建摘要
        summary = f"""

---

## 运行摘要

### 基本信息
- **运行 ID**: {run_id}
- **状态**: {status}
- **开始时间**: {format_datetime(started_at)}
- **结束时间**: {format_datetime(completed_at)}
- **总耗时**: {format_duration(total_duration_ms)}

### 执行阶段
| 阶段 | 状态 | 耗时 |
|------|------|------|
"""
        
        # 添加阶段详情
        for stage in stages:
            stage_name = stage.get("stage", "unknown")
            stage_status = stage.get("status", "unknown")
            duration = stage.get("duration_ms", 0)
            summary += f"| {stage_name} | {stage_status} | {format_duration(duration)} |\n"
        
        return summary
    
    def _format_input(
        self,
        project_info: Dict[str, Any],
        problem_understanding: Dict[str, Any],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]],
        knowledge_gaps: Dict[str, Any],
        final_hypothesis: Dict[str, Any],
        experiment_design: Dict[str, Any],
        small_validation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """格式化输入信息为字符串"""
        return {
            "project_info": json.dumps(project_info, ensure_ascii=False, indent=2),
            "problem_understanding": json.dumps(problem_understanding, ensure_ascii=False, indent=2),
            "literature_facts": json.dumps(literature_facts, ensure_ascii=False, indent=2),
            "citation_map": json.dumps(citation_map, ensure_ascii=False, indent=2),
            "knowledge_gaps": json.dumps(knowledge_gaps, ensure_ascii=False, indent=2),
            "final_hypothesis": json.dumps(final_hypothesis, ensure_ascii=False, indent=2),
            "experiment_design": json.dumps(experiment_design, ensure_ascii=False, indent=2),
            "small_validation": json.dumps(small_validation, ensure_ascii=False, indent=2) if small_validation else "无小样验证结果"
        }
    
    def _validate_and_normalize_result(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """验证和标准化结果"""
        # 确保顶层字段存在
        required_fields = ["title", "paper_title", "paper_abstract", "markdown_content", "chapters"]
        for field in required_fields:
            if field not in result_dict:
                if field == "title":
                    result_dict[field] = "科学假设与研究计划"
                elif field == "paper_title":
                    result_dict[field] = "研究报告"
                else:
                    result_dict[field] = ""
        
        # 确保 chapters 字段存在且包含所有必需章节
        if "chapters" not in result_dict or not isinstance(result_dict["chapters"], dict):
            result_dict["chapters"] = {}
        
        required_chapters = [
            "problem_statement", "rationale", "technical_details",
            "datasets", "source", "target", "methods", "experiments", "results", "references"
        ]
        
        for chapter in required_chapters:
            if chapter not in result_dict["chapters"]:
                if chapter == "references":
                    result_dict["chapters"][chapter] = []
                else:
                    result_dict["chapters"][chapter] = ""
        
        # 确保 references 是列表
        if not isinstance(result_dict["chapters"]["references"], list):
            result_dict["chapters"]["references"] = []
        
        return result_dict
    
    def _save_report_files(self, result: Dict[str, Any], project_info: Dict[str, Any]) -> Dict[str, Any]:
        """保存报告文件"""
        try:
            report_id = str(uuid.uuid4())
            
            # 创建目录
            report_path = os.path.join(self.reports_dir, report_id)
            os.makedirs(report_path, exist_ok=True)
            
            # 保存 Markdown 文件
            md_file = os.path.join(report_path, "report.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(result.get("markdown_content", ""))
            
            # 保存 JSON 数据
            json_file = os.path.join(report_path, "report_data.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # 尝试生成 PDF
            pdf_file = os.path.join(report_path, "report.pdf")
            pdf_success = self._convert_markdown_to_pdf(
                markdown_content=result.get("markdown_content", ""),
                pdf_file=pdf_file
            )
            
            logger.info(f"报告文件已保存到: {report_path}")
            
            return {
                "report_id": report_id,
                "report_path": report_path,
                "md_file": md_file,
                "json_file": json_file,
                "pdf_file": pdf_file if pdf_success else None,
                "pdf_success": pdf_success
            }
            
        except Exception as e:
            logger.error(f"保存报告文件时出错: {e}", exc_info=True)
            raise
    
    def _convert_markdown_to_pdf(self, markdown_content: str, pdf_file: str) -> bool:
        """
        将 Markdown 转换为 PDF
        
        Args:
            markdown_content: Markdown 内容
            pdf_file: PDF 文件路径
            
        Returns:
            是否成功
        """
        try:
            from weasyprint import HTML, CSS
            
            # 1. Markdown 转 HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=[
                    'extra',
                    'tables',
                    'toc',
                    'codehilite',
                    'fenced_code'
                ]
            )
            
            # 2. 获取 CSS 样式
            css_file = os.path.join(
                os.path.dirname(__file__),
                "report_style.css"
            )
            
            # 3. 构建完整 HTML
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>科学假设与研究计划</title>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            # 4. 使用 WeasyPrint 生成 PDF
            if os.path.exists(css_file):
                HTML(string=full_html).write_pdf(
                    pdf_file,
                    stylesheets=[CSS(filename=css_file)]
                )
            else:
                HTML(string=full_html).write_pdf(pdf_file)
            
            logger.info(f"PDF 生成成功: {pdf_file}")
            return True
            
        except Exception as e:
            logger.error(f"PDF 生成失败: {e}", exc_info=True)
            # PDF 失败不影响 Markdown 保存
            return False


# 全局单例
_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    """获取 ReportGenerationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance
