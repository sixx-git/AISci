"""报告类 Skill 统一导出"""
from app.skills.report.report_chart_generation_skill import ReportChartGenerationSkill
from app.skills.report.scientific_plot_skill import ScientificPlotSkill

__all__ = [
    "ReportChartGenerationSkill",
    "ScientificPlotSkill",
]