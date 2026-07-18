"""
IDE 式脚本修复循环：生成/修补 → smoke_run → 把报错喂回 LLM → 再修。
"""
from __future__ import annotations

import logging
import re
from typing import Literal, Optional

from llm.client import LLMClient
from llm.prompts import (
    SANDBOX_SCRIPT_PATCH_SYSTEM_PROMPT,
    SANDBOX_SCRIPT_PATCH_USER_TEMPLATE,
)
from schemas.experiment import ExperimentPlan
from core.script_validator import smoke_run_plan, validate_plan_static

logger = logging.getLogger(__name__)

RepairMode = Literal["local", "diagnose", "broader"]


def get_plan_script(plan: ExperimentPlan) -> str:
    params = plan.parameters or {}
    return (params.get("script") or plan.analysis_script or "").strip()


def lock_script_body(target: ExperimentPlan, source: ExperimentPlan) -> ExperimentPlan:
    """强制目标方案使用 source 的脚本正文（参数可保留 target 的）。"""
    script = get_plan_script(source)
    if not script:
        return target
    plan = target.model_copy(deep=True)
    params = dict(plan.parameters or {})
    params["script"] = script
    plan.parameters = params
    plan.analysis_script = script
    return plan


def normalize_column_params(plan: ExperimentPlan, column_contract: dict) -> ExperimentPlan:
    """把 feature_columns / target_column 对齐到真实列契约（含 int/str 列名）。"""
    plan = plan.model_copy(deep=True)
    params = dict(plan.parameters or {})
    script_params = dict(plan.script_params or {})
    if isinstance(params.get("script_params"), dict):
        script_params.update(params["script_params"])

    columns = list(column_contract.get("columns") or [])
    numeric_cols = list(column_contract.get("numeric_columns") or [])
    suggested = list(column_contract.get("suggested_target_columns") or [])
    col_by_str = {str(c): c for c in columns}
    num_by_str = {str(c): c for c in numeric_cols}

    def _resolve(name, pool_by_str, pool):
        if name in pool:
            return name
        if name is None:
            return None
        return pool_by_str.get(str(name))

    feats = script_params.get("feature_columns")
    if isinstance(feats, list) and (numeric_cols or columns):
        resolved = []
        for f in feats:
            hit = _resolve(f, num_by_str, numeric_cols) if numeric_cols else _resolve(f, col_by_str, columns)
            if hit is not None and hit not in resolved:
                resolved.append(hit)
        script_params["feature_columns"] = resolved or list(numeric_cols)[:9] or list(columns)[:9]

    target = script_params.get("target_column")
    resolved_target = _resolve(target, col_by_str, columns) if target is not None else None
    if resolved_target is None and suggested:
        resolved_target = _resolve(suggested[0], col_by_str, columns) or suggested[0]
    if resolved_target is not None:
        script_params["target_column"] = resolved_target

    # 大数据默认采样，避免全量
    if not script_params.get("sample_size"):
        row_count = column_contract.get("row_count") or 0
        if isinstance(row_count, (int, float)) and row_count > 50000:
            script_params["sample_size"] = 30000

    params["script_params"] = script_params
    script = get_plan_script(plan)
    if script:
        params["script"] = script
        plan.analysis_script = plan.analysis_script or script
    plan.parameters = params
    plan.script_params = script_params
    return plan


def error_fingerprint(error_message: str) -> str:
    """归一化错误指纹，用于识别「同错反复」。"""
    text = error_message or ""
    # 优先用短错误行（enriched 包的第一行）
    first = text.strip().splitlines()[0] if text.strip() else ""
    # 优先【出错位置】，避免匹配到 traceback 里 File ... line 1
    locus_m = re.search(r"出错位置】脚本约第\s*(\d+)\s*行", text)
    if locus_m:
        line = locus_m.group(1)
    else:
        line_ms = list(re.finditer(r"line\s+(\d+)", text, flags=re.I))
        line = line_ms[-1].group(1) if line_ms else "?"
    exc_m = re.search(
        r"(ValueError|KeyError|TypeError|IndexError|AttributeError|NameError|"
        r"RuntimeError|ImportError|ModuleNotFoundError|AssertionError|"
        r"LinAlgError|MemoryError)[:\s]+(.+)",
        first,
        flags=re.I,
    )
    if exc_m:
        body = exc_m.group(1) + ":" + exc_m.group(2)
    else:
        body = first[:240]
    body = re.sub(r"\d+", "N", body)
    body = re.sub(r"\s+", " ", body).strip().lower()
    return f"{line}|{body}"


def _repair_hint_for_error(error_message: str, column_contract: dict) -> str:
    """针对常见失败给出检查点提示（软引导，不注入固定修复代码）。"""
    err = (error_message or "").lower()
    hints = []
    non_num = list(column_contract.get("non_numeric_columns") or [])
    if "n_splits" in err or "number of groups" in err or ("groups" in err and "split" in err):
        group_candidates = [
            c for c in non_num
            if str(c).lower() in {"sensor", "subject", "subject_id", "run", "filename"}
            or "sensor" in str(c).lower()
            or "subject" in str(c).lower()
        ]
        hints.append(
            "GroupKFold 组数不足：不要用 class/label 当 groups；"
            f"改用候选分组列 {group_candidates or non_num[:3]}，并写 "
            "n_splits = min(5, len(np.unique(groups)))；若唯一组数<3 用 GroupShuffleSplit。"
        )
    if "keyerror" in err:
        hints.append("列名不存在：从列契约读取真实列名，feature 只用 numeric_columns。")
    if "could not convert string to float" in err or "d01" in err:
        hints.append("非数值列进入了特征矩阵：从 feature_columns 排除字符串列后再训练。")
    if (
        "same number of dimensions" in err
        or "all the input array dimensions" in err
        or ("concatenate" in err and "dimension" in err)
        or ("vstack" in err and "dimension" in err)
    ):
        hints.append(
            "数组维度不一致：检查 np.concatenate / vstack / hstack 两侧的 .ndim/.shape；"
            "标签 y 应用 1D（避免 df[[col]].values 得到 (n,1)），"
            "特征 X 保持 2D (n, d)；合成样本与真实样本拼接前先对齐维度。"
        )
    if "inconsistent numbers of samples" in err or "found input variables with inconsistent" in err:
        hints.append(
            "样本数不一致：确认 X/y 以及增强后 X_aug/y_aug 行数相同；"
            "过滤合成样本时应对 X_synth 与 y_synth 使用同一 mask。"
        )
    if "boolean index did not match" in err:
        hints.append("布尔索引长度不匹配：mask 长度必须等于被索引数组第 0 维。")
    if "f1" in err or "only 1 class" in err or "n_samples" in err or "imbalance" in err:
        hints.append(
            "类不平衡/样本过少：增大 script_params.sample_size（如 20000~50000），"
            "并对标签做正确二分类编码；SMOTE 前检查少数类至少有 k+1 个样本。"
        )
    if "memory" in err or "unable to allocate" in err:
        hints.append("内存不足：减小 sample_size / n_estimators，避免对全量做 O(n²) 核矩阵。")
    if "modulenotfound" in err or "no module named" in err:
        hints.append("缺少依赖：改用 sklearn/numpy/pandas/matplotlib 已有能力，勿依赖未安装包。")
    return "\n".join(f"- {h}" for h in hints)


def _repair_mode_instructions(mode: RepairMode, same_error_streak: int) -> str:
    if mode == "local":
        return (
            "【修复模式=local】尽量局部修改出错代码附近；"
            "先根据 traceback 与【出错代码附近】定位，再改最少行数。"
        )
    if mode == "diagnose":
        return (
            f"【修复模式=diagnose】同一错误已连续出现 {same_error_streak} 次。"
            "必须先在 diagnosis 写清根因（哪两个数组/变量维度或逻辑冲突），"
            "再只改相关函数或相关拼接/编码段落；禁止只做无关润色。"
        )
    return (
        f"【修复模式=broader】同一错误已连续出现 {same_error_streak} 次，局部修补无效。"
        "允许重写出错函数整段（如 run 内增强/训练段，或 generate_* / compute_*），"
        "但仍须保持研究意图与返回 (metrics, chart_paths)；"
        "diagnosis 必须说明为何前几轮没修好、本轮改法。"
    )


def patch_plan_from_error(
    llm: LLMClient,
    plan: ExperimentPlan,
    *,
    research_goal: str,
    column_contract: dict,
    error_message: str,
    analysis_summary: str = "",
    repair_mode: RepairMode = "local",
    same_error_streak: int = 1,
) -> ExperimentPlan:
    """基于当前脚本与报错做一次局部修补（轻量 JSON，避免整份 ExperimentPlan 校验翻车）。"""
    params = dict(plan.parameters or {})
    script = get_plan_script(plan)
    current_params = dict(plan.script_params or {})
    if isinstance(params.get("script_params"), dict):
        current_params.update(params["script_params"])

    hint = _repair_hint_for_error(error_message, column_contract)
    mode_note = _repair_mode_instructions(repair_mode, same_error_streak)
    enriched_error = error_message
    extras = [mode_note]
    if hint:
        extras.append("【系统修补提示】\n" + hint)
    enriched_error = error_message + "\n\n" + "\n\n".join(extras)

    # 同错升级时提高探索度，避免反复输出近似补丁
    temperature = {"local": 0.2, "diagnose": 0.35, "broader": 0.55}[repair_mode]

    schema_props = {
        "diagnosis": {
            "type": "string",
            "description": "一句话根因（必填于 diagnose/broader 模式）",
        },
        "script": {
            "type": "string",
            "description": "完整可执行 Python，必须含 def run(df, params)",
        },
        "analysis_script": {
            "type": "string",
            "description": "与 script 相同的完整代码",
        },
        "script_params": {
            "type": "object",
            "description": "脚本参数，含 feature_columns/target_column/sample_size 等",
        },
    }
    required = ["script"]
    if repair_mode in ("diagnose", "broader"):
        required = ["diagnosis", "script"]

    prompt = SANDBOX_SCRIPT_PATCH_USER_TEMPLATE.render(
        research_goal=research_goal,
        numeric_columns=column_contract.get("numeric_columns", []),
        non_numeric_columns=column_contract.get("non_numeric_columns", []),
        suggested_target_columns=column_contract.get("suggested_target_columns", []),
        previous_script=script[:12000],
        current_script_params=current_params,
        error_message=enriched_error,
        previous_analysis_summary=analysis_summary or enriched_error,
        repair_mode=repair_mode,
        same_error_streak=same_error_streak,
    )
    try:
        raw = llm.generate_structured(
            prompt=prompt,
            system_prompt=(
                SANDBOX_SCRIPT_PATCH_SYSTEM_PROMPT
                + "\n只输出 JSON 数据实例，字段可含 diagnosis, script, analysis_script, script_params。"
                "不要输出完整 ExperimentPlan，不要输出 JSON Schema。"
                + f"\n{mode_note}"
            ),
            output_schema={
                "type": "object",
                "properties": schema_props,
                "required": required,
            },
            temperature=temperature,
        )
    except Exception as e:
        logger.warning("脚本修补 LLM 调用失败，保留原脚本: %s", e)
        return normalize_column_params(plan.model_copy(deep=True), column_contract)

    diagnosis = (raw.get("diagnosis") or "").strip()
    if diagnosis:
        logger.info("脚本修补诊断 (mode=%s): %s", repair_mode, diagnosis[:300])

    new_script = (raw.get("script") or raw.get("analysis_script") or "").strip()
    if len(new_script) < 80 or "see analysis_script" in new_script.lower():
        logger.warning("修补产出无效脚本，保留修补前正文")
        return normalize_column_params(plan.model_copy(deep=True), column_contract)

    patched = plan.model_copy(deep=True)
    pparams = dict(patched.parameters or {})
    if isinstance(params.get("data_config"), dict):
        pparams["data_config"] = dict(params["data_config"])
    pparams["script"] = new_script
    new_sp = dict(current_params)
    if isinstance(raw.get("script_params"), dict):
        new_sp.update(raw["script_params"])
    pparams["script_params"] = new_sp
    patched.parameters = pparams
    patched.script_params = new_sp
    patched.analysis_script = (raw.get("analysis_script") or new_script).strip() or new_script
    return normalize_column_params(patched, column_contract)


def _select_repair_mode(same_error_streak: int) -> RepairMode:
    if same_error_streak >= 3:
        return "broader"
    if same_error_streak >= 2:
        return "diagnose"
    return "local"


def repair_plan_until_smoke(
    llm: LLMClient,
    plan: ExperimentPlan,
    *,
    research_goal: str,
    data_config: Optional[dict],
    column_contract: dict,
    smoke_sample_size: int = 10000,
    max_attempts: int = 20,
    require_charts: bool = True,
    on_exhausted: Literal["raise", "rollback"] = "raise",
    rollback_plan: Optional[ExperimentPlan] = None,
) -> tuple[ExperimentPlan, Optional[object]]:
    """
    IDE 式循环：normalize → smoke → patch → smoke …

    Returns:
        (plan, smoke_result)  smoke_result 为最后一次成功的 IterationResult

    on_exhausted:
      - raise: 设计阶段用，失败则不落库
      - rollback: 迭代阶段用，失败则回退 rollback_plan
    """
    current = normalize_column_params(plan, column_contract)
    last_errors: list[str] = []
    last_result = None
    prev_fingerprint: Optional[str] = None
    same_error_streak = 0

    for attempt in range(1, max_attempts + 1):
        static_errors = validate_plan_static(current)
        if static_errors:
            ok, errors, last_result = False, static_errors, None
        else:
            ok, errors, last_result = smoke_run_plan(
                current,
                data_config=data_config,
                sample_size=smoke_sample_size,
                require_charts=require_charts,
                stratified=True,
            )
        if ok:
            logger.info("脚本修复循环通过 (attempt=%s/%s)", attempt, max_attempts)
            return current, last_result

        last_errors = errors
        err_joined = "; ".join(errors)
        fp = error_fingerprint(err_joined)
        if fp == prev_fingerprint:
            same_error_streak += 1
        else:
            same_error_streak = 1
            prev_fingerprint = fp
        repair_mode = _select_repair_mode(same_error_streak)

        logger.warning(
            "脚本试跑未通过 (attempt=%s/%s, streak=%s, mode=%s): %s",
            attempt,
            max_attempts,
            same_error_streak,
            repair_mode,
            err_joined[:500],
        )
        if attempt >= max_attempts:
            break

        current = patch_plan_from_error(
            llm,
            current,
            research_goal=research_goal,
            column_contract=column_contract,
            error_message=err_joined,
            analysis_summary=(
                f"第 {attempt} 次试跑失败（同错连续 {same_error_streak} 次，模式 {repair_mode}）。"
                "请依据 traceback 与出错代码附近修复。"
            ),
            repair_mode=repair_mode,
            same_error_streak=same_error_streak,
        )

    err_text = "; ".join(last_errors) if last_errors else "未知错误"
    if on_exhausted == "rollback" and rollback_plan is not None:
        logger.warning("修复耗尽，回退到上轮可运行脚本: %s", err_text[:300])
        rolled = normalize_column_params(rollback_plan.model_copy(deep=True), column_contract)
        ok, errors, smoke_result = smoke_run_plan(
            rolled,
            data_config=data_config,
            sample_size=smoke_sample_size,
            require_charts=require_charts,
            stratified=True,
        )
        if ok:
            return rolled, smoke_result
        raise ValueError(
            "修复循环失败且回退脚本也无法通过试跑: "
            + "; ".join(errors or last_errors)
        )

    raise ValueError(
        f"脚本在 {max_attempts} 次 generate→smoke→patch 后仍未通过试跑: {err_text}"
    )
