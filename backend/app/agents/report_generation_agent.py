"""
报告生成智能体 (ReportGenerationAgent)
根据所有研究环节生成《科学假设与研究计划》Markdown 报告
"""
import logging
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)

settings = get_settings()

REPORT_GENERATION_PROMPT_TEMPLATE = """你是一位专业的学术写作专家。请根据提供的研究信息，生成一份完整的《科学假设与研究计划》Markdown 格式报告。

## 输入信息

### 项目信息
{project_info}

### 问题理解
{problem_understanding}

### 文献事实
{literature_facts}

### 引用映射
{citation_map}

### 知识缺口
{knowledge_gaps}

### 最终假设
{final_hypothesis}

### 实验设计
{experiment_design}

### 小样验证
{small_validation}

## 报告要求

请生成一份完整的 Markdown 格式报告，必须包含以下章节：

1. **Problem Statement** - 清晰陈述研究问题，说明其重要性和研究价值
2. **Rationale** - 阐述研究假设的理论依据和逻辑基础
3. **Technical Details** - 详细描述技术方法、模型架构、算法原理等
4. **Datasets** - 说明使用的数据集、数据来源、数据特征等
5. **Source** - 描述源数据的格式、内容、预处理方式
6. **Target** - 描述目标输出的格式、内容、评价标准
7. **Paper Title** - 生成一个吸引人的学术论文标题
8. **Paper Abstract** - 生成 200-300 字的论文摘要
9. **Methods** - 详细描述研究方法、实验步骤、评估指标
10. **Experiments** - 详细描述实验设计、对比方法、实验流程
11. **Results** - 描述预期结果、可能的发现、验证假设的方式
12. **References** - 参考文献列表（必须从提供的文献事实和引用映射中提取，禁止虚构）

## 参考文献要求

- 参考文献必须从提供的 literature_facts 和 citation_map 中提取
- 每条参考文献必须包含：作者、标题、年份、来源（如果有）
- 格式遵循学术规范（如 APA 或 IEEE 格式）
- 禁止虚构任何参考文献
- 在正文中适当引用这些参考文献

## 输出格式要求

请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：

{{
  "title": "科学假设与研究计划",
  "paper_title": "论文标题",
  "paper_abstract": "论文摘要...",
  "markdown_content": "# 完整的 Markdown 报告内容...",
  "chapters": {{
    "problem_statement": "Problem Statement 章节内容...",
    "rationale": "Rationale 章节内容...",
    "technical_details": "Technical Details 章节内容...",
    "datasets": "Datasets 章节内容...",
    "source": "Source 章节内容...",
    "target": "Target 章节内容...",
    "methods": "Methods 章节内容...",
    "experiments": "Experiments 章节内容...",
    "results": "Results 章节内容...",
    "references": ["参考文献 1", "参考文献 2", ...]
  }}
}}

## 注意事项

- 报告语言为中文（除非特别说明）
- 保持学术严谨性和专业性
- 章节结构清晰，逻辑连贯
- 所有内容必须基于提供的输入信息，不得凭空编造
- 适当使用表格、列表等格式增强可读性
"""


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
        small_validation: Optional[Dict[str, Any]] = None
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
            prompt = REPORT_GENERATION_PROMPT_TEMPLATE.format(**formatted_input)
            
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
                schema_example=schema_example
            )
            
            # 验证和标准化结果
            result = self._validate_and_normalize_result(result_dict)
            
            # 保存报告文件
            self._save_report_files(result, project_info)
            
            logger.info("研究报告生成完成")
            
            return result
            
        except Exception as e:
            logger.error(f"生成研究报告时出错: {e}", exc_info=True)
            raise
    
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
    
    def _save_report_files(self, result: Dict[str, Any], project_info: Dict[str, Any]) -> None:
        """保存报告文件"""
        try:
            import uuid
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
            
            logger.info(f"报告文件已保存到: {report_path}")
            
        except Exception as e:
            logger.error(f"保存报告文件时出错: {e}", exc_info=True)


# 全局单例
_agent_instance: Optional[ReportGenerationAgent] = None


def get_report_generation_agent() -> ReportGenerationAgent:
    """获取 ReportGenerationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReportGenerationAgent()
    return _agent_instance
