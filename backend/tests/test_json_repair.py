"""JSON 修复逻辑单元测试"""
import pytest

from app.services.qwen_client import _repair_json, _safe_json_loads


def test_safe_json_loads_normal():
    assert _safe_json_loads('{"a": 1}') == {"a": 1}


def test_safe_json_loads_markdown():
    assert _safe_json_loads('```json\n{"a": 1}\n```') == {"a": 1}


def test_repair_json_trailing_commas():
    assert _repair_json('{"a": 1, "b": [1,2,], "c": {"d": 3,},}') == {
        "a": 1,
        "b": [1, 2],
        "c": {"d": 3},
    }


def test_repair_json_python_literals():
    assert _repair_json('{"a": None, "b": True, "c": False}') == {
        "a": None,
        "b": True,
        "c": False,
    }


def test_repair_json_truncated():
    assert _repair_json('{"a": 1, "b": [1, 2') == {"a": 1, "b": [1, 2]}


def test_repair_json_extract_from_text():
    assert _repair_json('这是解释文字 {"result": "ok"} 后面还有文字') == {"result": "ok"}


def test_repair_json_python_single_quotes():
    assert _repair_json("{'key': 'value', 'num': 42}") == {"key": "value", "num": 42}


def test_repair_json_strips_null_control_characters():
    raw = '{"a": "ok\x00bad", "b": 1}'
    assert _repair_json(raw) == {"a": "okbad", "b": 1}


def test_repair_json_invalid_raises():
    with pytest.raises(Exception):
        _repair_json("this is not json at all")
