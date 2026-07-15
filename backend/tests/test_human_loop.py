"""人在回路 API 基础测试"""

import pytest

from app.services.stage_human_loop_service import STAGE_KEY_ORDER, get_stage_meta





def test_stage_key_order_has_seven_stages():
    assert len(STAGE_KEY_ORDER) == 7
    assert STAGE_KEY_ORDER[2] == "knowledge_gap"
    assert STAGE_KEY_ORDER[3] == "hypothesis_generation"
    assert STAGE_KEY_ORDER[5] == "iterative_experiment"
    assert STAGE_KEY_ORDER[6] == "report_generation"





def test_get_stage_meta_empty():

    class FakeExec:

        extra_metadata = None



    assert get_stage_meta(FakeExec()) == {}





def test_parse_stage_invalid():

    from app.services.prompt_override_service import _parse_stage



    with pytest.raises(ValueError):

        _parse_stage("not_a_stage")





def test_stage_chat_uses_conversational_prompt_and_full_regen():

    from unittest.mock import MagicMock, patch



    from app.services.stage_chat_service import StageChatService



    mock_db = MagicMock()

    svc = StageChatService(mock_db)

    fake_detail = {

        "human_modified_output": {"hypotheses": [{"hypothesis": "H1"}]},

        "output_data": {"hypotheses": []},

        "input_data": {"research_question": "Q"},

    }

    fake_run = MagicMock()

    fake_run.research_question = "测试问题"

    fake_stage_exec = MagicMock()

    fake_stage_exec.extra_metadata = {"chat_history": [{"user_message": "上一轮", "assistant_explanation": "已修改"}]}



    with patch.object(svc.human_loop, "get_stage_detail", return_value=fake_detail), patch.object(

        svc, "_get_run", return_value=fake_run

    ), patch.object(svc, "_get_stage_exec", return_value=fake_stage_exec), patch.object(

        svc.human_loop, "save_human_edit", return_value=fake_stage_exec

    ), patch(

        "app.services.stage_chat_service._call_llm_for_revision"

    ) as mock_llm:

        mock_llm.return_value = {

            "revised_output": {"hypotheses": [{"hypothesis": "H1 revised"}]},

            "explanation": "已加强表述",

            "changes_summary": ["更新假设措辞"],

        }

        result = svc.chat(
            run_id="run-1",
            stage="hypothesis_generation",
            user_message="请更具体",
            apply_change=True,
            mode="revise",
        )



    mock_llm.assert_called_once()

    call_kwargs = mock_llm.call_args.kwargs

    assert "原始阶段输入" in call_kwargs["prompt"]

    assert "对话历史" in call_kwargs["prompt"]

    assert call_kwargs["prefer_full_regen"] is True

    assert result["explanation"] == "已加强表述"

    assert result["revised_output"]["hypotheses"][0]["hypothesis"] == "H1 revised"

    assert result["applied"] is True

    assert result["revision_mode"] == "full"

    assert len(result["chat_history"]) == 2





def test_resolve_regenerate_result_prefers_full_output():

    from app.services.stage_chat_service import _resolve_regenerate_result



    current = {"hypotheses": [{"hypothesis": "H1", "score": 8}], "summary": "ok"}

    parsed = {

        "revised_output": {"hypotheses": [{"hypothesis": "H1 revised"}]},

        "explanation": "done",

        "changes_summary": ["x"],

    }

    out = _resolve_regenerate_result(current, parsed)

    assert out["revised_output"]["hypotheses"][0]["hypothesis"] == "H1 revised"

    assert out["revised_output"]["hypotheses"][0]["score"] == 8

    assert out["revised_output"]["summary"] == "ok"

    assert out["mode"] == "full"





def test_resolve_regenerate_result_falls_back_to_delta():

    from app.services.stage_chat_service import _resolve_regenerate_result



    current = {"hypotheses": [{"hypothesis": "H1", "score": 8}], "summary": "ok"}

    parsed = {

        "output_delta": {"hypotheses": [{"hypothesis": "H1 delta"}]},

        "explanation": "done",

        "changes_summary": ["x"],

    }

    out = _resolve_regenerate_result(current, parsed)

    assert out["revised_output"]["hypotheses"][0]["hypothesis"] == "H1 delta"

    assert out["mode"] == "delta"





def test_format_chat_history_includes_prior_turns():

    from app.services.stage_chat_service import _build_conversational_prompt



    prompt = _build_conversational_prompt(

        stage="hypothesis_generation",

        research_question="RQ",

        input_data={"a": 1},

        current_output={"hypotheses": []},

        chat_history=[

            {"user_message": "第一轮", "assistant_explanation": "已调整"},

            {"user_message": "再具体", "assistant_explanation": "已加强"},

        ],

        user_message="继续改",

        prefer_full_regen=True,

    )

    assert "第一轮" in prompt

    assert "已加强" in prompt

    assert "继续改" in prompt


def test_save_human_edit_keeps_completed_status():
    from unittest.mock import MagicMock, patch

    from app.models.pipeline import PipelineStage, PipelineStatus
    from app.services.stage_human_loop_service import StageHumanLoopService

    mock_db = MagicMock()
    svc = StageHumanLoopService(mock_db)
    run = MagicMock()
    run.id = "run-db-id"
    run.project_id = "proj-1"
    stage_exec = MagicMock()
    stage_exec.status = PipelineStatus.COMPLETED
    stage_exec.output_data = {"chapters": {"problem_statement": "old"}}
    stage_exec.extra_metadata = {}
    mock_db.query.return_value.filter.return_value.first.return_value = stage_exec

    with patch.object(svc, "_get_run", return_value=run), patch(
        "app.services.report_service.ReportService.sync_from_stage_human_output",
        return_value="report-1",
    ):
        svc.save_human_edit(
            run_id="run-1",
            stage=PipelineStage.REPORT_GENERATION.value,
            output_data={"chapters": {"problem_statement": "new"}},
            human_feedback="修订摘要",
            action="chat_apply",
        )

    assert stage_exec.status == PipelineStatus.COMPLETED
    assert stage_exec.extra_metadata["human_edited"] is True


def test_advisory_chat_does_not_apply_changes():
    from unittest.mock import MagicMock, patch

    from app.services.stage_chat_service import StageChatService

    mock_db = MagicMock()
    svc = StageChatService(mock_db)
    fake_detail = {
        "human_modified_output": None,
        "output_data": {"plots": [{"title": "fig1"}]},
        "input_data": {},
    }
    fake_run = MagicMock()
    fake_run.research_question = "测试"
    stage_exec = MagicMock()
    stage_exec.extra_metadata = {}

    with patch.object(svc.human_loop, "get_stage_detail", return_value=fake_detail), patch.object(
        svc, "_get_run", return_value=fake_run
    ), patch.object(svc, "_get_stage_exec", return_value=stage_exec), patch.object(
        svc.human_loop, "save_human_edit"
    ) as mock_save, patch(
        "app.services.stage_chat_service.qwen_structured_chat"
    ) as mock_llm:
        mock_llm.return_value = {
            "answer": "该图展示标签分布差异",
            "related_suggestions": ["可尝试 FedProx"],
        }
        result = svc.chat(
            run_id="run-1",
            stage="report_generation",
            user_message="这个图表什么意思？",
            mode="advisory",
        )

    assert result["applied"] is False
    assert result["revision_mode"] == "advisory"
    assert "标签分布" in result["explanation"]
    mock_save.assert_not_called()


def test_summarize_downstream_context_for_rerun():
    from unittest.mock import MagicMock

    from app.models.pipeline import PipelineStage
    from app.services.stage_human_loop_service import StageHumanLoopService

    mock_db = MagicMock()
    parent = MagicMock()
    parent.id = "parent-db-id"

    lit_exec = MagicMock()
    lit_exec.stage = PipelineStage.ITERATIVE_EXPERIMENT
    lit_exec.stage_order = 6
    lit_exec.output_data = {"warnings": ["数据列缺失 age"], "status": "blocked_need_data"}
    lit_exec.extra_metadata = {"human_feedback": "请补全人口学变量"}

    lit_exec2 = MagicMock()
    lit_exec2.stage = PipelineStage.HYPOTHESIS_GENERATION
    lit_exec2.stage_order = 4
    lit_exec2.output_data = {"hypotheses": [{"hypothesis": "联邦学习可提升 AUC"}]}
    lit_exec2.extra_metadata = {}

    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        lit_exec2,
        lit_exec,
    ]

    svc = StageHumanLoopService(mock_db)
    summaries = svc.summarize_downstream_context_for_rerun(parent, "literature_mining")

    assert any("假设" in s for s in summaries)
    assert any("迭代实验" in s or "数据列缺失" in s for s in summaries)
    assert all(s.startswith("[项目进展]") for s in summaries)

