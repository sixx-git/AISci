"""
端到端 Pipeline 测试（Mock 模式，不调用真实 Qwen API）
运行方式：
  cd backend
  $env:PYTHONPATH = "."
  python tests/test_pipeline_e2e.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 初始化内存数据库
from app.models.core import Base
engine = create_engine("sqlite:///:memory:", echo=False)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# 注入 Mock 客户端
from app.services.mock_qwen_client import use_mock, restore_real_client, MockQwenClient

# 注入 Mock 向量存储（绕过向量索引依赖）
from unittest.mock import patch
from app.services.vector_store import SearchResult
_mock_search_results = [
    SearchResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        content="本研究探讨了深度学习在医学影像诊断中的应用。通过对比实验发现，基于迁移学习的模型在数据量较少时性能显著优于传统方法。",
        page_number=1,
        source_title="深度学习在医学影像中的应用",
        similarity_score=0.95
    ),
    SearchResult(
        chunk_id="chunk-2",
        document_id="doc-1",
        content="实验结果表明，自适应特征选择能够提升小样本学习模型的泛化能力约15%。",
        page_number=2,
        source_title="深度学习在医学影像中的应用",
        similarity_score=0.87
    ),
    SearchResult(
        chunk_id="chunk-3",
        document_id="doc-2",
        content="小样本学习的关键挑战在于如何有效利用先验知识来弥补训练数据的不足。",
        page_number=1,
        source_title="小样本学习综述",
        similarity_score=0.82
    )
]

_vector_store_patcher = patch(
    'app.agents.literature_mining_agent.search_vector_store',
    return_value=_mock_search_results
)
_vector_store_patcher.start()
print("向量存储 Mock 注入 OK")

# 预设每个阶段的 Mock 响应
mock = use_mock(preset_responses={
    "problem_understanding": {
        "problem_statement": "研究问题陈述",
        "research_domain": "人工智能",
        "keywords": ["机器学习", "深度学习"],
        "scope_boundary": "小样本学习场景",
        "constraints": ["数据量限制"],
        "expected_output": ["性能提升方案"]
    },
    "literature_mining": {
        "citation_map": [
            {"title": "论文A", "authors": ["Author1"], "year": 2024, "summary": "相关研究摘要"}
        ],
        "facts": [
            {"fact_id": "f1", "content": "事实1", "source_paper_title": "论文A", "confidence": 0.9}
        ],
        "uncertain_points": [
            {"id": "u1", "description": "不确定点1"}
        ]
    },
    "knowledge_gap": {
        "known_facts": [
            {"fact_id": "f1", "content": "已知事实1", "source_paper_title": "论文A"},
            {"fact_id": "f2", "content": "已知事实2", "source_paper_title": "论文B"}
        ],
        "knowledge_gaps": [
            {"gap_id": "g1", "description": "研究缺口1：现有方法未充分验证", "basis": ["f1"], "potential_value": "高"},
            {"gap_id": "g2", "description": "研究缺口2：缺乏对比实验", "basis": ["f2"], "potential_value": "中"}
        ],
        "contradictions": [
            {"contradiction_id": "c1", "fact_ids": ["f1", "f2"], "description": "结果矛盾"}
        ],
        "possible_connections": [
            {"connection_id": "p1", "fact_ids": ["f1", "f2"], "description": "特征选择与泛化能力相关", "confidence": 0.75}
        ],
        "research_opportunities": [
            {"opportunity_id": "r1", "title": "新机会", "description": "探索自适应特征选择", "related_gap_ids": ["g1"], "expected_impact": "显著", "feasibility": 0.8}
        ]
    },
    "hypothesis_generation": {
        "hypotheses": [
            {
                "hypothesis": "假设1：自适应特征选择可提升小样本泛化能力",
                "rationale": "基于迁移学习理论",
                "novelty": "高",
                "testability": "中",
                "required_data": "数据集X",
                "possible_method": "方法Y",
                "risk": "低"
            }
        ],
        "summary": "生成了1个候选假设"
    },
    "hypothesis_review": {
        "reviews": [
            {
                "hypothesis_index": 0,
                "hypothesis": "假设1：自适应特征选择可提升小样本泛化能力",
                "scores": {
                    "scientific_value": {"score": 8, "reason": "具有重要科学价值"},
                    "novelty": {"score": 7, "reason": "有一定创新性"},
                    "testability": {"score": 8, "reason": "实验可验证"},
                    "data_availability": {"score": 7, "reason": "数据可获取"},
                    "cost_risk": {"score": 8, "reason": "成本可控"}
                },
                "overall_score": 7.8,
                "suggestions": "建议增加对比实验",
                "strengths": ["创新性好", "实用价值高"],
                "weaknesses": ["样本量可能不足"]
            }
        ],
        "summary": "总体评价通过，建议继续"
    },
    "experiment_design": {
        "hypothesis": "假设1",
        "objective": "实验目标",
        "methods": "实验方法",
        "datasets": ["数据集X"],
        "metrics": ["准确率"],
        "baselines": ["基线方法"],
        "steps": [{"step": 1, "title": "步骤1", "description": "描述"}]
    },
    "small_validation": {
        "hypothesis": "假设1",
        "validation_result": "验证通过",
        "confidence_score": 0.85,
        "issues": [],
        "suggestions": ["建议改进"]
    },
    "report_generation": {
        "paper_title": "研究报告标题",
        "paper_abstract": "研究摘要",
        "markdown_content": "# 研究报告\n\n内容...",
        "chapters": {
            "problem_statement": "问题陈述",
            "methods": "方法",
            "results": "结果",
            "references": ["参考文献1"]
        }
    }
})

print("=" * 60)
print("  端到端 Pipeline Mock 测试开始")
print("=" * 60)

# 创建测试 session 和项目
db = SessionLocal()

# 创建测试项目（Pipeline 运行需要项目存在）
from app.models.project import Project
import uuid
project_id = str(uuid.uuid4())
project = Project(
    id=project_id,
    name="测试项目",
    description="E2E 测试项目",
    status="draft"
)
db.add(project)
db.commit()

# 创建 Pipeline 请求
from app.schemas.pipeline import PipelineRunRequest
from app.services.pipeline_service import PipelineService
from app.services.qwen_client import get_call_logs, clear_call_logs

request = PipelineRunRequest(
    project_id=project_id,
    research_question="测试研究问题：如何验证端到端 Pipeline？"
)

print(f"\n项目 ID: {project_id}")
print(f"研究问题: {request.research_question}")

# 运行 Pipeline
print("\n--- 开始运行 Pipeline ---")
pipeline_service = PipelineService(db)
clear_call_logs()

try:
    result = pipeline_service.run_pipeline(request)
    
    print(f"\nPipeline 状态: {result.status}")
    print(f"运行 ID: {result.run_id}")
    print(f"总耗时: {result.total_duration:.2f}s")
    print(f"报告 ID: {result.final_report_id}")
    print(f"失败阶段: {result.failed_stage or '无'}")
    
    print(f"\n各阶段状态:")
    for i, stage in enumerate(result.stages):
        state = "✓" if stage.status == "completed" else "✗"
        dur = f"({stage.duration:.2f}s)" if stage.duration else ""
        print(f"  {i+1}. [{state}] {stage.stage.value} {dur}")
        if stage.error_message:
            print(f"      错误: {stage.error_message}")
    
    # 验证调用日志
    logs = get_call_logs()
    print(f"\n调用日志: {len(logs)} 条记录")
    for log in logs:
        print(f"  - {log.prompt_version}: {log.model_name}, {log.temperature}, {log.duration_ms}ms")
    
    # 验证数据库记录
    from app.models.pipeline import PipelineRun as DB_PipelineRun, PipelineStageExecution
    db_run = db.query(DB_PipelineRun).filter(DB_PipelineRun.run_id == result.run_id).first()
    print(f"\n数据库记录:")
    print(f"  PipelineRun: {db_run.status.value}, 阶段数: {len(db_run.stage_executions)}")
    
    for se in db_run.stage_executions:
        model_info = f"model={se.model_used}" if se.model_used else "no model"
        params = se.model_parameters or {}
        prompt_len = len(se.prompt_used) if se.prompt_used else 0
        print(f"    [{se.stage_order}] {se.stage.value}: {se.status.value}, "
              f"duration={se.duration_ms}ms, {model_info}, "
              f"temp={params.get('temperature', 'N/A')}, "
              f"prompt_len={prompt_len}")
    
    # 最终判定
    assert result.status == "completed", f"Pipeline 应该完成，实际: {result.status}"
    assert len(result.stages) == 8, f"应该 8 个阶段，实际 {len(result.stages)}"
    assert all(s.status == "completed" for s in result.stages), "所有阶段应完成"
    assert result.final_report_id is not None, "应该有报告 ID"
    assert len(logs) >= 1, f"至少 1 条调用日志，实际 {len(logs)}"
    
    print("\n" + "=" * 60)
    print("  所有测试通过! ✓")
    print("=" * 60)
    
except Exception as e:
    print(f"\n测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    restore_real_client()
    db.close()