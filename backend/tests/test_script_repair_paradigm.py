"""script_repair 自适应：语义指纹 + 通用/联邦范式分治。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "shaxiang-main" / "shaxiang-main"
sys.path.insert(0, str(ROOT))

from core.script_repair import (  # noqa: E402
    _repair_hint_for_error,
    _select_repair_mode,
    error_fingerprint,
    infer_experiment_paradigm,
)


def test_error_fingerprint_ignores_line_drift():
    e1 = (
        "smoke_run 失败: ValueError: The number of classes has to be greater than one; got 1 class\n"
        "【出错位置】脚本约第 120 行（run）"
    )
    e2 = (
        "smoke_run 失败: ValueError: The number of classes has to be greater than one; got 1 class\n"
        "【出错位置】脚本约第 135 行（run）"
    )
    assert error_fingerprint(e1) == error_fingerprint(e2)
    assert error_fingerprint(e1).startswith("valueerror:")


def test_same_error_streak_can_escalate():
    assert _select_repair_mode(1) == "local"
    assert _select_repair_mode(2) == "diagnose"
    assert _select_repair_mode(3) == "broader"


def test_infer_federated_from_fl_feedback():
    fb = (
        "[FL 实验范式 — 内容注入，非多机 runtime]\n"
        "- 档位: 标准 Non-IID（Dirichlet + FedProx 对比） (`standard_non_iid`)\n"
        "- 数据划分: method=dirichlet alpha=0.1 num_clients=20\n"
        "- 必跑基线: local_only, centralized, FedAvg, FedProx\n"
    )
    assert (
        infer_experiment_paradigm(
            research_goal="素数间隔密度模型",
            human_feedback=fb,
            script="",
        )
        == "federated"
    )


def test_infer_general_without_fl_signals():
    assert (
        infer_experiment_paradigm(
            research_goal="用随机森林预测表格标签并做 5 折交叉验证",
            human_feedback="",
            script="def run(df, params):\n    from sklearn.ensemble import RandomForestClassifier\n",
        )
        == "general"
    )


def test_explicit_paradigm_wins():
    assert (
        infer_experiment_paradigm(
            research_goal="FedAvg Non-IID",
            human_feedback="FedAvg FedProx",
            script="FedAvg",
            explicit="general",
        )
        == "general"
    )


def test_class_fail_hints_are_paradigm_split():
    err = "ValueError: The number of classes has to be greater than one; got 1 class"
    fl_hint = _repair_hint_for_error(err, {}, paradigm="federated")
    gen_hint = _repair_hint_for_error(err, {}, paradigm="general")
    assert "联邦" in fl_hint
    assert "全局单模型" in fl_hint or "勿改写成" in fl_hint
    assert "SMOTE" not in fl_hint  # 联邦路径不应默认推销通用过采样
    assert "通用" in gen_hint or "分层采样" in gen_hint
    assert "联邦客户端" in gen_hint  # 明确禁止混入联邦
    assert "FedAvg" not in gen_hint or "不要引入" in gen_hint


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
