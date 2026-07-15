"""
Report 服务
处理研究报告的数据库操作
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.project import Report, Project
from app.schemas.research import ReportCreate, ReportDBResponse, ReportBrowseItem
from app.core.database import get_db
from app.core.project_modes import normalize_project_mode
from app.services.latex_export_service import (
    export_report_via_latex,
    get_reports_storage_dir,
)

logger = logging.getLogger(__name__)


def backfill_project_report_if_missing(db: Session, project_id: str) -> Optional[Report]:
    """若项目无报告但 Pipeline 已完成报告阶段，尝试从阶段输出/磁盘补偿落库。"""
    if db.query(Report).filter(Report.project_id == project_id).first():
        return None

    from app.models.pipeline import (
        PipelineRun as DB_PipelineRun,
        PipelineStage as DB_PipelineStage,
        PipelineStageExecution as DB_PipelineStageExecution,
        PipelineStatus as DB_PipelineStatus,
    )
    from app.services.pipeline_service import PipelineService

    run = (
        db.query(DB_PipelineRun)
        .filter(
            DB_PipelineRun.project_id == project_id,
            DB_PipelineRun.status == DB_PipelineStatus.COMPLETED,
        )
        .order_by(DB_PipelineRun.completed_at.desc())
        .first()
    )
    if not run:
        return None

    stage_exec = (
        db.query(DB_PipelineStageExecution)
        .filter(
            DB_PipelineStageExecution.pipeline_run_id == run.id,
            DB_PipelineStageExecution.stage == DB_PipelineStage.REPORT_GENERATION,
            DB_PipelineStageExecution.status == DB_PipelineStatus.COMPLETED,
        )
        .first()
    )
    if not stage_exec or not stage_exec.output_data:
        return None

    svc = PipelineService(db)
    svc.run_id = run.run_id
    svc.db_pipeline_run = run
    if run.started_at:
        svc._pipeline_start = run.started_at
    report_id = svc._persist_pipeline_report(
        project_id,
        {"report_generation": stage_exec.output_data},
    )
    if not report_id:
        return None

    if not run.final_report_id:
        run.final_report_id = report_id
        db.commit()

    logger.info(
        "已从 Pipeline 阶段输出补偿落库报告 project_id=%s report_id=%s run_id=%s",
        project_id,
        report_id,
        run.run_id,
    )
    return db.query(Report).filter(Report.id == report_id).first()


def _parse_chapter_field(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str) and val.strip():
        stripped = val.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
    return val


def _chapter_to_db_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def merge_report_extra_metadata(
    base: Optional[Dict[str, Any]],
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """合并合规指标与 LaTeX PDF 导出元数据（Pipeline / API 共用）。"""
    extra = dict(base or {})
    plots = report_data.get("plots")
    if isinstance(plots, list) and plots:
        from app.services.report_plot_service import prepare_plots_for_persistence

        file_id = report_data.get("report_id") or report_data.get("pdf_path")
        extra["plots"] = prepare_plots_for_persistence(
            plots,
            report_file_id=str(file_id) if file_id else None,
            keep_base64=False,
        )
    if "pdf_success" in report_data:
        extra["pdf_success"] = bool(report_data.get("pdf_success"))
    if report_data.get("export_method"):
        extra["export_method"] = report_data["export_method"]
    if report_data.get("warning"):
        extra["pdf_warning"] = report_data["warning"]
    return extra


def report_pdf_exists(file_id: Optional[str]) -> bool:
    """检查报告目录下是否已有有效 PDF。"""
    if not file_id:
        return False
    pdf_path = get_reports_storage_dir() / file_id / "report.pdf"
    return pdf_path.is_file() and pdf_path.stat().st_size > 0


def report_to_db_response(
    report: Report,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> ReportDBResponse:
    """将 ORM Report 转为 API 响应（补齐 report_id / pdf_generated）。"""
    file_id = report.pdf_path
    extra = extra_metadata if extra_metadata is not None else (
        report.extra_metadata if isinstance(report.extra_metadata, dict) else {}
    )
    pdf_generated = report_pdf_exists(file_id) or bool(extra.get("pdf_success"))
    if extra.get("export_method") == "latex" and extra.get("pdf_success") is False:
        pdf_generated = False

    return ReportDBResponse(
        id=report.id,
        project_id=report.project_id,
        hypothesis_id=report.hypothesis_id,
        experiment_design_id=report.experiment_design_id,
        small_validation_id=report.small_validation_id,
        title=report.title,
        paper_title=report.paper_title,
        paper_abstract=report.paper_abstract,
        markdown_content=report.markdown_content,
        problem_statement=report.problem_statement,
        rationale=report.rationale,
        technical_details=report.technical_details,
        datasets=report.datasets,
        source=report.source,
        target=report.target,
        methods=report.methods,
        experiments=report.experiments,
        results=report.results,
        references=report.references,
        report_id=file_id,
        pdf_generated=pdf_generated,
        status=report.status,
        version=report.version or 1,
        extra_metadata=extra or None,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _report_fields_from_iterative_stage(
    ie_stage: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """从 iterative_experiment 阶段输出解析报告用 ed/sv（不再读顶层旧键/DB 实验设计表）。"""
    if not isinstance(ie_stage, dict):
        return {}, {}
    ed = ie_stage.get("experiment_design") if isinstance(ie_stage.get("experiment_design"), dict) else {}
    sv = ie_stage.get("small_validation") if isinstance(ie_stage.get("small_validation"), dict) else {}
    if ed and sv:
        return ed, sv
    experiments = ie_stage.get("experiments") or []
    primary = None
    pid = ie_stage.get("primary_experiment_id")
    if pid:
        primary = next((e for e in experiments if isinstance(e, dict) and e.get("id") == pid), None)
    if not primary and experiments and isinstance(experiments[0], dict):
        primary = experiments[0]
    if primary:
        from app.services.iterative_experiment_service import IterativeExperimentService

        synth = IterativeExperimentService.synthesize_report_fields(primary)
        ed = ed or synth.get("experiment_design") or {}
        sv = sv or synth.get("small_validation") or {}
    return ed if isinstance(ed, dict) else {}, sv if isinstance(sv, dict) else {}


def enrich_report_for_response(report: Report, db: Session) -> ReportDBResponse:
    """读取报告时重算合规指标，对齐 Pipeline 文献阶段与 References 章节。"""
    from app.models.pipeline import PipelineStage
    from app.services._utils.pipeline_queries import get_latest_pipeline_run, get_literature_mining_output, get_stage_output
    from app.services.literature_bundle_service import enrich_literature_mining
    from app.services.report_compliance_service import enrich_report_extra_metadata

    literature_mining = enrich_literature_mining(get_literature_mining_output(db, report.project_id))
    hypotheses: List[Dict[str, Any]] = []
    experiment_design: Optional[Dict[str, Any]] = None
    latest_run = get_latest_pipeline_run(db, report.project_id)
    if latest_run:
        hg = get_stage_output(db, latest_run.id, PipelineStage.HYPOTHESIS_GENERATION)
        if isinstance(hg, dict):
            hypotheses = hg.get("hypotheses") or []
        ie_stage = get_stage_output(db, latest_run.id, PipelineStage.ITERATIVE_EXPERIMENT)
        ed, _sv = _report_fields_from_iterative_stage(
            ie_stage if isinstance(ie_stage, dict) else None
        )
        experiment_design = ed or None

    extra = enrich_report_extra_metadata(
        report,
        literature_mining=literature_mining if isinstance(literature_mining, dict) else None,
        hypotheses=hypotheses if isinstance(hypotheses, list) else [],
        experiment_design=experiment_design,
    )
    return report_to_db_response(report, extra_metadata=extra)


class ReportService:
    """研究报告服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_report(self, report_data: ReportCreate) -> Report:
        """创建新的研究报告"""
        try:
            db_report = Report(
                project_id=report_data.project_id,
                hypothesis_id=report_data.hypothesis_id,
                experiment_design_id=report_data.experiment_design_id,
                small_validation_id=report_data.small_validation_id,
                pdf_path=report_data.report_id,  # 旧 report_id 映射为 pdf_path
                title=report_data.title,
                paper_title=report_data.paper_title,
                paper_abstract=report_data.paper_abstract,
                markdown_content=report_data.markdown_content,
                problem_statement=report_data.problem_statement,
                rationale=report_data.rationale,
                technical_details=report_data.technical_details,
                datasets=report_data.datasets,
                source=report_data.source,
                target=report_data.target,
                methods=report_data.methods,
                experiments=report_data.experiments,
                results=report_data.results,
                references=report_data.references,
                status=report_data.status or "draft",
                version=report_data.version or 1,
                extra_metadata=report_data.extra_metadata
            )
            
            self.db.add(db_report)
            self.db.commit()
            self.db.refresh(db_report)
            
            logger.info(f"创建研究报告成功，ID: {db_report.id}")
            return db_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建研究报告失败: {e}", exc_info=True)
            raise
    
    def get_report_by_id(self, report_id: str) -> Optional[Report]:
        """根据 ID 获取研究报告"""
        return self.db.query(Report).filter(
            Report.id == report_id
        ).first()
    
    def get_reports_by_project(
        self,
        project_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Report]:
        """获取项目的研究报告列表"""
        query = self.db.query(Report).filter(
            Report.project_id == project_id
        )
        
        if status:
            query = query.filter(Report.status == status)
        
        reports = query.order_by(
            Report.created_at.desc()
        ).limit(limit).offset(offset).all()

        if not reports and offset == 0:
            backfilled = backfill_project_report_if_missing(self.db, project_id)
            if backfilled:
                return [backfilled]

        return reports
    
    def get_latest_report_by_project(
        self,
        project_id: str,
        *,
        ensure_pdf: bool = True,
    ) -> Optional[Report]:
        """获取项目最新的研究报告；可选在 PDF 缺失时自动补生成。"""
        report = self.db.query(Report).filter(
            Report.project_id == project_id
        ).order_by(
            Report.created_at.desc()
        ).first()
        if not report:
            report = backfill_project_report_if_missing(self.db, project_id)
        if report and ensure_pdf and report.pdf_path and not report_pdf_exists(report.pdf_path):
            try:
                self.regenerate_pdf(report.id)
                self.db.refresh(report)
            except Exception as exc:
                logger.warning("自动补生成 PDF 失败 report=%s: %s", report.id, exc)
        return report

    def browse_reports(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        project_mode: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[ReportBrowseItem], int]:
        """跨项目分页浏览报告，支持时间与项目模式筛选。"""
        page = max(1, page)
        page_size = max(1, min(page_size, 50))

        query = (
            self.db.query(Report, Project)
            .join(Project, Report.project_id == Project.id)
        )

        if project_mode and project_mode not in ("", "all"):
            normalized = normalize_project_mode(project_mode)
            query = query.filter(Project.project_mode == normalized)

        if date_from is not None:
            query = query.filter(Report.created_at >= date_from)
        if date_to is not None:
            query = query.filter(Report.created_at <= date_to)

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    Report.title.ilike(kw),
                    Report.paper_title.ilike(kw),
                    Project.name.ilike(kw),
                    Project.research_question.ilike(kw),
                )
            )

        total = query.count()
        rows = (
            query.order_by(Report.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items: List[ReportBrowseItem] = []
        for report, project in rows:
            items.append(
                ReportBrowseItem(
                    id=report.id,
                    project_id=project.id,
                    project_name=project.name,
                    project_mode=normalize_project_mode(project.project_mode or "general"),
                    research_question=project.research_question,
                    title=report.title,
                    paper_title=report.paper_title,
                    status=report.status,
                    version=report.version or 1,
                    created_at=report.created_at,
                    updated_at=report.updated_at,
                )
            )
        return items, total
    
    def update_report(
        self,
        report_id: str,
        update_data: dict
    ) -> Optional[Report]:
        """更新研究报告"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            return None
        
        try:
            # 如果更新内容包含版本信息，递增版本
            if "version" in update_data:
                update_data["version"] = int(update_data["version"])
            else:
                update_data["version"] = db_report.version + 1
            
            for key, value in update_data.items():
                if hasattr(db_report, key):
                    setattr(db_report, key, value)
            
            self.db.commit()
            self.db.refresh(db_report)
            
            logger.info(f"更新研究报告成功，ID: {report_id}")
            return db_report
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新研究报告失败: {e}", exc_info=True)
            raise

    def sync_from_stage_human_output(
        self,
        project_id: str,
        run_id: str,
        stage_output: Dict[str, Any],
    ) -> Optional[str]:
        """将报告阶段 human_modified_output 同步到 Report 表，供报告 Tab 展示。"""
        from app.models.pipeline import PipelineRun
        from app.services.data_finder_slim import resolve_report_generation_payload

        payload = resolve_report_generation_payload(stage_output) or stage_output
        if not isinstance(payload, dict) or not payload:
            return None

        run = self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        db_report: Optional[Report] = None
        if run and run.final_report_id:
            db_report = self.get_report_by_id(run.final_report_id)
        if not db_report:
            db_report = (
                self.db.query(Report)
                .filter(Report.project_id == project_id)
                .order_by(Report.updated_at.desc(), Report.created_at.desc())
                .first()
            )
        if not db_report:
            logger.warning(
                "报告 HITL 同步跳过：未找到 Report project=%s run=%s", project_id, run_id
            )
            return None

        chapters = payload.get("chapters", {}) if isinstance(payload.get("chapters"), dict) else {}
        title = str(payload.get("paper_title") or payload.get("title") or db_report.title or "研究报告")
        db_report.title = title
        db_report.paper_title = title
        if payload.get("paper_abstract") is not None:
            db_report.paper_abstract = _chapter_to_db_text(payload.get("paper_abstract"))

        chapter_fields = (
            "problem_statement",
            "rationale",
            "technical_details",
            "datasets",
            "source",
            "target",
            "methods",
            "experiments",
            "results",
        )
        for field in chapter_fields:
            if field in chapters:
                setattr(db_report, field, _chapter_to_db_text(chapters[field]))
            elif field in payload:
                setattr(db_report, field, _chapter_to_db_text(payload[field]))

        if "references" in chapters:
            refs = chapters["references"]
            db_report.references = (
                json.dumps(refs, ensure_ascii=False) if isinstance(refs, (list, dict)) else _chapter_to_db_text(refs)
            )
        elif "references" in payload:
            refs = payload["references"]
            db_report.references = (
                json.dumps(refs, ensure_ascii=False) if isinstance(refs, (list, dict)) else _chapter_to_db_text(refs)
            )

        extra = merge_report_extra_metadata(
            db_report.extra_metadata if isinstance(db_report.extra_metadata, dict) else {},
            payload,
        )
        extra["last_hitl_sync_at"] = datetime.now().isoformat()
        extra["hitl_sync_run_id"] = run_id
        db_report.extra_metadata = extra
        db_report.version = int(db_report.version or 1) + 1
        db_report.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(db_report)
        logger.info(
            "报告 HITL 同步成功 project=%s run=%s report_id=%s",
            project_id,
            run_id,
            db_report.id,
        )
        return db_report.id
    
    def _re_enrich_report_chapters(self, db_report: Report) -> Dict[str, Any]:
        """用 Pipeline 数据上下文回填/补全报告章节（尤其 results 与 FITS 数据）。"""
        from app.agents.report_generation_agent import get_report_generation_agent
        from app.models.pipeline import PipelineStage
        from app.services.data_finder_service import get_data_finder_service
        from app.services.dataset_service import DatasetService
        from app.services.data_finder_slim import slim_data_context
        from app.services._utils.pipeline_queries import get_latest_pipeline_run, get_stage_output

        agent = get_report_generation_agent()
        chapters: Dict[str, Any] = {
            "problem_statement": db_report.problem_statement or "",
            "rationale": db_report.rationale or "",
            "technical_details": db_report.technical_details or "",
            "datasets": _parse_chapter_field(db_report.datasets),
            "source": db_report.source or "",
            "target": db_report.target or "",
            "methods": db_report.methods or "",
            "experiments": _parse_chapter_field(db_report.experiments),
            "results": _parse_chapter_field(db_report.results),
        }
        result: Dict[str, Any] = {"chapters": chapters, "title": db_report.title}

        data_context: Dict[str, Any] = {}
        try:
            data_context = slim_data_context(
                DatasetService(self.db).get_project_data_context(db_report.project_id)
            )
        except Exception as exc:
            logger.warning("re_enrich: 获取 data_context 失败: %s", exc)

        df_results = get_data_finder_service(self.db).load_results(db_report.project_id) or {}
        if isinstance(df_results, dict) and df_results:
            data_context["data_finder_results"] = df_results
            result = agent._enrich_report_with_data_finder(result, df_results)

        experiment_design: Dict[str, Any] = {}
        small_validation: Dict[str, Any] = {}
        latest_run = get_latest_pipeline_run(self.db, db_report.project_id)
        if latest_run:
            ie_stage = get_stage_output(self.db, latest_run.id, PipelineStage.ITERATIVE_EXPERIMENT)
            experiment_design, small_validation = _report_fields_from_iterative_stage(
                ie_stage if isinstance(ie_stage, dict) else None
            )
            if isinstance(ie_stage, dict):
                data_context = {
                    **data_context,
                    "iterative_experiment": {
                        "status": ie_stage.get("status"),
                        "primary_experiment_id": ie_stage.get("primary_experiment_id"),
                        "report_experiment_ids": ie_stage.get("report_experiment_ids") or [],
                    },
                }

        result = agent._backfill_chapters_from_pipeline(
            result,
            experiment_design=experiment_design,
            data_context=data_context,
            small_validation=small_validation,
        )
        enriched = result.get("chapters")
        return enriched if isinstance(enriched, dict) else chapters

    def _load_literature_bundle_for_report(
        self, db_report: Report
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """加载 Pipeline 文献阶段数据，供引用验证与质量检查使用。"""
        from app.services._utils.pipeline_queries import get_literature_mining_output
        from app.services.literature_bundle_service import enrich_literature_mining
        from app.services.report_compliance_service import (
            literature_bundle_from_pipeline_stage,
            normalize_literature_bundle,
        )

        extra = dict(db_report.extra_metadata or {})
        lm = enrich_literature_mining(get_literature_mining_output(self.db, db_report.project_id))
        facts, citation_map, verified = literature_bundle_from_pipeline_stage(
            lm if isinstance(lm, dict) else None
        )
        if not citation_map and not verified:
            facts, citation_map, verified = normalize_literature_bundle(
                {
                    "facts": extra.get("evidence_facts") or [],
                    "citation_map": extra.get("citation_map") or [],
                    "verified_references": extra.get("verified_references") or [],
                }
            )
        return facts, citation_map, verified

    def _refresh_report_plots_and_quality(
        self,
        db_report: Report,
        chapters: Dict[str, Any],
        *,
        charts_dir: str,
        verified_references: Optional[List[Dict[str, Any]]] = None,
        references_verified: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """从项目数据生成图表并重跑质量检查。"""
        from app.agents.report_generation_agent import ReportGenerationAgent
        from app.services.report_charts_service import generate_report_plots_from_project
        from app.services.report_compliance_service import reconcile_reference_check, parse_report_references

        plots = generate_report_plots_from_project(
            db_report.project_id,
            self.db,
            charts_dir,
        )
        from app.services.report_plot_service import prepare_plots_for_persistence

        plots = prepare_plots_for_persistence(
            plots,
            report_file_id=db_report.pdf_path,
            keep_base64=False,
        )

        refs = parse_report_references(db_report.references)
        lit_facts, citation_map, pipeline_verified = self._load_literature_bundle_for_report(
            db_report
        )
        verified_list = list(verified_references or pipeline_verified or [])
        ref_check = reconcile_reference_check(
            refs,
            citation_map,
            verified_list,
            lit_facts,
        )
        refs_verified = (
            references_verified
            if references_verified is not None
            else ref_check.get("verified_count", 0)
        )

        chapters_for_qc = dict(chapters)
        if refs and not chapters_for_qc.get("references"):
            chapters_for_qc["references"] = refs

        report_payload = {
            "paper_title": db_report.paper_title,
            "paper_abstract": db_report.paper_abstract,
            "references": refs,
            "chapters": chapters_for_qc,
            "plots": plots,
        }
        chart_outputs = {"scientific_plot": {"data": {"charts": plots}}} if plots else {}
        qc_output = ReportGenerationAgent._run_quality_check_sync(
            report_payload,
            verified_list,
            chart_outputs,
            references_verified=refs_verified,
        )
        return plots, qc_output

    def regenerate_pdf(
        self,
        report_id: str,
        *,
        citation_map: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        """为已有报告按 LaTeX 模板重新导出 PDF。"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            raise ValueError("报告不存在")
        file_id = db_report.pdf_path
        if not file_id:
            raise ValueError("报告未关联文件目录，无法生成 PDF")

        enriched_chapters = self._re_enrich_report_chapters(db_report)
        from app.services.report_compliance_service import ensure_technical_details_qwen_disclosure

        td_raw = enriched_chapters.get("technical_details", db_report.technical_details)
        enriched_chapters["technical_details"] = ensure_technical_details_qwen_disclosure(td_raw)
        chapter_fields = (
            "problem_statement", "rationale", "technical_details", "datasets",
            "source", "target", "methods", "experiments", "results",
        )
        for key in chapter_fields:
            if key in enriched_chapters:
                setattr(db_report, key, _chapter_to_db_text(enriched_chapters[key]))
        db_report.version = (db_report.version or 1) + 1

        refs = db_report.references
        try:
            refs_list = json.loads(refs) if isinstance(refs, str) and refs.strip().startswith("[") else refs
        except json.JSONDecodeError:
            refs_list = [refs] if refs else []

        export_dir = get_reports_storage_dir() / file_id
        from app.services.report_charts_service import get_public_charts_dir

        charts_dir = str(get_public_charts_dir())
        plots, qc_output = self._refresh_report_plots_and_quality(
            db_report,
            enriched_chapters,
            charts_dir=charts_dir,
        )

        result = {
            "title": db_report.title,
            "paper_title": db_report.paper_title,
            "paper_abstract": db_report.paper_abstract,
            "plots": plots,
            "chapters": {
                "problem_statement": enriched_chapters.get("problem_statement", db_report.problem_statement),
                "rationale": enriched_chapters.get("rationale", db_report.rationale),
                "technical_details": enriched_chapters.get("technical_details", db_report.technical_details),
                "datasets": enriched_chapters.get("datasets", db_report.datasets),
                "source": enriched_chapters.get("source", db_report.source),
                "target": enriched_chapters.get("target", db_report.target),
                "methods": enriched_chapters.get("methods", db_report.methods),
                "experiments": enriched_chapters.get("experiments", db_report.experiments),
                "results": enriched_chapters.get("results", db_report.results),
                "references": refs_list if isinstance(refs_list, list) else [],
            },
        }
        verified = list(citation_map or [])
        json_path = export_dir / "report_data.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if not verified:
                    verified = list(saved.get("citation_map") or saved.get("verified_references") or [])
            except (json.JSONDecodeError, OSError):
                pass
        if not verified and isinstance(refs_list, list):
            from app.services.latex_export_service import parse_reference_line_to_item

            for r in refs_list:
                if not isinstance(r, str) or not r.strip():
                    continue
                parsed = parse_reference_line_to_item(r)
                if parsed.get("title"):
                    verified.append(parsed)
                else:
                    verified.append({"title": r.strip()})

        from app.services.report_content_sanitizer import sanitize_report_result

        export_result = export_report_via_latex(
            result=sanitize_report_result(result),
            output_dir=str(export_dir),
            project_info={"title": db_report.paper_title},
            citation_map=citation_map or verified,
            verified_references=verified,
        )
        result_payload = {
            "success": export_result.get("pdf_success", False),
            "pdf_success": export_result.get("pdf_success", False),
            "pdf_path": export_result.get("pdf_path"),
            "warning": export_result.get("warning"),
            "export_method": export_result.get("export_method"),
        }

        from app.services.report_service import enrich_report_for_response

        extra = dict((enrich_report_for_response(db_report, self.db).extra_metadata) or {})
        extra["plots"] = plots
        if qc_output:
            extra["report_quality_check"] = qc_output
        extra["pdf_success"] = bool(result_payload.get("pdf_success", False))
        if result_payload.get("export_method"):
            extra["export_method"] = result_payload["export_method"]
        if result_payload.get("pdf_success"):
            extra.pop("pdf_warning", None)
        elif result_payload.get("warning"):
            extra["pdf_warning"] = result_payload["warning"]

        db_report.extra_metadata = extra
        db_report.markdown_content = ""
        self.db.commit()
        self.db.refresh(db_report)

        return {
            **result_payload,
            "report": report_to_db_response(db_report),
        }

    def delete_report(self, report_id: str) -> bool:
        """删除研究报告及其导出文件。"""
        db_report = self.get_report_by_id(report_id)
        if not db_report:
            return False

        file_id = db_report.pdf_path
        try:
            self.db.delete(db_report)
            self.db.commit()

            if file_id:
                import shutil
                export_dir = get_reports_storage_dir() / file_id
                if export_dir.exists():
                    shutil.rmtree(export_dir, ignore_errors=True)

            logger.info(f"删除研究报告成功，ID: {report_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"删除研究报告失败: {e}", exc_info=True)
            raise

    def get_plot_image_path(self, report_id: str, plot_id: str) -> Optional[Path]:
        """解析报告图表 PNG 路径。"""
        from app.services.report_plot_service import resolve_plot_image_path

        report = self.get_report_by_id(report_id)
        if not report:
            return None
        extra = report.extra_metadata if isinstance(report.extra_metadata, dict) else {}
        return resolve_plot_image_path(
            extra,
            plot_id,
            report_file_id=report.pdf_path,
        )


def get_report_service() -> ReportService:
    """获取 ReportService 实例"""
    db = next(get_db())
    return ReportService(db)
