"""
IDE 式脚本修复循环：生成/修补 → smoke_run → 把报错喂回 LLM → 再修。

自适应要点：
- 用语义错误指纹识别「同错反复」（不依赖漂移的行号）
- 根据研究目标 / 反馈 / 脚本推断实验范式（general | federated），分治给修复原则
- 只给诊断性软引导，不注入固定修复代码模板
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
ExperimentParadigm = Literal["general", "federated"]

# 联邦范式信号（启发式加权，非硬编码业务规则）
_FL_SIGNAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bfedavg\b|\bfedprox\b|\bfederated\b|\bfl\b", re.I), 2.0),
    (re.compile(r"联邦|客户端划分|通信轮次|参与率", re.I), 2.0),
    (re.compile(r"non[-\s]?iid|dirichlet|pathological", re.I), 1.5),
    (re.compile(r"num_clients|participation_rate|local_epochs|client_drift", re.I), 1.2),
    (re.compile(r"\[FL\s*实验范式|FL\s*Starter\s*Pack|hfl_|vfl_", re.I), 2.5),
    (re.compile(r"centralized.*local_only|local_only.*fedavg", re.I), 1.0),
]


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


def infer_experiment_paradigm(
    *,
    research_goal: str = "",
    human_feedback: str = "",
    script: str = "",
    explicit: Optional[str] = None,
) -> ExperimentParadigm:
    """
    自适应推断实验范式：federated | general。

    优先尊重显式标记；否则对目标/反馈/脚本做加权启发式，避免把通用任务
    误判成联邦，也避免联邦任务被当成普通 CV。
    """
    if explicit:
        e = str(explicit).strip().lower()
        if e in {"federated", "fl", "hfl", "vfl", "fed"}:
            return "federated"
        if e in {"general", "tabular", "standard", "cv"}:
            return "general"

    blob = "\n".join(
        [
            research_goal or "",
            human_feedback or "",
            (script or "")[:8000],
        ]
    )
    score = 0.0
    for pat, weight in _FL_SIGNAL_PATTERNS:
        if pat.search(blob):
            score += weight

    # 脚本结构信号：多客户端循环 / 聚合权重
    if re.search(r"num_clients|client_data|client_ids|participation", blob, re.I):
        score += 1.0
    if re.search(r"aggregate|avg_coef|FedProx|prox_mu", blob, re.I):
        score += 0.8

    paradigm: ExperimentParadigm = "federated" if score >= 2.0 else "general"
    logger.info("推断实验范式 paradigm=%s score=%.1f", paradigm, score)
    return paradigm


def _extract_exception_body(error_message: str) -> tuple[str, str]:
    """返回 (exc_type_or_empty, normalized_body)。"""
    text = error_message or ""
    first = text.strip().splitlines()[0] if text.strip() else ""
    # enriched 首行常为 "smoke_run 失败: ValueError: ..."
    first = re.sub(r"^smoke_run\s*失败[:：]\s*", "", first, flags=re.I)
    exc_m = re.search(
        r"(ValueError|KeyError|TypeError|IndexError|AttributeError|NameError|"
        r"RuntimeError|ImportError|ModuleNotFoundError|AssertionError|"
        r"LinAlgError|MemoryError)[:\s]+(.+)",
        first,
        flags=re.I,
    )
    if exc_m:
        exc_type = exc_m.group(1)
        body = exc_m.group(2)
    else:
        # 全文再搜一次异常行
        full_m = re.search(
            r"(ValueError|KeyError|TypeError|IndexError|AttributeError|NameError|"
            r"RuntimeError|ImportError|ModuleNotFoundError|AssertionError|"
            r"LinAlgError|MemoryError)[:\s]+(.+)",
            text,
            flags=re.I,
        )
        if full_m:
            exc_type = full_m.group(1)
            body = full_m.group(2).splitlines()[0]
        else:
            exc_type = ""
            body = first[:240]
    body = re.sub(r"\d+", "N", body)
    body = re.sub(r"\s+", " ", body).strip().lower()
    return exc_type, body


def error_fingerprint(error_message: str) -> str:
    """
    语义错误指纹：以异常类型+归一化消息为主，不把行号计入指纹。

    行号会随 LLM 局部插入/删除漂移，计入指纹会导致同错 streak 永远为 1，
    修复模式无法从 local 升级到 diagnose/broader。
    """
    exc_type, body = _extract_exception_body(error_message)
    if exc_type:
        return f"{exc_type.lower()}:{body}"
    return body or "unknown"


def _paradigm_principles(paradigm: ExperimentParadigm) -> str:
    """模式分治原则（软约束，不给固定代码）。"""
    if paradigm == "federated":
        return (
            "【实验范式=federated】按联邦学习问题修复与设计：\n"
            "- 保留客户端划分 / 本地更新 / 聚合 / 通信轮次等联邦结构，"
            "不要退化成「忽略划分的全局单模型 CV」来绕过报错。\n"
            "- Non-IID 下部分客户端标签单一是常见现象：先区分"
            "「全局标签是否退化」与「仅局部 client 单类」，再自适应处理该路径。\n"
            "- 本地训练 API 须与标签支撑集兼容；检查是否所有 .fit / partial_fit "
            "路径都做了合法样本与类别支撑检查，而不是只改一处循环。\n"
            "- 不要把通用解（盲目增大 sample_size、SMOTE、去掉联邦结构）当默认手段。"
        )
    return (
        "【实验范式=general】按通用表格/统计学习问题修复与设计：\n"
        "- 关注标签编码、分层采样、全局类别覆盖、特征数值化与泄漏控制。\n"
        "- 禁止为了“躲过报错”临时引入 FedAvg / 客户端划分 / Dirichlet 等联邦结构"
        "（除非研究目标本身就是联邦学习）。\n"
        "- 类稀缺时优先诊断标签与采样，再调整模型与过采样策略。"
    )


def _repair_hint_for_error(
    error_message: str,
    column_contract: dict,
    *,
    paradigm: ExperimentParadigm = "general",
) -> str:
    """针对常见失败给出检查点提示（软引导，不注入固定修复代码）。"""
    err = (error_message or "").lower()
    hints: list[str] = []
    non_num = list(column_contract.get("non_numeric_columns") or [])

    if "n_splits" in err or "number of groups" in err or ("groups" in err and "split" in err):
        group_candidates = [
            c for c in non_num
            if str(c).lower() in {"sensor", "subject", "subject_id", "run", "filename"}
            or "sensor" in str(c).lower()
            or "subject" in str(c).lower()
        ]
        if paradigm == "federated":
            hints.append(
                "分组折数不足：联邦场景请优先用 client_id / 参与方划分做评估协议，"
                f"不要把 label 当 groups；候选列 {group_candidates or non_num[:3]}。"
            )
        else:
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

    # 单类 / 类别不足：按范式分治，避免通用与联邦互相污染
    class_fail = (
        "number of classes" in err
        or "got 1 class" in err
        or "only one class" in err
        or "only 1 class" in err
        or re.search(r"\bclasses?\b.+\b(greater|at least|require)", err) is not None
    )
    if class_fail:
        if paradigm == "federated":
            hints.append(
                "类别支撑不足（联邦）：请自诊断根因是全局标签退化，还是 Non-IID 导致"
                "部分 client/batch 单类。针对所有本地训练与初始化路径做自适应处理；"
                "保持联邦评估协议，勿改写成全局单模型。"
            )
        else:
            hints.append(
                "类别支撑不足（通用）：检查标签编码、分层采样与全局类别覆盖；"
                "少数类过少时可增大 sample_size 或改用 class_weight；"
                "SMOTE 前确认少数类样本数 ≥ k_neighbors+1。"
                "不要引入联邦客户端结构来绕过。"
            )
    elif "f1" in err or "imbalance" in err:
        if paradigm == "general":
            hints.append(
                "类不平衡相关指标异常：核对标签编码与采样；极端不平衡时优先 class_weight / "
                "调整 sample_size，再考虑过采样。"
            )
        else:
            hints.append(
                "指标异常：结合 client 级分布与全局分布分别诊断，避免只用全局均值掩盖 Non-IID。"
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
            "但须扫描同类调用点，避免只修一处、同错换行号再爆。"
        )
    if mode == "diagnose":
        return (
            f"【修复模式=diagnose】同一语义错误已连续出现 {same_error_streak} 次。"
            "必须先在 diagnosis 写清根因（变量/路径/范式约束冲突），"
            "再系统修复所有相关调用点；禁止无关润色。"
        )
    return (
        f"【修复模式=broader】同一语义错误已连续出现 {same_error_streak} 次，局部修补无效。"
        "允许在当前实验范式内重写出错子系统（如本地训练函数、划分逻辑、评估段），"
        "但仍须保持研究意图、范式边界与返回 (metrics, chart_paths)；"
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
    human_feedback: str = "",
    experiment_paradigm: Optional[ExperimentParadigm] = None,
) -> ExperimentPlan:
    """基于当前脚本与报错做一次局部修补（轻量 JSON，避免整份 ExperimentPlan 校验翻车）。"""
    params = dict(plan.parameters or {})
    script = get_plan_script(plan)
    current_params = dict(plan.script_params or {})
    if isinstance(params.get("script_params"), dict):
        current_params.update(params["script_params"])

    paradigm = experiment_paradigm or infer_experiment_paradigm(
        research_goal=research_goal,
        human_feedback=human_feedback,
        script=script,
    )
    hint = _repair_hint_for_error(error_message, column_contract, paradigm=paradigm)
    mode_note = _repair_mode_instructions(repair_mode, same_error_streak)
    paradigm_note = _paradigm_principles(paradigm)
    extras = [mode_note, paradigm_note]
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
        experiment_paradigm=paradigm,
        human_feedback=(human_feedback or "")[:4000] or None,
    )
    try:
        raw = llm.generate_structured(
            prompt=prompt,
            system_prompt=(
                SANDBOX_SCRIPT_PATCH_SYSTEM_PROMPT
                + "\n只输出 JSON 数据实例，字段可含 diagnosis, script, analysis_script, script_params。"
                "不要输出完整 ExperimentPlan，不要输出 JSON Schema。"
                + f"\n{mode_note}\n{paradigm_note}"
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
        logger.info(
            "脚本修补诊断 (mode=%s, paradigm=%s): %s",
            repair_mode,
            paradigm,
            diagnosis[:300],
        )

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
    # 记录推断范式，供后续轮次稳定复用（非业务硬编码）
    new_sp.setdefault("_experiment_paradigm", paradigm)
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
    max_attempts: int = 10,
    require_charts: bool = True,
    require_numeric_metrics: bool = True,
    on_exhausted: Literal["raise", "rollback"] = "raise",
    rollback_plan: Optional[ExperimentPlan] = None,
    human_feedback: str = "",
    experiment_paradigm: Optional[ExperimentParadigm] = None,
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

    script0 = get_plan_script(current)
    sp0 = dict(current.script_params or {})
    explicit = sp0.get("_experiment_paradigm") or sp0.get("experiment_paradigm")
    paradigm = experiment_paradigm or infer_experiment_paradigm(
        research_goal=research_goal,
        human_feedback=human_feedback,
        script=script0,
        explicit=str(explicit) if explicit else None,
    )

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
                require_numeric_metrics=require_numeric_metrics,
                stratified=True,
            )
        if ok:
            logger.info(
                "脚本修复循环通过 (attempt=%s/%s, paradigm=%s)",
                attempt,
                max_attempts,
                paradigm,
            )
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

        # 每轮用最新脚本再确认范式；仅 script_params 显式标记可锁定，避免把推断结果误当显式
        _sp = current.script_params or {}
        _explicit = _sp.get("_experiment_paradigm") or _sp.get("experiment_paradigm")
        paradigm = infer_experiment_paradigm(
            research_goal=research_goal,
            human_feedback=human_feedback,
            script=get_plan_script(current),
            explicit=str(_explicit) if _explicit else None,
        )

        logger.warning(
            "脚本试跑未通过 (attempt=%s/%s, streak=%s, mode=%s, paradigm=%s, fp=%s): %s",
            attempt,
            max_attempts,
            same_error_streak,
            repair_mode,
            paradigm,
            fp[:120],
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
                f"第 {attempt} 次试跑失败（同错连续 {same_error_streak} 次，"
                f"修复模式 {repair_mode}，实验范式 {paradigm}）。"
                "请依据 traceback 与出错代码附近，在当前范式边界内修复。"
            ),
            repair_mode=repair_mode,
            same_error_streak=same_error_streak,
            human_feedback=human_feedback,
            experiment_paradigm=paradigm,
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
            require_numeric_metrics=require_numeric_metrics,
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
