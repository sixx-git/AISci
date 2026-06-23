"""人在回路 API 基础测试"""
import pytest
from app.services.stage_human_loop_service import STAGE_KEY_ORDER, get_stage_meta


def test_stage_key_order_has_nine_stages():
    assert len(STAGE_KEY_ORDER) == 9
    assert STAGE_KEY_ORDER[2] == "data_acquisition"
    assert STAGE_KEY_ORDER[4] == "hypothesis_generation"
    assert STAGE_KEY_ORDER[6] == "experiment_design"


def test_get_stage_meta_empty():
    class FakeExec:
        extra_metadata = None

    assert get_stage_meta(FakeExec()) == {}


def test_parse_stage_invalid():
    from app.services.prompt_override_service import _parse_stage

    with pytest.raises(ValueError):
        _parse_stage("not_a_stage")
