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

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.services.pdf_export_service import export_markdown_to_pdf

logger = logging.getLogger(__name__)


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
            result = self._validate_and_normalize_result(
                result_dict,
                literature_facts,
                citation_map
            )
            
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
    
    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        literature_facts: List[Dict[str, Any]] = None,
        citation_map: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
        
        # 确保 chapters 字段存在且包含所有必需章节（12 项挑战杯规范字段）
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
        
        # 参考文献真实性校验
        ref_check = self._validate_references(
            result_dict["chapters"]["references"],
            literature_facts or [],
            citation_map or []
        )
        
        # 如果参考文献全部无法验证且不为空标记，强制替换
        if ref_check["suspicious_count"] > 0 and ref_check["verified_count"] == 0:
            logger.warning(f"参考文献校验失败：{ref_check['suspicious_count']} 条疑似虚构引用")
            result_dict["chapters"]["references"] = ["暂无真实文献引用，需补充文献库"]
            ref_check["references_replaced"] = True
        
        # 构建比赛规范合规性检查结果
        compliance_check = self._build_compliance_check(result_dict, ref_check)
        result_dict["compliance_check"] = compliance_check
        
        return result_dict
    
    def _validate_references(
        self,
        references: List[str],
        literature_facts: List[Dict[str, Any]],
        citation_map: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        校验参考文献是否来自已上传的文献库或证据链
        
        Returns:
            {
                "verified_count": 可验证的引用数,
                "suspicious_count": 疑似虚构的引用数,
                "verified_refs": 验证通过的引用列表,
                "suspicious_refs": 疑似虚构的引用列表,
                "references_replaced": 是否已替换
            }
        """
        if not references or references == ["暂无真实文献引用，需补充文献库"]:
            return {
                "verified_count": 0,
                "suspicious_count": 0,
                "verified_refs": [],
                "suspicious_refs": [],
                "references_replaced": False,
                "note": "暂无文献引用"
            }
        
        # 构建可验证的关键词库（从 literature_facts 和 citation_map 提取）
        verified_keywords = set()
        for fact in (literature_facts or []):
            for key in ["title", "authors", "source", "content"]:
                val = fact.get(key, "")
                if isinstance(val, str) and len(val) > 3:
                    # 使用短序列用于模糊匹配
                    verified_keywords.add(val[:50].lower())
        for cit in (citation_map or []):
            for key in ["title", "authors", "source", "reference_text", "citation"]:
                val = cit.get(key, "")
                if isinstance(val, str) and len(val) > 3:
                    verified_keywords.add(val[:50].lower())
        
        verified_refs = []
        suspicious_refs = []
        
        for ref in references:
            if not ref or not isinstance(ref, str):
                suspicious_refs.append(str(ref) if ref else "(空引用)")
                continue
            
            ref_lower = ref[:100].lower()
            is_verified = False
            
            for kw in verified_keywords:
                # 检查引用文本是否包含已知文献的关键信息
                if len(kw) > 10 and kw in ref_lower:
                    is_verified = True
                    break
                # 也尝试用较短片段匹配（作者名等）
                if len(kw) >= 5 and kw[:20] in ref_lower:
                    is_verified = True
                    break
            
            if is_verified:
                verified_refs.append(ref)
            else:
                suspicious_refs.append(ref)
        
        return {
            "verified_count": len(verified_refs),
            "suspicious_count": len(suspicious_refs),
            "verified_refs": verified_refs,
            "suspicious_refs": suspicious_refs,
            "references_replaced": False
        }
    
    def _build_compliance_check(
        self,
        result_dict: Dict[str, Any],
        ref_check: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建 12 项挑战杯规范合规性检查结果"""
        chapters = result_dict.get("chapters", {})
        
        # 定义 12 项检查字段
        CHECK_FIELDS = [
            ("problem_statement", "Problem Statement"),
            ("rationale", "Rationale"),
            ("technical_details", "Technical Details"),
            ("datasets", "Datasets"),
            ("source", "Source"),
            ("target", "Target"),
            ("paper_title", "Paper Title"),
            ("paper_abstract", "Paper Abstract"),
            ("methods", "Methods"),
            ("experiments", "Experiments"),
            ("results", "Results"),
            ("references", "References"),
        ]
        
        items = []
        for key, label in CHECK_FIELDS:
            if key == "paper_title":
                value = result_dict.get("paper_title", "")
            elif key == "paper_abstract":
                value = result_dict.get("paper_abstract", "")
            else:
                value = chapters.get(key, "")
            
            if key == "references":
                refs = chapters.get("references", [])
                if not refs or refs == ["暂无真实文献引用，需补充文献库"]:
                    status = "missing"
                    note = "暂无真实文献引用，需补充文献库"
                elif ref_check.get("references_replaced"):
                    status = "human_review"
                    note = f"检测到 {ref_check.get('suspicious_count', 0)} 条疑似虚构引用，已被替换为安全提示"
                elif ref_check.get("suspicious_count", 0) > 0:
                    status = "human_review"
                    note = f"检测到 {ref_check.get('suspicious_count', 0)} 条引用无法在文献库中验证，需人工确认"
                else:
                    status = "completed"
                    note = f"{ref_check.get('verified_count', 0)} 条引用已通过文献库验证"
            elif isinstance(value, str) and len(value.strip()) > 10:
                status = "completed"
                note = None
            elif isinstance(value, str) and len(value.strip()) > 0:
                status = "human_review"
                note = "内容较短，建议补充完善"
            else:
                status = "missing"
                note = "该字段缺失，需补充内容"
            
            items.append({
                "key": key,
                "label": label,
                "status": status,
                "note": note
            })
        
        completed = sum(1 for i in items if i["status"] == "completed")
        missing = sum(1 for i in items if i["status"] == "missing")
        needs_review = sum(1 for i in items if i["status"] == "human_review")
        
        return {
            "total": 12,
            "completed": completed,
            "missing": missing,
            "human_review": needs_review,
            "references_verified": ref_check.get("verified_count", 0),
            "references_suspicious": ref_check.get("suspicious_count", 0),
            "items": items
        }
    
    def _save_report_files(self, result: Dict[str, Any], project_info: Dict[str, Any]) -> Dict[str, Any]:
        """保存报告文件"""
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

        # 生成 PDF（新服务：Playwright → WeasyPrint → 降级警告）
        pdf_file = os.path.join(report_path, "report.pdf")
        pdf_result = export_markdown_to_pdf(
            markdown_content=result.get("markdown_content", ""),
            output_path=pdf_file,
            css_path=os.path.join(os.path.dirname(__file__), "report_style.css"),
        )

        logger.info(f"报告文件已保存到: {report_path}")

        return {
            "report_id": report_id,
            "report_path": report_path,
            "md_file": md_file,
            "json_file": json_file,
            "pdf_file": pdf_result.get("pdf_path"),
            "pdf_success": pdf_result.get("success", False),
            "warning": pdf_result.get("warning"),
        }


# 全局单例
_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    """获取 ReportGenerationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance
