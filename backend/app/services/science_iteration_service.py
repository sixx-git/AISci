"""科学自迭代 — 溯源、编排、会话聚合"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.iterative_science import (
    assess_evidence_sufficiency,
    evaluate_verifiable_spec_against_validation,
)
from app.schemas.science_iteration import (
    DataGroundingItem,
    HypothesisGroundingBlock,
    HypothesisOriginBlock,
    HypothesisProvenanceResponse,
    HypothesisVerificationBlock,
    IterationRoundRecord,
    IterationRoundScores,
    LiteratureGroundingItem,
    MaterialSupplementAction,
    MaterialSupplementPlan,
    ScienceIterationConfig,
    ScienceIterationSessionResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = ScienceIterationConfig(
    enabled=True,
    max_rounds=5,
    auto_triggers=[],
    auto_literature_on_weak_evidence=False,
)


def resolve_science_iteration_config(
    project_config: Optional[Dict[str, Any]] = None,
    run_options: Optional[Dict[str, Any]] = None,
) -> ScienceIterationConfig:
    cfg = dict((project_config or {}).get("science_iteration") or {})
    opts = run_options or {}
    if "science_iteration_enabled" in opts:
        cfg["enabled"] = bool(opts["science_iteration_enabled"])
    if opts.get("science_iteration_max_rounds") is not None:
        cfg["max_rounds"] = int(opts["science_iteration_max_rounds"])
    try:
        return ScienceIterationConfig(**{**DEFAULT_CONFIG.model_dump(), **cfg})
    except Exception:
        return DEFAULT_CONFIG


def _fact_lookup(facts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for f in facts:
        fid = f.get("fact_id")
        if fid:
            out[str(fid)] = f
    return out


def _parse_list_field(val: Any) -> List[str]:
    """将数据库中可能存储为 JSON 字符串的字段安全解析为 list。

    支持三种输入：None / list / JSON 字符串。确保返回 List[str]。
    """
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if x]
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def build_reasoning_chain(
    pu: Dict[str, Any],
    kg: Dict[str, Any],
) -> List[str]:
    chain: List[str] = []
    if pu.get("main_contradiction"):
        chain.append(f"主要矛盾: {pu['main_contradiction']}")
    gaps = kg.get("knowledge_gaps") or []
    for g in gaps[:3]:
        desc = g.get("description", g) if isinstance(g, dict) else str(g)
        if desc:
            chain.append(f"知识缺口: {desc}")
    if pu.get("expected_output"):
        exp = pu["expected_output"]
        if isinstance(exp, list):
            chain.append(f"研究目的: {'; '.join(str(x) for x in exp[:3])}")
    return chain


def build_hypothesis_provenance(
    db: Session,
    hypothesis_id: str,
    *,
    pipeline_results: Optional[Dict[str, Any]] = None,
) -> HypothesisProvenanceResponse:
    """聚合假设来源、依据与验证规格。"""
    from app.services.evidence_reasoning_service import get_evidence_reasoning_service
    from app.services.hypothesis_service import HypothesisService

    hypo_service = HypothesisService(db)
    hypo = hypo_service.get_hypothesis_by_id(hypothesis_id)
    if not hypo:
        raise ValueError("假设不存在")

    results = pipeline_results or {}
    pu = results.get("problem_understanding") or {}
    kg = results.get("knowledge_gap") or {}
    lm = results.get("literature_mining") or {}
    da = results.get("data_acquisition") or results.get("data_finder") or {}
    df_results = da.get("extract") if isinstance(da.get("extract"), dict) else da
    if not df_results and hypo.project_id:
        try:
            from app.services.data_finder_service import get_data_finder_service

            df_results = get_data_finder_service(db).load_results(hypo.project_id) or {}
        except Exception:
            df_results = {}

    hg = results.get("hypothesis_generation") or {}
    hr = results.get("hypothesis_review") or {}
    from app.services.iterative_experiment_service import resolve_ed_sv_from_results

    _, ed, sv = resolve_ed_sv_from_results(results)

    hypo_dict = {
        "hypothesis": hypo.hypothesis,
        "supporting_fact_ids": _parse_list_field(hypo.supporting_fact_ids),
        "data_evidence_ids": _parse_list_field(getattr(hypo, "data_evidence_ids", None)),
        "dataset_field_refs": _parse_list_field(getattr(hypo, "dataset_field_refs", None)),
        "evidence_level": hypo.evidence_level or "medium",
        "validation_target": getattr(hypo, "validation_target", "") or "",
        "expected_measurable_effect": getattr(hypo, "expected_measurable_effect", "") or "",
        "verifiable_spec": {},
    }

    pipeline_hypos = [h for h in (hg.get("hypotheses") or []) if isinstance(h, dict)]
    matched_pipeline: Optional[Dict[str, Any]] = None
    for h in pipeline_hypos:
        if h.get("id") == hypothesis_id or h.get("hypothesis_id") == hypothesis_id:
            matched_pipeline = h
            break
    if matched_pipeline is None:
        hypo_text = (hypo.hypothesis or "").strip()
        for h in pipeline_hypos:
            if (h.get("hypothesis") or "").strip() == hypo_text:
                matched_pipeline = h
                break
    if matched_pipeline:
        hypo_dict.update(matched_pipeline)

    primary_idx = int(hg.get("primary_index") or 0)
    if pipeline_hypos:
        primary_idx = min(max(0, primary_idx), len(pipeline_hypos) - 1)
    primary_pipeline = pipeline_hypos[primary_idx] if pipeline_hypos else None
    is_primary = bool(
        matched_pipeline is not None
        and primary_pipeline is not None
        and (
            matched_pipeline is primary_pipeline
            or matched_pipeline.get("id") == primary_pipeline.get("id")
            or (matched_pipeline.get("hypothesis") or "").strip()
            == (primary_pipeline.get("hypothesis") or "").strip()
        )
    ) or (getattr(hypo, "priority", None) == 1 and matched_pipeline is None)

    sufficiency = assess_evidence_sufficiency(hypo_dict)
    facts = list(lm.get("facts") or [])
    fact_map = _fact_lookup(facts)

    literature: List[LiteratureGroundingItem] = []
    sfids = _parse_list_field(hypo_dict.get("supporting_fact_ids"))
    for fid in sfids:
        f = fact_map.get(str(fid), {})
        literature.append(LiteratureGroundingItem(
            fact_id=str(fid),
            content=str(f.get("content") or f.get("fact_text") or ""),
            quote_text=str(f.get("quote_text") or ""),
            source_title=str(f.get("source_paper_title") or f.get("source_title") or ""),
            document_id=str(f.get("document_id") or ""),
            relevance_score=f.get("relevance_score"),
        ))

    # 仅绑定到本假设的数据证据；不再把项目全部表格塞给每条假设
    data_items: List[DataGroundingItem] = []
    bound_data_ids = set(_parse_list_field(hypo_dict.get("data_evidence_ids")))
    for tbl in (df_results.get("extracted_tables") or [])[:24]:
        if not isinstance(tbl, dict):
            continue
        tid = str(tbl.get("table_id") or "")
        if bound_data_ids and tid not in bound_data_ids and str(tbl.get("source_title") or "") not in bound_data_ids:
            continue
        if not bound_data_ids:
            # 无绑定则不展示「数据依据」，避免所有假设显示同一批空/全局表
            continue
        data_items.append(DataGroundingItem(
            table_id=tid,
            source_title=str(tbl.get("source_title") or ""),
            source_type=str(tbl.get("source_type") or "paper_table"),
            csv_path=str(tbl.get("csv_path") or ""),
            row_count=tbl.get("row_count"),
            extraction_method=str(tbl.get("extraction_method") or ""),
        ))

    er_service = get_evidence_reasoning_service()
    chain = er_service.load_evidence_chain(hypo.project_id, hypothesis_id) or {}
    counter = list(chain.get("counter_evidence") or [])

    # 每条假设只用自己的 verifiable_spec；禁止非主假设回退到 primary（会导致验证页内容完全一样）
    vspec = hypo_dict.get("verifiable_spec") if isinstance(hypo_dict.get("verifiable_spec"), dict) else {}
    if not vspec:
        from app.core.iterative_science import build_verifiable_hypothesis_spec_for_mode

        vspec = build_verifiable_hypothesis_spec_for_mode(
            hypo.hypothesis or "",
            project_mode="general",
            hypo_meta=hypo_dict,
            experiment_design=ed if isinstance(ed, dict) else None,
        )
    # 沙箱/迭代实验结果属于主假设验证；非主假设不复用同一套 checks
    checks = evaluate_verifiable_spec_against_validation(sv, vspec) if (sv and is_primary) else []
    if not is_primary and vspec:
        # 仍给出基于本假设证据的轻量检查，避免空白但内容雷同
        fact_count = len(hypo_dict.get("supporting_fact_ids") or [])
        checks = [{
            "check_id": "own_evidence_sufficiency",
            "description": "本假设文献证据支撑",
            "expected": "supporting_fact_ids ≥ 1",
            "actual": f"facts={fact_count}, level={hypo_dict.get('evidence_level')}",
            "passed": fact_count > 0 and hypo_dict.get("evidence_level") != "low",
            "source": "hypothesis_provenance",
        }]

    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    tree = hg.get("hypothesis_tree") or {}
    selected_branch = None
    for b in tree.get("branches") or []:
        if b.get("branch_id") == tree.get("selected_branch_id"):
            selected_branch = b
            break

    compliance = (results.get("report_generation") or {}).get("compliance_check") or {}
    logic_review = compliance.get("proposal_logic_review") or {}
    logic_data = logic_review.get("data") if isinstance(logic_review, dict) else {}

    return HypothesisProvenanceResponse(
        hypothesis_id=hypothesis_id,
        hypothesis_text=hypo.hypothesis or "",
        origin=HypothesisOriginBlock(
            main_contradiction=str(pu.get("main_contradiction") or ""),
            phenomenon_contradiction=str(pu.get("phenomenon_contradiction") or ""),
            problem_statement=str(pu.get("problem_statement") or ""),
            research_significance=str(pu.get("research_significance") or ""),
            reasoning_chain=build_reasoning_chain(pu, kg),
        ),
        grounding=HypothesisGroundingBlock(
            literature=literature,
            data=data_items,
            multimodal=list(lm.get("multimodal_evidence") or [])[:6],
            counter_evidence=counter[:8],
            knowledge_gaps=[
                str(g.get("description", g)) for g in (kg.get("knowledge_gaps") or [])[:6]
                if isinstance(g, dict) or g
            ],
        ),
        verification=HypothesisVerificationBlock(
            verifiable_spec=vspec if isinstance(vspec, dict) else {},
            validation_target=str(hypo_dict.get("validation_target") or ""),
            expected_measurable_effect=str(hypo_dict.get("expected_measurable_effect") or ""),
            verification_checks=checks,
            sandbox_success=(
                (sv.get("sandbox_execution") or {}).get("success")
                if (sv and is_primary)
                else None
            ),
        ),
        evidence_sufficiency=str(sufficiency.get("evidence_sufficiency") or ""),
        evidence_level=str(hypo_dict.get("evidence_level") or "medium"),
        scores={
            "ensemble_overall": ensemble.get("overall") or hr.get("ensemble_overall"),
            "ensemble_decision": ensemble.get("decision") or hr.get("ensemble_decision"),
            "hypothesis_tree_score": (selected_branch or {}).get("composite_score"),
            "evidence_balance": chain.get("evidence_balance_score"),
            "logic_score": (logic_data or {}).get("logic_score") if isinstance(logic_data, dict) else None,
        },
    )


def build_material_supplement_plan(
    results: Dict[str, Any],
    *,
    trigger: str = "auto",
) -> MaterialSupplementPlan:
    """根据缺口生成资料补充计划（第三期）。"""
    triggers: List[str] = [trigger] if trigger else []
    actions: List[MaterialSupplementAction] = []
    queries: List[str] = []

    pu = results.get("problem_understanding") or {}
    kg = results.get("knowledge_gap") or {}
    hg = results.get("hypothesis_generation") or {}
    hr = results.get("hypothesis_review") or {}
    da = results.get("data_acquisition") or {}
    coverage = (da.get("coverage_report") or {}).get("completeness_score")

    hypotheses = hg.get("hypotheses") or []
    primary = hypotheses[0] if hypotheses else {}
    if isinstance(primary, dict):
        suff = assess_evidence_sufficiency(primary)
        if suff.get("evidence_sufficiency") in ("weak", "missing"):
            triggers.append("evidence_weak")
            actions.append(MaterialSupplementAction(
                action_type="literature_search",
                description="补充文献检索以绑定 supporting_fact_ids",
                priority="high",
                target="literature_mining",
            ))
            rq = pu.get("problem_statement") or pu.get("main_contradiction") or ""
            if rq:
                queries.append(str(rq)[:200])

    gaps = kg.get("knowledge_gaps") or []
    if gaps:
        triggers.append("knowledge_gap")
        for g in gaps[:2]:
            desc = g.get("description", g) if isinstance(g, dict) else str(g)
            if desc:
                queries.append(str(desc)[:120])

    if coverage is not None and float(coverage) < 70:
        triggers.append("data_coverage_low")
        actions.append(MaterialSupplementAction(
            action_type="data_gap_enrich",
            description=f"Coverage {coverage}% 低于阈值，触发 Gap 补搜与 CSV 合并",
            priority="high",
            target="experiment_design",
        ))

    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    decision = ensemble.get("decision") or hr.get("ensemble_decision")
    if decision and str(decision).lower() != "accept":
        triggers.append("review_reject")
        for w in (ensemble.get("weaknesses") or [])[:2]:
            actions.append(MaterialSupplementAction(
                action_type="hypothesis_refine",
                description=f"评审弱点: {w}",
                priority="medium",
                target="hypothesis_generation",
            ))

    return MaterialSupplementPlan(
        triggers=list(dict.fromkeys(triggers)),
        actions=actions,
        suggested_queries=list(dict.fromkeys(queries))[:6],
    )


def _extract_scores(results: Dict[str, Any]) -> IterationRoundScores:
    hr = results.get("hypothesis_review") or {}
    hg = results.get("hypothesis_generation") or {}
    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    tree = hg.get("hypothesis_tree") or {}
    branch = (tree.get("branches") or [{}])[0] if tree.get("branches") else {}
    chain = (results.get("evidence_reasoning") or {}).get("evidence_chain") or {}
    meta = results.get("_pipeline_extra") or {}
    trend = meta.get("quality_trend") or []
    gate_passed = None
    if trend:
        last = trend[-1]
        if "passed" in last:
            gate_passed = bool(last["passed"])
        else:
            s = last.get("score")
            if s is not None:
                try:
                    gate_passed = float(s) >= 50.0
                except (TypeError, ValueError):
                    pass
    compliance = (results.get("report_generation") or {}).get("compliance_check") or {}
    logic = (compliance.get("proposal_logic_review") or {}).get("data") or {}

    return IterationRoundScores(
        hypothesis_tree=branch.get("composite_score"),
        ensemble_overall=ensemble.get("overall") or hr.get("ensemble_overall"),
        evidence_balance=chain.get("evidence_balance_score"),
        logic_score=logic.get("logic_score") if isinstance(logic, dict) else None,
        cqs=100.0 if gate_passed else (0.0 if gate_passed is False else None),
        gate_passed=gate_passed,
    )


def build_iteration_round(
    round_num: int,
    trigger: str,
    results: Dict[str, Any],
    *,
    label: str = "",
    actions_taken: Optional[List[str]] = None,
    prev_scores: Optional[IterationRoundScores] = None,
    material_plan: Optional[MaterialSupplementPlan] = None,
) -> IterationRoundRecord:
    hg = results.get("hypothesis_generation") or {}
    hr = results.get("hypothesis_review") or {}
    tree = hg.get("hypothesis_tree") or {}
    selected = tree.get("selected_hypothesis") or {}
    hypo_text = ""
    if isinstance(selected, dict):
        hypo_text = str(selected.get("hypothesis") or "")
    if not hypo_text:
        reviews = hr.get("reviews") or []
        if reviews:
            hypo_text = str(reviews[0].get("hypothesis") or "")

    scores = _extract_scores(results)
    delta: Dict[str, Any] = {}
    if prev_scores and prev_scores.ensemble_overall is not None and scores.ensemble_overall is not None:
        delta["ensemble_delta"] = round(float(scores.ensemble_overall) - float(prev_scores.ensemble_overall), 2)
    if prev_scores and prev_scores.hypothesis_tree is not None and scores.hypothesis_tree is not None:
        delta["tree_score_delta"] = round(float(scores.hypothesis_tree) - float(prev_scores.hypothesis_tree), 2)

    return IterationRoundRecord(
        round=round_num,
        trigger=trigger,
        label=label or f"R{round_num}",
        hypothesis_preview=hypo_text[:400],
        actions_taken=list(actions_taken or []),
        scores=scores,
        delta_from_prev=delta,
        material_plan=material_plan,
        snapshot_label=label or f"R{round_num}",
    )


def build_session_from_results(
    project_id: str,
    run_id: str,
    results: Dict[str, Any],
    *,
    extra_metadata: Optional[Dict[str, Any]] = None,
    config: Optional[ScienceIterationConfig] = None,
) -> ScienceIterationSessionResponse:
    meta = extra_metadata or {}
    rounds_raw = list(meta.get("science_iteration_rounds") or [])
    rounds = [IterationRoundRecord(**r) if isinstance(r, dict) else r for r in rounds_raw]

    hg = results.get("hypothesis_generation") or {}
    hr = results.get("hypothesis_review") or {}
    snapshots = list(meta.get("version_snapshots") or [])
    plan_raw = meta.get("material_supplement_plan")
    plan = MaterialSupplementPlan(**plan_raw) if isinstance(plan_raw, dict) else build_material_supplement_plan(results)

    current_best = {
        "hypothesis_preview": (rounds[-1].hypothesis_preview if rounds else ""),
        "ensemble_decision": (hr.get("skill_outputs") or {}).get("ensemble_review", {}).get("decision")
        or hr.get("ensemble_decision"),
        "report_id": meta.get("final_report_id") or results.get("report_generation", {}).get("report_id"),
    }

    checkpoints = []
    for ev in meta.get("closed_loop_events") or []:
        if ev.get("type") in ("hitl_gate", "human_feedback", "teaching_auto_refinement"):
            checkpoints.append({
                "type": ev.get("type"),
                "at": ev.get("at"),
                "summary": ev.get("summary") or ev.get("reasons"),
            })

    return ScienceIterationSessionResponse(
        session_id=str(meta.get("science_iteration_session_id") or uuid.uuid4()),
        project_id=project_id,
        run_id=run_id,
        config=config or DEFAULT_CONFIG,
        rounds=rounds,
        current_best=current_best,
        version_snapshots=snapshots,
        material_supplement_plan=plan,
        human_checkpoints=checkpoints[:10],
    )


class ScienceIterationOrchestrator:
    """标准 Pipeline 自迭代编排（第二期 MVP）。"""

    def __init__(self, db: Session, pipeline_service: Any):
        self.db = db
        self.pipeline = pipeline_service

    def _get_config(self) -> ScienceIterationConfig:
        project_id = self.pipeline.db_pipeline_run.project_id if self.pipeline.db_pipeline_run else ""
        from app.services.project_service import ProjectService

        project = ProjectService(self.db).get_project(project_id)
        pcfg = project.config if project and isinstance(project.config, dict) else {}
        return resolve_science_iteration_config(pcfg, self.pipeline._run_options)

    def _append_round(
        self,
        results: Dict[str, Any],
        round_record: IterationRoundRecord,
    ) -> None:
        meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
        rounds = list(meta.get("science_iteration_rounds") or [])
        rounds.append(round_record.model_dump())
        meta["science_iteration_rounds"] = rounds[-10:]
        if not meta.get("science_iteration_session_id"):
            meta["science_iteration_session_id"] = str(uuid.uuid4())
        self.pipeline._persist_extra_metadata(meta)

    def record_milestone(
        self,
        results: Dict[str, Any],
        trigger: str,
        *,
        label: str = "",
        actions: Optional[List[str]] = None,
    ) -> None:
        cfg = self._get_config()
        if not cfg.enabled:
            return
        meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
        rounds = meta.get("science_iteration_rounds") or []
        round_num = len(rounds) + 1
        prev_scores = None
        if rounds:
            last = rounds[-1]
            if isinstance(last, dict) and last.get("scores"):
                try:
                    prev_scores = IterationRoundScores(**last["scores"])
                except Exception:
                    pass
        plan = build_material_supplement_plan(results, trigger=trigger) if trigger != "initial" else None
        rec = build_iteration_round(
            round_num, trigger, results,
            label=label or f"R{round_num}_{trigger}",
            actions_taken=actions,
            prev_scores=prev_scores,
            material_plan=plan,
        )
        self._append_round(results, rec)
        if plan and plan.actions:
            meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
            meta["material_supplement_plan"] = plan.model_dump()
            self.pipeline._persist_extra_metadata(meta)

    def _ensemble_accepted(self, results: Dict[str, Any], cfg: ScienceIterationConfig) -> Tuple[bool, float]:
        hr = results.get("hypothesis_review") or {}
        ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
        decision = str(ensemble.get("decision") or hr.get("ensemble_decision") or "").lower()
        overall = ensemble.get("overall") or hr.get("ensemble_overall")
        try:
            score = float(overall) if overall is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        if decision == "accept":
            return True, score
        return score >= cfg.min_ensemble_score, score

    def maybe_run_standard_refinement(
        self,
        stages: List[Any],
        results: Dict[str, Any],
        research_question: str,
        project_id: str,
        project_mode: str,
    ) -> Optional[Dict[str, Any]]:
        """评审未 Accept 时单轮 refine（标准模式）。"""
        cfg = self._get_config()
        if not cfg.enabled:
            return None
        if "review_reject" not in cfg.auto_triggers:
            return None
        if self.pipeline._run_options.get("pipeline_mode") == "discovery":
            return None

        meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
        refine_count = int(meta.get("science_iteration_refine_count") or 0)
        if refine_count >= max(1, cfg.max_rounds - 1):
            return None

        accepted, score = self._ensemble_accepted(results, cfg)
        if accepted:
            return None

        hr = results.get("hypothesis_review") or {}
        ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
        weaknesses = list(ensemble.get("weaknesses") or [])[:4]
        suggestions = list(ensemble.get("revision_suggestions") or [])[:4]
        self.pipeline._discovery_refinement = weaknesses + suggestions

        self.record_milestone(
            results, "review_reject",
            label=f"R{refine_count + 1}_before_refine",
            actions=[f"ensemble_score={score}", "inject_review_weaknesses"],
        )
        self.pipeline._capture_iteration_snapshot(refine_count + 1, results, label=f"refine_R{refine_count + 1}_before")

        logger.info("[ScienceIteration] 标准模式单轮 refine，score=%.1f", score)
        self.pipeline._run_stage(stages, 4, results, research_question, project_id,
            lambda: self.pipeline._exec_hypothesis_generation(
                results.get("problem_understanding"),
                results.get("literature_mining"),
                results.get("knowledge_gap"),
                results.get("ideation_novelty"),
            ))
        try:
            self.pipeline._exec_evidence_reasoning(project_id, research_question, results)
        except Exception as exc:
            logger.warning("refine 证据链失败: %s", exc)
        try:
            self.pipeline._exec_hypothesis_tree(results, research_question)
        except Exception as exc:
            logger.warning("refine 假设树失败: %s", exc)
        self.pipeline._run_stage(stages, 5, results, research_question, project_id,
            lambda: self.pipeline._exec_hypothesis_review(results.get("hypothesis_generation")))

        meta["science_iteration_refine_count"] = refine_count + 1
        self.pipeline._persist_extra_metadata(meta)
        self.pipeline._capture_iteration_snapshot(refine_count + 1, results, label=f"refine_R{refine_count + 1}_after")
        self.record_milestone(
            results, "review_refine_complete",
            label=f"R{refine_count + 1}_after_refine",
            actions=["reran_hypothesis_generation", "reran_hypothesis_review"],
        )

        plan = build_material_supplement_plan(results, trigger="review_refine")
        meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
        meta["material_supplement_plan"] = plan.model_dump()
        self.pipeline._persist_extra_metadata(meta)

        return {"refine_round": refine_count + 1, "ensemble_score_before": score}

    def maybe_supplement_literature_on_weak_evidence(
        self,
        results: Dict[str, Any],
        project_id: str,
        research_question: str,
    ) -> Optional[Dict[str, Any]]:
        cfg = self._get_config()
        if not cfg.enabled or not cfg.auto_literature_on_weak_evidence:
            return None
        if "evidence_weak" not in cfg.auto_triggers:
            return None

        hg = results.get("hypothesis_generation") or {}
        hypotheses = hg.get("hypotheses") or []
        if not hypotheses or not isinstance(hypotheses[0], dict):
            return None
        suff = assess_evidence_sufficiency(hypotheses[0])
        if suff.get("evidence_sufficiency") not in ("weak", "missing"):
            return None

        from app.services.literature_discovery_adapter import discover_and_import_literature

        pu = results.get("problem_understanding") or {}
        data_spec = (results.get("data_acquisition") or {}).get("data_spec") or {}
        discovery = discover_and_import_literature(
            self.db, project_id, research_question,
            data_spec=data_spec if isinstance(data_spec, dict) else None,
            max_papers=min(cfg.auto_literature_max, 5),
        )
        if discovery.get("imported_count", 0) > 0:
            self.record_milestone(
                results, "evidence_weak",
                actions=[f"auto_literature_import={discovery.get('imported_count')}"],
            )
        return discovery

    def finalize_session(self, results: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self._get_config()
        project_id = self.pipeline.db_pipeline_run.project_id if self.pipeline.db_pipeline_run else ""
        run_id = self.pipeline.run_id
        meta = dict(self.pipeline.db_pipeline_run.extra_metadata or {})
        session = build_session_from_results(
            project_id, run_id, results,
            extra_metadata=meta, config=cfg,
        )
        meta["science_iteration"] = session.model_dump()
        self.pipeline._persist_extra_metadata(meta)
        return session.model_dump()


def get_science_iteration_orchestrator(db: Session, pipeline_service: Any) -> ScienceIterationOrchestrator:
    return ScienceIterationOrchestrator(db, pipeline_service)
