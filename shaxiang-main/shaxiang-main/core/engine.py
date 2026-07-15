import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from schemas.experiment import Experiment, ExperimentPlan, ExperimentStatus
from schemas.result import IterationResult
from schemas.analysis import AnalysisReport, IterationDecision
from core.planner import ExperimentPlanner
from core.executor import ExperimentExecutor
from core.analyzer import ResultAnalyzer
from core.reflector import IterationReflector
from storage.repository import Repository, IterationRecord

logger = logging.getLogger(__name__)


def prepare_sandbox_plan(
    plan: ExperimentPlan,
    data_config: Optional[dict] = None,
    fallback_plan: Optional[ExperimentPlan] = None,
) -> ExperimentPlan:
    """
    将 LLM 产出的方案规范成 SandboxExecutor 可执行的结构。

    常见问题:
    - 脚本写在 analysis_script，但执行器读 parameters.script
    - data_config 用了 type/path 而不是 source_type/source_path
    - 真实上传路径在 experiment.current_data_config，LLM 可能写错或省略
    - 后续迭代的 adapted plan 常丢掉脚本，需要从上一轮/初始方案继承
    """
    params = dict(plan.parameters or {})
    fallback_params = dict((fallback_plan.parameters if fallback_plan else None) or {})

    # 1. 注入/纠正 data_config（优先用实验真实配置）
    if data_config:
        params["data_config"] = _normalize_data_config(dict(data_config))
    else:
        dc = params.get("data_config") or fallback_params.get("data_config")
        if isinstance(dc, dict) and dc:
            params["data_config"] = _normalize_data_config(dict(dc))

    # 2. 同步脚本: analysis_script ↔ parameters.script，必要时继承上轮
    script = (
        (params.get("script") or "").strip()
        or (plan.analysis_script or "").strip()
        or (fallback_params.get("script") or "").strip()
        or ((fallback_plan.analysis_script if fallback_plan else None) or "").strip()
    )
    if script:
        params["script"] = script
        if not (plan.analysis_script or "").strip():
            plan.analysis_script = script

    # 3. 合并 script_params
    script_params: dict = {}
    if fallback_plan and fallback_plan.script_params:
        script_params.update(fallback_plan.script_params)
    if isinstance(fallback_params.get("script_params"), dict):
        script_params.update(fallback_params["script_params"])
    if plan.script_params:
        script_params.update(plan.script_params)
    if isinstance(params.get("script_params"), dict):
        script_params.update(params["script_params"])
    for key in (
        "target_column", "n_estimators", "max_depth", "test_size", "random_state",
        "group_column", "value_column", "threshold", "top_n", "learning_rate",
        "chart_dir", "iteration_label",
    ):
        if key in params and key not in script_params:
            script_params[key] = params[key]
        elif key in fallback_params and key not in script_params:
            script_params[key] = fallback_params[key]
    if script_params:
        params["script_params"] = script_params
        plan.script_params = script_params

    plan.parameters = params
    return plan


def _normalize_data_config(dc: dict) -> dict:
    """纠正字段别名，并对已知数据集回退到预置 Profile。"""
    if "source_type" not in dc and "type" in dc:
        dc["source_type"] = dc.pop("type")
    if "source_path" not in dc and "path" in dc:
        dc["source_path"] = dc.pop("path")

    # AutoDetect / 模糊 profile 时，路径像预置数据集则切到官方 Profile
    source_path = (dc.get("source_path") or "").lower()
    profile_name = dc.get("profile_name") or ""
    if dc.get("source_type") == "directory" and (
        not profile_name or profile_name == "AutoDetect" or dc.get("profile_json")
    ):
        if "uci har" in source_path or "ucihar" in source_path.replace(" ", ""):
            dc["profile_name"] = "UCI_HAR"
            dc.pop("profile_json", None)
        elif "sisfall" in source_path:
            dc["profile_name"] = "SisFall"
            dc.pop("profile_json", None)
        elif "mobiact" in source_path:
            dc["profile_name"] = "MobiAct"
            dc.pop("profile_json", None)
    return dc


@dataclass
class EngineConfig:
    max_iterations: int = 10
    early_stop_on_success: bool = True
    stagnation_window: int = 3
    max_consecutive_failures: int = 2
    # smoke_only 默认样本量（LLM 未指定 script_params.sample_size 时使用）
    smoke_sample_size: int = 10000
    smoke_sample_size_min: int = 2000
    smoke_sample_size_max: int = 80000
    metadata_sample_size: int = 5000
    max_script_repair_attempts: int = 20
    # 已弃用：sandbox 每轮均基于脚本+修改意见重设计，不再「成功只调参」
    lock_script_on_success: bool = False
    # True=smoke 后再正式全量推演；False=小样本验收即本轮完成（默认）
    # 关闭时：按 script_params.sample_size 动态决定抽取行数（夹在 min/max）
    full_dataset_run: bool = False

    @classmethod
    def from_env(cls) -> "EngineConfig":
        import os
        raw = (os.getenv("SHAXIANG_FULL_DATASET_RUN") or "0").strip().lower()
        full = raw in {"1", "true", "yes", "on"}
        return cls(full_dataset_run=full)


def _inject_smoke_sample_size(
    plan: ExperimentPlan,
    sample_size: int,
    column_contract: Optional[dict] = None,
) -> ExperimentPlan:
    """写入动态 sample_size，并尽量带上分层标签列供加载器用。"""
    plan = plan.model_copy(deep=True)
    params = dict(plan.parameters or {})
    sp = dict(plan.script_params or {})
    if isinstance(params.get("script_params"), dict):
        sp.update(params["script_params"])
    sp["sample_size"] = int(sample_size)
    # 推断分层标签
    target = sp.get("target_column")
    if not target:
        suggested = (column_contract or {}).get("suggested_target_columns") or []
        if suggested:
            target = suggested[0]
            sp["target_column"] = target
    params["script_params"] = sp
    dc = dict(params.get("data_config") or {})
    if target:
        dc["target_columns"] = [target]
        dc["sample_method"] = "stratified"
    params["data_config"] = dc
    plan.parameters = params
    plan.script_params = sp
    return plan


def resolve_run_mode(experiment: Experiment, config: EngineConfig) -> str:
    """
    解析本轮运行范围。
    - smoke_only: 仅小样本验收，图表写 data/charts/smoke；样本量可由 LLM 动态调整
    - full: smoke 通过后再正式执行（data/charts）
    """
    mode = (getattr(experiment, "run_mode", None) or "").strip().lower()
    if mode in {"smoke_only", "full"}:
        return mode
    return "full" if config.full_dataset_run else "smoke_only"


def resolve_smoke_sample_size(
    plan: Optional[ExperimentPlan],
    config: EngineConfig,
    column_contract: Optional[dict] = None,
) -> int:
    """
    smoke_only 下的动态样本量：
    优先 script_params.sample_size（由大模型按类不平衡/任务需要给出），
    否则用默认 smoke_sample_size，并夹在 [min, max]。
    """
    n = None
    if plan is not None:
        params = plan.parameters or {}
        sp = dict(plan.script_params or {})
        if isinstance(params.get("script_params"), dict):
            sp.update(params["script_params"])
        for cand in (sp.get("sample_size"), params.get("sample_size")):
            try:
                v = int(cand)
                if v > 0:
                    n = v
                    break
            except (TypeError, ValueError):
                continue

    if n is None:
        n = int(config.smoke_sample_size)

    # 极度不平衡时：若 metadata 行数很大而默认偏小，抬到至少 10000
    row_count = (column_contract or {}).get("row_count") or 0
    try:
        row_count = int(row_count)
    except (TypeError, ValueError):
        row_count = 0
    if row_count > 100000 and n < 10000:
        n = 10000

    n = max(int(config.smoke_sample_size_min), min(int(config.smoke_sample_size_max), int(n)))
    return n


class IterationEngine:
    """
    闭环迭代引擎 - 编排 Plan → Execute → Analyze → Reflect 循环
    """

    def __init__(
        self,
        planner: ExperimentPlanner,
        executor: ExperimentExecutor,
        analyzer: ResultAnalyzer,
        reflector: IterationReflector,
        repository: Repository,
        config: EngineConfig = None,
    ):
        self.planner = planner
        self.executor = executor
        self.analyzer = analyzer
        self.reflector = reflector
        self.repository = repository
        self.config = config or EngineConfig()

    def start_experiment(self, experiment: Experiment) -> Experiment:
        """启动实验，生成初始方案"""
        # 生成初始方案
        plan = self.planner.generate_initial_plan(
            research_goal=experiment.research_goal,
            constraints=experiment.constraints,
        )
        experiment.initial_plan = plan
        experiment.status = ExperimentStatus.RUNNING
        self.repository.save_experiment(experiment)
        logger.info(f"实验启动: {experiment.title} (ID: {experiment.id})")
        return experiment

    def run_single_iteration(self, experiment: Experiment) -> IterationRecord:
        """执行一轮完整迭代: Plan → Execute → Analyze → Reflect"""
        iteration_num = experiment.current_iteration + 1
        logger.info(f"开始第 {iteration_num} 轮迭代...")

        start = time.time()
        experiment.status = ExperimentStatus.RUNNING
        experiment.phase = "running"
        self.repository.update_experiment(experiment)

        # === 1. PLAN ===
        fallback_plan = experiment.initial_plan
        last_success_plan = self._find_last_successful_plan(experiment.id) or experiment.initial_plan
        data_config = (
            getattr(experiment, "current_data_config", None)
            or getattr(experiment, "data_config", None)
        )
        column_contract = {}
        if experiment.executor_type == "sandbox" and data_config:
            try:
                from core.script_validator import load_metadata_with_contract
                column_contract = load_metadata_with_contract(
                    data_config, sample_size=self.config.metadata_sample_size
                )
            except Exception as e:
                logger.warning(f"列契约加载失败，继续迭代: {e}")

        if iteration_num == 1:
            plan = experiment.initial_plan
            if plan is None:
                raise ValueError("尚未设计分析方案，请先完成「确认并设计分析脚本」")
        else:
            latest = self.repository.get_latest_iteration(experiment.id)
            prev_analysis = AnalysisReport.model_validate(latest.analysis) if latest and latest.analysis else None
            prev_decision = IterationDecision.model_validate(latest.decision) if latest and latest.decision else None
            prev_status = latest.status if latest else "failed"
            prev_error = latest.error_message if latest else ""

            if latest and latest.plan:
                try:
                    fallback_plan = ExperimentPlan.model_validate(latest.plan)
                except Exception:
                    fallback_plan = experiment.initial_plan

            # 优先继承上轮成功脚本正文，再按修改意见迭代；失败轮也尽量从最近可运行脚本出发
            base_plan = last_success_plan or fallback_plan or experiment.initial_plan
            prev_script = ""
            if base_plan:
                prev_script = (
                    (base_plan.parameters or {}).get("script")
                    or base_plan.analysis_script
                    or ""
                )
            if not prev_script and fallback_plan:
                prev_script = (
                    (fallback_plan.parameters or {}).get("script")
                    or fallback_plan.analysis_script
                    or ""
                )

            if experiment.executor_type == "sandbox":
                # 每轮：脚本 + 分析/反射修改意见 + 列契约 + 人工反馈 → 高自由度重设计
                from core.script_designer import ScriptDesigner

                designer = ScriptDesigner(self.planner.llm, self.repository)
                guidance_parts = []
                if prev_analysis:
                    guidance_parts.append(
                        "【上轮分析】\n"
                        f"评估: {prev_analysis.overall_assessment}\n"
                        f"摘要: {prev_analysis.summary}\n"
                        f"问题: {'; '.join(prev_analysis.identified_issues or [])}\n"
                        f"建议: {'; '.join(prev_analysis.suggested_adjustments or [])}"
                    )
                if prev_decision:
                    guidance_parts.append(
                        "【方案调整方向】\n"
                        f"是否继续: {prev_decision.should_continue}\n"
                        f"预期改进: {prev_decision.expected_improvement}\n"
                        f"调整项: {'; '.join(prev_decision.next_plan_adjustments or [])}\n"
                        f"审查问题: {'; '.join(prev_decision.review_questions or [])}"
                    )
                if prev_status != "success" and prev_error:
                    guidance_parts.append(f"【上轮执行错误】\n{prev_error}")
                guidance_parts.append(
                    "【硬性迭代要求】\n"
                    "- 必须在上轮脚本基础上完善，而不是只改 script_params\n"
                    "- 传感器数据禁止行级随机划分；优先按 sensor/受试者分组（不要用 class/label 当 group）\n"
                    "- GroupKFold 必须写 n_splits=min(5, n_unique_groups)，组数不足时降折或改 GroupShuffleSplit\n"
                    "- feature 只用传感器数值列，排除 activity_type/subject 等标识列\n"
                    "- 保留/补充：类别分布、基线模型对比、可靠交叉验证；指标虚高(≈1.0)必须排查泄漏"
                )
                analysis_summary = "\n\n".join(guidance_parts)
                human_fb = (experiment.human_feedback or "").strip() or None

                plan = designer.design_script(
                    hypothesis=experiment.hypothesis or experiment.research_goal,
                    data_config=data_config or {},
                    dataset_metadata=column_contract,
                    previous_plan=base_plan,
                    previous_analysis_summary=analysis_summary,
                    constraints=experiment.constraints,
                    human_feedback=human_fb,
                    current_script=prev_script,
                    allow_full_rewrite=True,
                )
                logger.info(
                    "sandbox 第 %s 轮：基于脚本+修改意见重设计（prev_status=%s）",
                    iteration_num,
                    prev_status,
                )
            elif prev_analysis and prev_decision:
                plan = self.planner.generate_adapted_plan(
                    experiment,
                    prev_analysis,
                    prev_decision,
                    previous_status=prev_status or "failed",
                    error_message=prev_error or "",
                    column_contract=column_contract,
                    previous_script=prev_script,
                    locked_plan=last_success_plan,
                    force_script_rewrite=True,
                )
            else:
                plan = self.planner.generate_initial_plan(experiment.research_goal, experiment.constraints)

        # 沙箱：IDE 式 smoke 修补；按 run_mode 决定是否再全量推演
        run_mode = resolve_run_mode(experiment, self.config)
        smoke_result = None
        if experiment.executor_type == "sandbox":
            from core.script_validator import validate_plan_static
            from core.script_repair import normalize_column_params, repair_plan_until_smoke

            plan = prepare_sandbox_plan(plan, data_config, fallback_plan=fallback_plan or last_success_plan)
            if column_contract:
                plan = normalize_column_params(plan, column_contract)

            sandbox = self.executor.registry.get("sandbox")
            if sandbox:
                prep_errors = sandbox.validate_plan(plan) + validate_plan_static(plan)
                if prep_errors:
                    logger.warning("方案静态校验告警，进入 IDE 修复循环: %s", prep_errors)

            smoke_n = resolve_smoke_sample_size(plan, self.config, column_contract)
            # 把动态样本量写回 plan，供 LLM 下一轮参考，并让分层采样生效
            plan = _inject_smoke_sample_size(plan, smoke_n, column_contract)

            plan, smoke_result = repair_plan_until_smoke(
                self.planner.llm,
                plan,
                research_goal=experiment.hypothesis or experiment.research_goal,
                data_config=data_config,
                column_contract=column_contract or {},
                smoke_sample_size=smoke_n,
                max_attempts=self.config.max_script_repair_attempts,
                require_charts=True,
                on_exhausted="raise",
                rollback_plan=None,
            )
            plan = prepare_sandbox_plan(plan, data_config, fallback_plan=last_success_plan)
            smoke_n = resolve_smoke_sample_size(plan, self.config, column_contract)
            plan = _inject_smoke_sample_size(plan, smoke_n, column_contract)

            experiment.initial_plan = plan
            if (experiment.human_feedback or "").strip() and getattr(experiment, "feedback_status", "") == "submitted":
                experiment.feedback_status = "applied"
            self.repository.update_experiment(experiment)

        # === 2. EXECUTE ===
        if experiment.executor_type == "sandbox" and run_mode == "smoke_only":
            # 小样本验收即为本轮完成；样本量由 LLM/脚本参数动态决定（非固定 2000）
            smoke_n = resolve_smoke_sample_size(plan, self.config, column_contract)
            if smoke_result is None:
                from core.script_validator import smoke_run_plan
                ok, errors, smoke_result = smoke_run_plan(
                    plan,
                    data_config=data_config,
                    sample_size=smoke_n,
                    require_charts=True,
                    stratified=True,
                )
                if not ok or smoke_result is None:
                    raise ValueError("smoke_only 模式复验失败: " + "; ".join(errors or ["无结果"]))
            result = smoke_result
            result.iteration_number = iteration_num
            prefix = f"[smoke_only sample_size={smoke_n}] "
            if not (result.summary or "").startswith("[smoke"):
                result.summary = prefix + (result.summary or "")
            logger.info(
                "run_mode=smoke_only：跳过全量，使用动态小样 n=%s 完成本轮",
                smoke_n,
            )
        else:
            result = self.executor.execute(plan, experiment.executor_type)
            result.iteration_number = iteration_num
            if experiment.executor_type == "sandbox" and run_mode == "full":
                if not (result.summary or "").startswith("[full"):
                    result.summary = "[full] " + (result.summary or "")

        # === 3. ANALYZE ===
        if result.status == "success":
            analysis = self.analyzer.analyze(result, plan, experiment.id)
        else:
            analysis = AnalysisReport(
                iteration_number=iteration_num,
                overall_assessment="significant_issue",
                summary=f"实验执行失败: {result.error_message}",
                identified_issues=[result.error_message],
            )

        # === 4. REFLECT ===
        consecutive_failures = self._count_consecutive_failures(experiment.id, result.status)
        if result.status == "success":
            decision = self.reflector.reflect(
                analysis=analysis,
                experiment_id=experiment.id,
                max_iterations=experiment.max_iterations,
                completed_iterations=iteration_num,
            )
        else:
            should_ask_human = consecutive_failures >= self.config.max_consecutive_failures
            decision = IterationDecision(
                should_continue=not should_ask_human,
                needs_human_review=should_ask_human,
                next_plan_adjustments=["修复执行错误后重试"],
                expected_improvement="修复后重新评估",
                review_questions=["请检查标签列/特征列与脚本，确认后再继续迭代"] if should_ask_human else [],
            )
            if should_ask_human:
                experiment.feedback_status = "pending"

        # === 保存记录 ===
        duration = time.time() - start

        # 提取数值指标
        metrics = {}
        if result.data_points:
            for dp in result.data_points:
                if isinstance(dp.value, (int, float)):
                    metrics[dp.key] = dp.value
        # 标注运行范围，避免与全量结果混淆
        if experiment.executor_type == "sandbox":
            metrics["run_scope"] = "smoke" if run_mode == "smoke_only" else "full"

        record = IterationRecord(
            iteration_number=iteration_num,
            plan=plan.model_dump(),
            result=result.model_dump(),
            analysis=analysis.model_dump(),
            decision=decision.model_dump(),
            metrics=metrics,
            status=result.status,
            error_message=result.error_message,
            duration_seconds=duration,
        )
        self.repository.save_iteration(experiment.id, record)

        # 更新实验状态
        experiment.current_iteration = iteration_num
        should_stop, reason = self.should_terminate(experiment, analysis, decision)
        if should_stop:
            if decision.needs_human_review or getattr(experiment, "feedback_status", None) == "pending":
                experiment.status = ExperimentStatus.PAUSED
                experiment.phase = "needs_human_review"
                logger.info(f"实验暂停待人工确认: {reason}")
            else:
                experiment.status = ExperimentStatus.COMPLETED
                experiment.phase = "completed"
                logger.info(f"实验完成: {reason}")
        else:
            experiment.phase = "running"
        self.repository.update_experiment(experiment)

        return record

    def run_to_completion(
        self,
        experiment: Experiment,
        callback: Callable = None,
    ) -> Experiment:
        """持续运行迭代直到满足终止条件"""
        # sandbox 已有设计脚本时，禁止 start_experiment 覆盖 initial_plan
        if experiment.executor_type == "sandbox" and experiment.initial_plan is not None:
            experiment.status = ExperimentStatus.RUNNING
            experiment.phase = "running"
            self.repository.update_experiment(experiment)
        else:
            experiment = self.start_experiment(experiment)

        while experiment.status == ExperimentStatus.RUNNING:
            try:
                record = self.run_single_iteration(experiment)
            except Exception as e:
                logger.error(f"自动运行中断: {e}")
                experiment = self.repository.get_experiment(experiment.id) or experiment
                experiment.status = ExperimentStatus.FAILED
                experiment.phase = "failed"
                experiment.feedback_status = "pending"
                self.repository.update_experiment(experiment)
                raise
            if callback:
                callback(record)
            experiment = self.repository.get_experiment(experiment.id)
            if experiment is None:
                break

        return experiment

    def run_data_iteration(
        self,
        experiment: Experiment,
        phase: str = "recommend",
    ):
        """
        假设驱动迭代 — 按阶段执行

        阶段:
        - recommend: LLM 推荐数据集
        - design: 根据上传数据设计脚本
        - execute: 执行完整 Plan → Execute → Analyze → Reflect

        Returns:
            根据 phase 返回不同结果
        """
        experiment.phase = phase
        self.repository.update_experiment(experiment)

        if phase == "recommend":
            from core.dataset_advisor import DatasetAdvisor
            advisor = DatasetAdvisor(self.planner.llm, self.repository)
            report = advisor.recommend_datasets(
                hypothesis=experiment.hypothesis or experiment.research_goal,
                constraints=experiment.constraints,
                human_feedback=experiment.human_feedback,
            )
            experiment.dataset_recommendations = [d.model_dump() for d in report.recommended_datasets]
            experiment.phase = "data_recommended"
            self.repository.update_experiment(experiment)
            return report

        elif phase == "design":
            from core.script_designer import ScriptDesigner
            from core.script_validator import load_metadata_with_contract
            from core.script_repair import repair_plan_until_smoke

            designer = ScriptDesigner(self.planner.llm, self.repository)

            data_config = experiment.current_data_config or {}
            try:
                metadata = load_metadata_with_contract(
                    data_config, sample_size=self.config.metadata_sample_size
                )
            except Exception as e:
                raise ValueError(f"数据加载失败，无法设计脚本: {e}") from e

            latest = self.repository.get_latest_iteration(experiment.id)
            prev_plan = None
            prev_analysis_summary = None
            if latest and latest.plan:
                try:
                    prev_plan = ExperimentPlan.model_validate(latest.plan)
                except Exception:
                    pass
            if latest and latest.analysis:
                try:
                    prev_analysis = AnalysisReport.model_validate(latest.analysis)
                    prev_analysis_summary = (
                        f"评估: {prev_analysis.overall_assessment}\n"
                        f"摘要: {prev_analysis.summary}\n"
                        f"问题: {'; '.join(prev_analysis.identified_issues)}"
                    )
                except Exception:
                    pass

            feedback = (experiment.human_feedback or "").strip()
            current_script = ""
            if prev_plan is not None:
                current_script = (
                    (prev_plan.parameters or {}).get("script")
                    or prev_plan.analysis_script
                    or ""
                )
            if not current_script and experiment.initial_plan is not None:
                current_script = (
                    (experiment.initial_plan.parameters or {}).get("script")
                    or experiment.initial_plan.analysis_script
                    or ""
                )

            # 一次 LLM 设计 + 多轮 smoke→patch（IDE 式），通过才落库
            # 有人工反馈时：高自由度重写，不锁在旧成功脚本上
            plan = designer.design_script(
                hypothesis=experiment.hypothesis or experiment.research_goal,
                data_config=data_config,
                dataset_metadata=metadata,
                previous_plan=prev_plan or experiment.initial_plan,
                previous_analysis_summary=prev_analysis_summary,
                constraints=experiment.constraints,
                human_feedback=feedback or None,
                current_script=current_script or None,
                allow_full_rewrite=bool(feedback),
            )
            plan = prepare_sandbox_plan(plan, data_config)
            smoke_n = resolve_smoke_sample_size(plan, self.config, metadata)
            plan = _inject_smoke_sample_size(plan, smoke_n, metadata)
            plan, _smoke_result = repair_plan_until_smoke(
                self.planner.llm,
                plan,
                research_goal=experiment.hypothesis or experiment.research_goal,
                data_config=data_config,
                column_contract=metadata,
                smoke_sample_size=smoke_n,
                max_attempts=self.config.max_script_repair_attempts,
                require_charts=True,
                on_exhausted="raise",
            )
            smoke_n = resolve_smoke_sample_size(plan, self.config, metadata)
            plan = _inject_smoke_sample_size(plan, smoke_n, metadata)
            plan = prepare_sandbox_plan(plan, data_config)

            experiment.initial_plan = plan
            experiment.data_config = data_config
            experiment.phase = "script_designed"
            experiment.status = ExperimentStatus.CREATED
            if feedback:
                experiment.feedback_status = "applied"
            self.repository.update_experiment(experiment)
            return plan

        elif phase == "execute":
            return self.run_single_iteration(experiment)

    def should_terminate(
        self,
        experiment: Experiment,
        analysis: AnalysisReport,
        decision: IterationDecision,
    ) -> tuple[bool, str]:
        """判断是否应终止迭代"""
        # 条件1: 达到最大迭代轮数
        if experiment.current_iteration >= experiment.max_iterations:
            return True, f"已达到最大迭代轮数 {experiment.max_iterations}"

        # 条件2: 连续失败 / 需人工确认（须先于「should_continue=False = 成功」判断）
        if decision.needs_human_review or (
            hasattr(experiment, "feedback_status") and experiment.feedback_status == "pending"
        ):
            return True, (
                f"连续失败达到 {self.config.max_consecutive_failures} 次，停止并等待人工确认"
                if decision.needs_human_review
                else "等待人工反馈后继续迭代"
            )

        # 条件3: LLM 判断已成功
        if not decision.should_continue and self.config.early_stop_on_success:
            return True, "LLM 评估实验目标已达成，停止迭代"

        # 条件4: 分析报告标记为成功
        if analysis.overall_assessment == "success" and self.config.early_stop_on_success:
            return True, "分析报告确认实验目标已达成"

        # 条件5: 连续多轮无显著改进（停滞检测）
        if self._check_stagnation(experiment):
            return True, f"连续 {self.config.stagnation_window} 轮无显著改进，检测到收敛停滞"

        return False, ""

    def _find_last_successful_plan(self, experiment_id: str) -> Optional[ExperimentPlan]:
        iterations = self.repository.get_iterations(experiment_id)
        for it in reversed(iterations):
            if it.status == "success" and it.plan:
                try:
                    return ExperimentPlan.model_validate(it.plan)
                except Exception:
                    continue
        return None

    def _count_consecutive_failures(self, experiment_id: str, current_status: str) -> int:
        """含本轮结果的连续失败计数。"""
        count = 1 if current_status != "success" else 0
        if current_status == "success":
            return 0
        iterations = self.repository.get_iterations(experiment_id)
        for it in reversed(iterations):
            if it.status == "success":
                break
            count += 1
        return count

    def _check_stagnation(self, experiment: Experiment) -> bool:
        """检测是否连续多轮停滞"""
        history = self.repository.get_metrics_history(experiment.id)
        if len(history) < self.config.stagnation_window:
            return False

        # 取最近 N 轮的 overall_score
        recent = history[-self.config.stagnation_window:]
        scores = [h.get("overall_score") for h in recent if "overall_score" in h]
        if len(scores) < self.config.stagnation_window:
            return False

        # 判断变化幅度是否都小于阈值
        threshold = 0.02
        for i in range(1, len(scores)):
            if abs(scores[i] - scores[i - 1]) > threshold:
                return False
        return True
