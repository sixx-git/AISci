from pydantic import BaseModel, Field


class DatasetRecommendation(BaseModel):
    """单条数据集推荐"""
    name: str = Field(..., description="数据集名称")
    description: str = Field("", description="数据集描述")
    source_type: str = Field("uploaded", description="来源类型: uploaded, huggingface, url")
    download_url: str = Field("", description="下载链接或 HuggingFace ID")
    file_format: str = Field("csv", description="文件格式: csv, json, parquet")
    is_required: bool = Field(False, description="是否必须上传（True=必须, False=可选补充）")
    reason: str = Field("", description="推荐理由：这个数据集如何帮助验证假设")
    expected_columns: list[str] = Field(default_factory=list, description="预期的关键字段")
    size_hint: str = Field("", description="数据集大小提示（如 ~10K rows）")


class DatasetRecommendationReport(BaseModel):
    """数据集推荐报告（LLM生成）"""
    hypothesis_summary: str = Field("", description="对用户假设的理解")
    recommended_datasets: list[DatasetRecommendation] = Field(default_factory=list)
    alternative_approaches: list[str] = Field(default_factory=list, description="如果数据不可用时的替代方案")
    data_preparation_notes: str = Field("", description="数据准备注意事项")
