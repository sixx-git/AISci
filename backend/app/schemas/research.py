"""
研究相关 Schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class ResearchRequest(BaseModel):
    """研究请求"""
    topic: str = Field(..., description="研究主题")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    research_type: str = Field("literature_review", description="研究类型")
    max_tokens: Optional[int] = Field(2000, description="最大 tokens 数")


class ResearchResponse(BaseModel):
    """研究响应"""
    success: bool = Field(..., description="是否成功")
    research_id: str = Field(..., description="研究项目ID")
    title: str = Field(..., description="研究标题")
    content: str = Field(..., description="研究内容")
    references: Optional[List[str]] = Field(None, description="参考文献列表")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")


class EvidenceResponse(BaseModel):
    """证据链响应"""
    id: str
    project_id: str
    hypothesis_id: str
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    fact_text: str
    quote_text: Optional[str] = None
    page_number: Optional[int] = None
    relevance_score: float
    source_title: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class HypothesisCreate(BaseModel):
    """创建假设"""
    project_id: str = Field(..., description="项目ID")
    research_question: str = Field(..., description="研究问题")
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")
    supporting_fact_ids: Optional[List[str]] = Field(None, description="支持的文献事实 ID 列表")
    evidence_level: Optional[str] = Field("medium", description="证据级别: high / medium / low")
    status: Optional[str] = Field("draft", description="状态")
    priority: Optional[int] = Field(3, ge=1, le=5, description="优先级 1-5")
    confidence: Optional[float] = Field(0.5, ge=0, le=1, description="置信度 0-1")
    alignment_score: Optional[int] = Field(None, ge=0, le=100, description="问题对齐度 0-100")
    off_topic: Optional[bool] = Field(None, description="是否偏题")
    off_topic_reason: Optional[str] = Field(None, description="偏题原因")
    matched_keywords: Optional[List[str]] = Field(None, description="匹配到的关键词")
    missing_keywords: Optional[List[str]] = Field(None, description="缺失的关键词")
    question_alignment: Optional[str] = Field(None, description="假设与研究问题的对齐说明")
    dataset_field_refs: Optional[List[str]] = Field(None, description="引用的数据集字段")
    data_evidence_ids: Optional[List[str]] = Field(None, description="引用的数据证据 ID")
    validation_target: Optional[str] = Field(None, description="验证目标指标")
    expected_measurable_effect: Optional[str] = Field(None, description="预期的可量化效果")

    @field_validator("matched_keywords", "missing_keywords", "dataset_field_refs", "data_evidence_ids", mode="before")
    @classmethod
    def _parse_json_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class HypothesisResponse(HypothesisCreate):
    """假设响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class HypothesisItem(BaseModel):
    """单个假设项（用于生成结果）"""
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")
    supporting_fact_ids: List[str] = Field(default_factory=list, description="支持的文献事实 ID 列表")
    evidence_level: str = Field(default="medium", description="证据级别: high / medium / low")
    question_alignment: str = Field(default="", description="假设与研究问题的对齐说明")
    dataset_field_refs: List[str] = Field(default_factory=list, description="引用的数据集字段")
    data_evidence_ids: List[str] = Field(default_factory=list, description="引用的数据证据 ID")
    validation_target: str = Field(default="", description="验证目标指标")
    expected_measurable_effect: str = Field(default="", description="预期的可量化效果")


class HypothesisGenerationRequest(BaseModel):
    """假设生成请求"""
    project_id: str = Field(..., description="项目ID")
    research_question: str = Field(..., description="研究问题")
    facts: List[dict] = Field(..., description="事实列表")
    knowledge_gaps: List[dict] = Field(..., description="知识缺口列表")
    constraints: List[str] = Field(..., description="约束条件列表")


class HypothesisGenerationResponse(BaseModel):
    """假设生成响应"""
    hypotheses: List[HypothesisItem] = Field(..., description="生成的假设列表")
    summary: Optional[str] = Field(None, description="生成摘要")


class ExperimentDesignCreate(BaseModel):
    """创建实验设计"""
    project_id: str = Field(..., description="项目ID")
    hypothesis_id: str = Field(..., description="假设ID")
    hypothesis: str = Field(..., description="假设内容")
    methods: str = Field(..., description="研究方法")
    datasets: str = Field(..., description="数据集")
    source_data: str = Field(..., description="源数据")
    target_data: str = Field(..., description="目标数据")
    baselines: str = Field(..., description="基线方法")
    metrics: str = Field(..., description="评估指标")
    experimental_steps: str = Field(..., description="实验步骤")
    expected_results: str = Field(..., description="预期结果")
    limitations: str = Field(..., description="局限性")
    status: Optional[str] = Field("draft", description="状态")
    priority: Optional[int] = Field(3, ge=1, le=5, description="优先级 1-5")


class ExperimentDesignDBResponse(ExperimentDesignCreate):
    """实验设计数据库响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ExperimentDesignItem(BaseModel):
    """单个实验设计项（用于生成结果）"""
    methods: str = Field(..., description="研究方法")
    datasets: str = Field(..., description="数据集")
    source_data: str = Field(..., description="源数据")
    target_data: str = Field(..., description="目标数据")
    baselines: str = Field(..., description="基线方法")
    metrics: str = Field(..., description="评估指标")
    experimental_steps: str = Field(..., description="实验步骤")
    expected_results: str = Field(..., description="预期结果")
    limitations: str = Field(..., description="局限性")


class ExperimentDesignRequest(BaseModel):
    """实验设计请求"""
    project_id: str = Field(..., description="项目ID")
    hypothesis_id: str = Field(..., description="假设ID")
    hypothesis: str = Field(..., description="假设内容")
    rationale: Optional[str] = Field(None, description="理论依据")
    novelty: Optional[str] = Field(None, description="创新性")
    testability: Optional[str] = Field(None, description="可测试性")
    required_data: Optional[str] = Field(None, description="所需数据")
    possible_method: Optional[str] = Field(None, description="可能的方法")
    risk: Optional[str] = Field(None, description="风险")


class ExperimentDesignGenerationResponse(BaseModel):
    """实验设计生成响应"""
    experiment_design: ExperimentDesignItem = Field(..., description="生成的实验设计")
    summary: Optional[str] = Field(None, description="生成摘要")


class SmallValidationCreate(BaseModel):
    """创建小样验证"""
    project_id: str = Field(..., description="项目ID")
    experiment_design_id: str = Field(..., description="实验设计ID")
    hypothesis: str = Field(..., description="假设内容")
    has_real_data: int = Field(0, description="是否有真实数据 0: no, 1: yes")
    analysis_script: str = Field(..., description="pandas 分析脚本")
    simulated_data: Optional[str] = Field(None, description="模拟数据 JSON")
    simulation_assumptions: Optional[str] = Field(None, description="模拟假设说明")
    charts: Optional[str] = Field(None, description="图表数据 JSON 列表")
    statistics: Optional[str] = Field(None, description="统计结果 JSON")
    run_log: Optional[str] = Field(None, description="运行日志")
    status: Optional[str] = Field("draft", description="状态")
    execution_time: Optional[float] = Field(None, description="执行时间")


class SmallValidationDBResponse(SmallValidationCreate):
    """小样验证数据库响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SmallValidationRequest(BaseModel):
    """小样验证请求"""
    project_id: str = Field(..., description="项目ID")
    experiment_design_id: str = Field(..., description="实验设计ID")
    hypothesis: str = Field(..., description="假设内容")
    methods: Optional[str] = Field(None, description="研究方法")
    datasets: Optional[str] = Field(None, description="数据集说明")
    metrics: Optional[str] = Field(None, description="评估指标")
    csv_data_path: Optional[str] = Field(None, description="CSV 数据路径（如果有）")


class SmallValidationItem(BaseModel):
    """小样验证项"""
    has_real_data: int = Field(..., description="是否有真实数据 0: no, 1: yes")
    analysis_script: str = Field(..., description="pandas 分析脚本")
    simulated_data: Optional[str] = Field(None, description="模拟数据 JSON")
    simulation_assumptions: Optional[str] = Field(None, description="模拟假设说明")
    charts: Optional[str] = Field(None, description="图表数据 JSON 列表")
    statistics: Optional[str] = Field(None, description="统计结果 JSON")
    run_log: Optional[str] = Field(None, description="运行日志")


class SmallValidationGenerationResponse(BaseModel):
    """小样验证生成响应"""
    validation: SmallValidationItem = Field(..., description="生成的验证方案")
    summary: Optional[str] = Field(None, description="生成摘要")


class ReportGenerationRequest(BaseModel):
    """报告生成请求"""
    project_id: str = Field(..., description="项目 ID")
    project_info: dict = Field(..., description="项目基本信息")
    problem_understanding: dict = Field(..., description="问题理解结果")
    literature_facts: List[dict] = Field(..., description="文献事实列表")
    citation_map: List[dict] = Field(..., description="引用映射列表")
    knowledge_gaps: dict = Field(..., description="知识缺口结果")
    final_hypothesis: dict = Field(..., description="最终假设")
    experiment_design: dict = Field(..., description="实验设计")
    small_validation: Optional[dict] = Field(None, description="小样验证结果")


class ReportChapterItem(BaseModel):
    """报告章节内容"""
    problem_statement: str = Field(..., description="问题陈述")
    rationale: str = Field(..., description="原理依据")
    technical_details: str = Field(..., description="技术细节")
    datasets: str = Field(..., description="数据集说明")
    source: str = Field(..., description="源数据说明")
    target: str = Field(..., description="目标说明")
    methods: str = Field(..., description="研究方法")
    experiments: str = Field(..., description="实验设计")
    results: str = Field(..., description="预期结果")
    references: List[str] = Field(..., description="参考文献列表")


class ReportGenerationResult(BaseModel):
    """报告生成结果"""
    title: str = Field(..., description="报告标题")
    paper_title: str = Field(..., description="论文标题")
    paper_abstract: str = Field(..., description="论文摘要")
    markdown_content: str = Field(..., description="Markdown 格式完整报告")
    chapters: ReportChapterItem = Field(..., description="各章节内容")
    report_id: Optional[str] = Field(None, description="报告 ID")
    pdf_download_url: Optional[str] = Field(None, description="PDF 下载地址")
    md_download_url: Optional[str] = Field(None, description="Markdown 下载地址")
    pdf_success: Optional[bool] = Field(None, description="PDF 是否生成成功")


class ReportGenerationResponse(BaseModel):
    """报告生成响应"""
    report: ReportGenerationResult = Field(..., description="生成的报告")
    summary: Optional[str] = Field(None, description="生成摘要")


class ReportCreate(BaseModel):
    """创建研究报告"""
    project_id: str = Field(..., description="项目 ID")
    hypothesis_id: Optional[str] = Field(None, description="假设 ID")
    experiment_design_id: Optional[str] = Field(None, description="实验设计 ID")
    small_validation_id: Optional[str] = Field(None, description="小样验证 ID")
    title: str = Field(..., description="报告标题")
    paper_title: str = Field(..., description="论文标题")
    paper_abstract: str = Field(..., description="论文摘要")
    markdown_content: str = Field(..., description="Markdown 内容")
    problem_statement: str = Field(..., description="问题陈述")
    rationale: str = Field(..., description="原理依据")
    technical_details: str = Field(..., description="技术细节")
    datasets: str = Field(..., description="数据集说明")
    source: str = Field(..., description="源数据说明")
    target: str = Field(..., description="目标说明")
    methods: str = Field(..., description="研究方法")
    experiments: str = Field(..., description="实验设计")
    results: str = Field(..., description="预期结果")
    references: str = Field(..., description="参考文献")
    report_id: Optional[str] = Field(None, description="报告文件 ID")
    pdf_generated: Optional[bool] = Field(False, description="PDF 是否生成成功")
    status: Optional[str] = Field("draft", description="状态")
    version: Optional[int] = Field(1, description="版本")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据（如合规性检查结果）")


class ReportDBResponse(ReportCreate):
    """报告数据库响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    """创建数据集"""
    project_id: str = Field(..., description="项目 ID")
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="存储路径")
    file_size: Optional[int] = Field(None, description="文件大小 (bytes)")
    data_type: str = Field("unknown", description="数据类型")
    source_type: str = Field("upload", description="来源: upload/history/public")
    n_rows: Optional[int] = Field(None, description="行数")
    n_columns: Optional[int] = Field(None, description="列数")
    columns_json: Optional[str] = Field(None, description="列名列表 JSON")
    dtypes_json: Optional[str] = Field(None, description="字段类型 JSON")
    missing_count: Optional[int] = Field(None, description="缺失值总数")
    missing_rate: Optional[float] = Field(None, description="缺失率")
    statistics_json: Optional[str] = Field(None, description="统计信息 JSON")
    preview_json: Optional[str] = Field(None, description="前 N 行预览 JSON")
    preprocessing_status: str = Field("pending", description="预处理状态")
    use_for_hypothesis: bool = Field(True, description="是否用于假设生成")
    extra_metadata: Optional[str] = Field(None, description="额外元数据 JSON")


class DatasetResponse(BaseModel):
    """数据集响应"""
    id: str
    project_id: str
    filename: str
    file_path: str
    file_size: Optional[int] = None
    data_type: str
    source_type: str
    n_rows: Optional[int] = None
    n_columns: Optional[int] = None
    columns_json: Optional[str] = None
    dtypes_json: Optional[str] = None
    missing_count: Optional[int] = None
    missing_rate: Optional[float] = None
    statistics_json: Optional[str] = None
    preview_json: Optional[str] = None
    preprocessing_status: str
    use_for_hypothesis: bool
    extra_metadata: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
