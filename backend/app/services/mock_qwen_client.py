"""
Mock Qwen 客户端 —— 不真实调用 API 也能测试 Pipeline

使用方式：
  from app.services.mock_qwen_client import use_mock
  use_mock()  # 注入 MockQwenClient 替换全局单例

  # 或手动设置特定 agent 的响应
  from app.services.mock_qwen_client import MockQwenClient
  mock = MockQwenClient()
  mock.set_response("problem_understanding", {...})
"""
import json
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from app.services.qwen_client import (
    QwenClient, QwenError, QwenAPIError, 
    get_qwen_client, _set_qwen_client,
    get_call_logs
)

logger = logging.getLogger(__name__)


def _find_in_prompt(prompt: str, *keywords: str) -> Optional[str]:
    """在 prompt 中查找关键字，返回匹配的第一个关键字"""
    for kw in keywords:
        if kw.lower() in prompt.lower():
            return kw
    return None


class MockQwenClient(QwenClient):
    """
    Mock Qwen 客户端

    - 重写 structured_chat 和 chat，不发起真实 HTTP 请求
    - 根据 schema_example 自动生成合理的假数据
    - 支持 preset_responses 预设特定响应
    - 仍然记录调用日志
    """

    def __init__(self):
        # 不初始化真实 OpenAI client
        self.api_key = "mock-key"
        self.base_url = "mock://"
        self.model = "mock-model"
        self.timeout = 0
        self.max_retries = 0
        self.client = None

        # 预设响应映射：key → 固定返回值
        self.preset_responses: Dict[str, dict] = {}

        logger.info("MockQwenClient initialized (no real API calls will be made)")

    def set_response(self, key: str, response: dict):
        """为特定的 agent/场景预设响应"""
        self.preset_responses[key] = response

    def _generate_mock_from_schema(self, schema: dict) -> dict:
        """根据 schema_example 自动生成模拟数据"""
        def _gen_value(v):
            if isinstance(v, str):
                return f"mock_{v[:20]}"
            elif isinstance(v, bool):
                return v
            elif isinstance(v, int):
                return v if v != 0 else 5
            elif isinstance(v, float):
                return 0.75 if v > 0 else v
            elif isinstance(v, list):
                if len(v) == 0:
                    return []
                return [_gen_value(v[0])]
            elif isinstance(v, dict):
                return {k: _gen_value(val) for k, val in v.items()}
            elif v is None:
                return None
            return str(v)

        return {k: _gen_value(v) for k, v in schema.items()}

    def structured_chat(
        self,
        prompt: str,
        schema_example: Optional[Union[Dict[str, Any], str]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        prompt_version: str = ""
    ) -> Dict[str, Any]:
        """
        Mock 结构化对话：根据 prompt 关键词匹配预设响应，或根据 schema 自动生成
        """
        t0 = time.time()
        mock_result = None

        # 1. 查找预设响应
        for key, response in self.preset_responses.items():
            if key in prompt:
                mock_result = response
                break

        # 2. 根据 schema 自动生成
        if mock_result is None and isinstance(schema_example, dict):
            mock_result = self._generate_mock_from_schema(schema_example)

        # 3. 兜底
        if mock_result is None:
            mock_result = {"mock": True, "message": "MockQwenClient — no schema or preset matched"}

        # 模拟 API 延迟
        time.sleep(0.01)
        duration_ms = int((time.time() - t0) * 1000)

        # 记录日志
        self._log_call(
            model_name="mock-model",
            temperature=temperature,
            prompt_version=prompt_version,
            input_text=prompt,
            output_text=json.dumps(mock_result, ensure_ascii=False),
            duration_ms=duration_ms,
            success=True
        )

        logger.info(f"[MockQwen] structured_chat returned {len(json.dumps(mock_result))} bytes")
        return mock_result

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0
    ) -> str:
        """Mock 普通对话"""
        t0 = time.time()
        result = f"[MockQwen response to: {prompt[:50]}...]"
        time.sleep(0.01)
        duration_ms = int((time.time() - t0) * 1000)

        self._log_call(
            model_name="mock-model",
            temperature=temperature,
            prompt_version="",
            input_text=prompt,
            output_text=result,
            duration_ms=duration_ms,
            success=True
        )
        return result

    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> str:
        """Mock 多轮对话"""
        last_msg = messages[-1]["content"] if messages else "empty"
        return self.chat(prompt=last_msg, temperature=temperature)


# ==================== 便捷注入函数 ====================

def use_mock(
    preset_responses: Optional[Dict[str, dict]] = None
) -> MockQwenClient:
    """
    注入 MockQwenClient 替换全局 QwenClient 单例

    使用后所有 Agent 调用 qwen_structured_chat/qwen_chat 都会走 mock。

    Args:
        preset_responses: 预设响应字典 {keyword: response_dict}

    Returns:
        MockQwenClient 实例

    Example:
        from app.services.mock_qwen_client import use_mock

        mock = use_mock({
            "problem_understanding": {
                "problem_statement": "测试问题",
                "research_domain": "AI",
                "keywords": ["test"],
                "scope_boundary": "test scope",
                "constraints": ["c1"],
                "expected_output": ["o1"]
            }
        })
    """
    mock = MockQwenClient()
    if preset_responses:
        for key, resp in preset_responses.items():
            mock.set_response(key, resp)
    _set_qwen_client(mock)
    logger.info("MockQwenClient injected as global QwenClient singleton")
    return mock


def restore_real_client():
    """恢复真实的 QwenClient 单例"""
    _set_qwen_client(QwenClient())
    logger.info("Real QwenClient restored")


# ==================== 测试辅助 ====================

def run_mock_pipeline_test() -> Dict[str, Any]:
    """
    运行完整的 Mock Pipeline 测试，验证所有 Agent 链路可用

    Returns:
        测试结果摘要
    """
    from app.agents import (
        get_problem_understanding_agent,
        get_literature_mining_agent,
        get_knowledge_gap_agent,
        get_hypothesis_generation_agent,
        get_hypothesis_review_agent,
        get_experiment_design_agent,
        get_small_validation_agent,
        get_report_generation_agent,
    )
    from app.services.qwen_client import clear_call_logs, get_call_logs

    logger.info("=" * 60)
    logger.info("开始 Mock Pipeline 测试")
    logger.info("=" * 60)

    # 注入 mock
    use_mock()
    clear_call_logs()

    test_results = {}
    errors = []

    try:
        # 1. Problem Understanding
        logger.info("[1/8] 测试 ProblemUnderstandingAgent...")
        agent = get_problem_understanding_agent()
        result = agent.analyze("测试研究问题：AI 在医学中的应用")
        test_results["problem_understanding"] = {
            "status": "OK",
            "fields": list(result.model_dump().keys())
        }

        # 2. Literature Mining（需要向量索引，跳过实际检索）
        logger.info("[2/8] 测试 LiteratureMiningAgent...")
        lit_agent = get_literature_mining_agent()
        # 模拟搜索结果
        from app.services.vector_store import SearchResult
        mock_chunks = [
            SearchResult(
                chunk_id="chunk_001",
                document_id="doc_001",
                content="模拟文献内容：AI 技术在医学影像分析中表现优异",
                page_number=1,
                source_title="模拟论文 A",
                similarity_score=0.9
            )
        ]
        # 直接测试 _extract_facts（绕过向量搜索）
        formatted = lit_agent._format_chunks(mock_chunks)
        extract_result = lit_agent._extract_facts("AI 医学应用", formatted)
        test_results["literature_mining"] = {
            "status": "OK",
            "fields": list(extract_result.keys())
        }

        # 3. Knowledge Gap
        logger.info("[3/8] 测试 KnowledgeGapAgent...")
        gap_agent = get_knowledge_gap_agent()
        from app.agents.literature_mining_agent import ScienceFact
        mock_facts = [
            ScienceFact(
                fact_id="f_001",
                content="AI 可辅助医学诊断",
                source_chunk_id="c_001",
                source_paper_title="论文A"
            )
        ]
        gap_result = gap_agent.analyze(mock_facts, ["AI 的准确性不确定"])
        test_results["knowledge_gap"] = {
            "status": "OK",
            "fields": list(gap_result.model_dump().keys())
        }

        # 4. Hypothesis Generation
        logger.info("[4/8] 测试 HypothesisGenerationAgent...")
        hypo_gen_agent = get_hypothesis_generation_agent()
        hypo_result = hypo_gen_agent.generate(
            research_question="AI 医学应用",
            facts=[{"content": "AI 有效", "source_paper_title": "论文A"}],
            knowledge_gaps=[{"description": "数据不足", "potential_value": "高"}],
            constraints=["时间有限"]
        )
        test_results["hypothesis_generation"] = {
            "status": "OK",
            "count": len(hypo_result.hypotheses)
        }

        # 5. Hypothesis Review
        logger.info("[5/8] 测试 HypothesisReviewAgent...")
        from app.agents.hypothesis_review_agent import HypothesisCandidate
        review_agent = get_hypothesis_review_agent()
        candidates = [
            HypothesisCandidate(
                hypothesis=h.hypothesis,
                rationale=h.rationale,
                novelty=h.novelty,
                testability=h.testability,
                required_data=h.required_data,
                possible_method=h.possible_method,
                risk=h.risk
            )
            for h in hypo_result.hypotheses
        ]
        review_result = review_agent.review(candidates)
        test_results["hypothesis_review"] = {
            "status": "OK",
            "count": len(review_result.reviews)
        }

        # 6. Experiment Design
        logger.info("[6/8] 测试 ExperimentDesignAgent...")
        exp_agent = get_experiment_design_agent()
        top_hypo = hypo_result.hypotheses[0]
        exp_result = exp_agent.design_experiment(
            hypothesis=top_hypo.hypothesis,
            rationale=top_hypo.rationale,
            novelty=top_hypo.novelty,
            testability=top_hypo.testability,
            required_data=top_hypo.required_data,
            possible_method=top_hypo.possible_method,
            risk=top_hypo.risk
        )
        test_results["experiment_design"] = {
            "status": "OK",
            "fields": list(exp_result.keys())
        }

        # 7. Small Validation
        logger.info("[7/8] 测试 SmallValidationAgent...")
        val_agent = get_small_validation_agent()
        val_result = val_agent.generate_validation(
            hypothesis=top_hypo.hypothesis,
            methods=exp_result.get("methods", ""),
            datasets=exp_result.get("datasets", ""),
            metrics=exp_result.get("metrics", "")
        )
        test_results["small_validation"] = {
            "status": "OK",
            "fields": list(val_result.keys())
        }

        # 8. Report Generation
        logger.info("[8/8] 测试 ReportGenerationAgent...")
        report_agent = get_report_generation_agent()
        report_result = report_agent.generate_report(
            project_info={"title": "Mock 测试项目"},
            problem_understanding=test_results["problem_understanding"],
            literature_facts=[{"fact_id": "f_001", "content": "AI 有效"}],
            citation_map=[],
            knowledge_gaps={"knowledge_gaps": []},
            final_hypothesis={"hypothesis": top_hypo.hypothesis},
            experiment_design=exp_result,
            small_validation=val_result
        )
        test_results["report_generation"] = {
            "status": "OK",
            "fields": list(report_result.keys())
        }

    except Exception as e:
        logger.error(f"Mock pipeline test failed: {e}", exc_info=True)
        errors.append(str(e))

    # 收集日志
    logs = get_call_logs()

    # 恢复真实客户端
    restore_real_client()

    summary = {
        "test_name": "Mock Pipeline 全链路测试",
        "overall_status": "PASSED" if not errors else "FAILED",
        "stages_tested": len(test_results),
        "test_results": test_results,
        "errors": errors,
        "call_logs_count": len(logs),
        "call_logs": [{
            "model": l.model_name,
            "temperature": l.temperature,
            "prompt_version": l.prompt_version,
            "duration_ms": l.duration_ms,
            "success": l.success
        } for l in logs]
    }

    logger.info("=" * 60)
    logger.info(f"Mock Pipeline 测试完成: {summary['overall_status']}")
    logger.info(f"  测试阶段: {summary['stages_tested']}/8")
    logger.info(f"  Qwen 调用日志: {summary['call_logs_count']} 条")
    if errors:
        logger.info(f"  错误: {errors}")
    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    # 直接运行此文件可执行 mock 测试
    import sys
    sys.path.insert(0, ".")
    summary = run_mock_pipeline_test()
    print(json.dumps(summary, ensure_ascii=False, indent=2))