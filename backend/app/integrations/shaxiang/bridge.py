"""Shaxiang ExperimentService 桥接：注入 AISci llm_runtime，投影到项目 JSON。

失败显式抛错，不静默 mock。

与 Streamlit 直跑的关键差异修复：
1. 工作目录必须为 shaxiang 根（smoke/charts 用相对路径 data/charts）
2. 设计脚本 JSON 含完整 analysis_script，max_tokens 需高于 shaxiang 默认 4096
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

_svc_fingerprint: Optional[str] = None
_shaxiang_modules_mtime: Optional[float] = None

# shaxiang .env.example 默认 4096；ExperimentPlan+脚本易被截断，尤其 qwen3.6-max
SHAXIANG_MAX_TOKENS = 16384

# 热更新这些模块，避免 uvicorn 不 --reload 时仍用旧 AutoDetect / verify 逻辑
_SHAXIANG_HOT_RELOAD_GLOBS = (
    "services/experiment_service.py",
    "executors/numeric_coerce.py",
    "executors/directory_loader.py",
    "executors/adaptive_table_combine.py",
    "executors/data_adapter.py",
    "core/script_validator.py",
    "core/dataset_profiler.py",
)

T = TypeVar("T")


class ShaxiangBridgeError(RuntimeError):
    """迭代实验 / shaxiang 可对用户展示的业务错误。"""


def shaxiang_root() -> Path:
    # backend/app/integrations/shaxiang/bridge.py → AISci/
    return Path(__file__).resolve().parents[4] / "shaxiang-main" / "shaxiang-main"


def _shaxiang_sources_mtime(root: Path) -> float:
    latest = 0.0
    for rel in _SHAXIANG_HOT_RELOAD_GLOBS:
        p = root / rel
        if p.is_file():
            latest = max(latest, p.stat().st_mtime)
    return latest


def _reload_shaxiang_modules_if_changed(root: Path) -> bool:
    """源码变更时 reload shaxiang 包并重置 ExperimentService 单例。"""
    global _shaxiang_modules_mtime
    import importlib

    mtime = _shaxiang_sources_mtime(root)
    if _shaxiang_modules_mtime is not None and mtime <= _shaxiang_modules_mtime:
        return False

    prefixes = (
        "services.",
        "executors.",
        "core.",
        "llm.",
        "schemas.",
        "config.",
    )
    exact = {
        "services",
        "executors",
        "core",
        "llm",
        "schemas",
        "config",
    }
    names = [
        name
        for name in list(sys.modules)
        if name in exact or any(name.startswith(p) for p in prefixes)
    ]
    # 先清子模块再清父包，避免残留旧类
    for name in sorted(names, key=lambda n: n.count("."), reverse=True):
        sys.modules.pop(name, None)

    try:
        from services.experiment_service import ExperimentService

        ExperimentService.reset()
    except Exception:
        pass

    _shaxiang_modules_mtime = mtime
    logger.info("Shaxiang 模块已热重载 (mtime=%.0f)", mtime)
    return True


def ensure_shaxiang_path() -> Path:
    root = shaxiang_root()
    if not root.is_dir():
        raise ShaxiangBridgeError(
            f"未找到 shaxiang-main（期望路径: {root}）。请将 shaxiang 放到仓库根目录后再使用迭代实验。"
        )
    path = str(root)
    if path not in sys.path:
        sys.path.insert(0, path)
    for sub in ("data", "data/uploads", "data/charts", "data/charts/smoke"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _reload_shaxiang_modules_if_changed(root)
    return root


@contextmanager
def shaxiang_workdir():
    """对齐 Streamlit：在 shaxiang 根目录下执行（相对 chart/upload 路径才正确）。"""
    root = ensure_shaxiang_path()
    prev = os.getcwd()
    os.chdir(str(root))
    try:
        yield root
    finally:
        try:
            os.chdir(prev)
        except Exception:
            pass


def uploads_dir(project_id: str) -> Path:
    root = ensure_shaxiang_path()
    dest = root / "data" / "uploads" / project_id
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _llm_fingerprint() -> str:
    from app.core.llm_runtime import (
        get_effective_api_key,
        get_effective_base_url,
        get_effective_model,
        get_effective_use_mock_llm,
    )

    key = (get_effective_api_key() or "").strip()
    return "|".join(
        [
            "mock" if get_effective_use_mock_llm() else "real",
            key[:6] + "…" + key[-4:] if len(key) > 10 else ("set" if key else "empty"),
            get_effective_model() or "",
            get_effective_base_url() or "",
            f"mt{SHAXIANG_MAX_TOKENS}",
        ]
    )


def require_real_llm() -> None:
    from app.core.llm_runtime import get_effective_api_key, get_effective_use_mock_llm

    if get_effective_use_mock_llm():
        raise ShaxiangBridgeError(
            "迭代实验需要真实 LLM，请在右上角「高级」中关闭模拟 LLM，并配置 API 密钥与模型。"
        )
    if not (get_effective_api_key() or "").strip():
        raise ShaxiangBridgeError(
            "未配置 API 密钥。请在右上角「高级」设置中配置 Qwen API Key 与模型后再使用迭代实验。"
        )


def _translate_llm_error(exc: BaseException) -> BaseException:
    if isinstance(exc, ShaxiangBridgeError):
        return exc
    if isinstance(exc, ValueError):
        return exc
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()
    if (
        "unterminated string" in low
        or "结构化输出" in msg
        or "重试耗尽" in msg
        or "json" in low and ("parse" in low or "decode" in low)
    ):
        return ShaxiangBridgeError(
            "设计脚本时模型返回的 JSON 被截断或无法解析（脚本字段过长时常见）。"
            f"桥接已使用 max_tokens={SHAXIANG_MAX_TOKENS}；"
            "可在右上角「高级」改用 qwen-plus / qwen3.5-plus 后再试「确认并设计分析脚本」。"
            f" 详情: {msg}"
        )
    return ShaxiangBridgeError(f"迭代实验失败: {msg}")


def _run_in_shaxiang(fn: Callable[[], T]) -> T:
    with shaxiang_workdir():
        try:
            return fn()
        except BaseException as exc:
            raise _translate_llm_error(exc) from exc


def get_service():
    """获取已注入主项目 LLM 的 ExperimentService 单例。"""
    global _svc_fingerprint
    require_real_llm()
    root = ensure_shaxiang_path()
    fp = _llm_fingerprint()

    from services.experiment_service import ExperimentService
    from config.settings import AppConfig, LLMConfig, StorageConfig

    if ExperimentService._instance is not None and _svc_fingerprint != fp:
        ExperimentService.reset()
        _svc_fingerprint = None

    if ExperimentService._instance is None:
        from app.core.llm_runtime import (
            get_effective_api_key,
            get_effective_base_url,
            get_effective_model,
        )
        from executors.sandbox import SandboxExecutor

        db_path = str(root / "data" / "experiments.db")
        cfg = AppConfig(
            llm=LLMConfig(
                base_url=get_effective_base_url(),
                api_key=get_effective_api_key().strip(),
                model=get_effective_model(),
                temperature=0.3,
                max_tokens=SHAXIANG_MAX_TOKENS,
            ),
            storage=StorageConfig(db_path=db_path),
        )
        # 在 shaxiang 根下初始化，使相对路径 mkdir 落在正确位置
        with shaxiang_workdir():
            ExperimentService._instance = ExperimentService(cfg)
            # 全量执行器也改为绝对路径，避免 uvicorn CWD=backend 写错目录
            ExperimentService._instance.executor.register(
                SandboxExecutor(
                    data_dir=str(root / "data" / "uploads"),
                    chart_dir=str(root / "data" / "charts"),
                )
            )
        _svc_fingerprint = fp
        logger.info(
            "Shaxiang ExperimentService 已初始化 model=%s max_tokens=%s db=%s cwd_root=%s",
            get_effective_model(),
            SHAXIANG_MAX_TOKENS,
            db_path,
            root,
        )
    return ExperimentService._instance


def _dump_plan(plan: Any) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    if hasattr(plan, "model_dump"):
        d = plan.model_dump()
    elif isinstance(plan, dict):
        d = plan
    else:
        return None
    return {
        "title": d.get("title") or "",
        "description": d.get("description") or "",
        "methodology": d.get("methodology") or "",
        "analysis_script": d.get("analysis_script") or "",
        "script_params": d.get("script_params") or {},
        "success_criteria": d.get("success_criteria") or [],
    }


def _normalize_recs(raw: Any) -> List[Dict[str, Any]]:
    from app.core.dataset_urls import normalize_dataset_rec_dict

    items: List[Any] = []
    if raw is None:
        return []
    if hasattr(raw, "recommended_datasets"):
        items = list(raw.recommended_datasets or [])
    elif isinstance(raw, list):
        items = list(raw)
    else:
        return []

    out: List[Dict[str, Any]] = []
    for it in items:
        if hasattr(it, "model_dump"):
            d = it.model_dump()
        elif isinstance(it, dict):
            d = dict(it)
        else:
            continue
        out.append(normalize_dataset_rec_dict(d))
    return out


def _extract_chart_entries(result: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """对齐 shaxiang iteration_timeline：从 raw_output.chart_paths 等提取图表。"""
    root = shaxiang_root()
    charts_root = (root / "data" / "charts").resolve()
    candidates: List[str] = []

    raw = result.get("raw_output") if isinstance(result.get("raw_output"), dict) else {}
    for p in raw.get("chart_paths") or []:
        if isinstance(p, str) and p.strip():
            candidates.append(p.strip())

    for dp in result.get("data_points") or []:
        if isinstance(dp, dict) and dp.get("key") == "chart_path" and isinstance(dp.get("value"), str):
            candidates.append(dp["value"])

    for c in result.get("charts") or []:
        if isinstance(c, str):
            candidates.append(c)
        elif isinstance(c, dict):
            for key in ("path", "file_path", "name"):
                if isinstance(c.get(key), str) and c.get(key):
                    candidates.append(c[key])
                    break

    viz_notes: Dict[str, str] = {}
    for i, note in enumerate(analysis.get("visualization_notes") or []):
        if not isinstance(note, dict):
            continue
        desc = (note.get("description") or "").strip()
        if not desc:
            continue
        name = (note.get("chart_name") or "").strip()
        if name:
            viz_notes[Path(name).name.lower()] = desc
        viz_notes[str(i)] = desc

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw_path in enumerate(candidates):
        path = Path(raw_path)
        if not path.is_absolute():
            path = (root / raw_path).resolve()
        else:
            path = path.resolve()
        if not path.exists() or not path.is_file():
            continue
        try:
            rel = path.relative_to(charts_root).as_posix()
        except ValueError:
            # 仅允许 charts 目录下文件
            continue
        if rel in seen:
            continue
        seen.add(rel)
        name = path.name
        out.append(
            {
                "name": name,
                "path": rel,
                "note": viz_notes.get(name.lower()) or viz_notes.get(str(i)) or "",
                "url": f"/api/v1/iterative-experiments/charts/{rel}",
            }
        )
    return out


def _normalize_iteration(it: Dict[str, Any]) -> Dict[str, Any]:
    result = it.get("result") if isinstance(it.get("result"), dict) else {}
    analysis = it.get("analysis") if isinstance(it.get("analysis"), dict) else {}
    decision = it.get("decision") if isinstance(it.get("decision"), dict) else {}
    plan = it.get("plan") if isinstance(it.get("plan"), dict) else {}
    metrics = it.get("metrics") if isinstance(it.get("metrics"), dict) else {}
    if not metrics and isinstance(result.get("metrics"), dict):
        metrics = result["metrics"]

    charts = _extract_chart_entries(result, analysis)

    cont = decision.get("continue")
    if cont is None:
        cont = decision.get("should_continue")
    if cont is None:
        cont = True
    status = (it.get("status") or "success").lower()
    if status in {"ok", "completed", "success"}:
        status = "success"
    elif status not in {"success", "failed", "partial"}:
        status = "failed" if it.get("error_message") else "partial"

    viz_notes = []
    for note in analysis.get("visualization_notes") or []:
        if isinstance(note, dict):
            viz_notes.append(
                {
                    "chart_name": note.get("chart_name") or "",
                    "description": note.get("description") or "",
                }
            )
        elif note:
            viz_notes.append({"chart_name": "", "description": str(note)})

    raw_output = result.get("raw_output") if isinstance(result.get("raw_output"), dict) else {}
    script_log = raw_output.get("script_log") or ""

    return {
        "iteration_number": int(it.get("iteration_number") or 0),
        "status": status,
        "plan": {
            "title": plan.get("title") or "迭代方案",
            "description": plan.get("description") or "",
            "methodology": plan.get("methodology") or "",
            "success_criteria": plan.get("success_criteria") or [],
        },
        "result": {
            "metrics": metrics,
            "charts": charts,
            "summary": result.get("summary") or analysis.get("summary") or "",
            "script_log": script_log if isinstance(script_log, str) else "",
        },
        "analysis": {
            "overall_assessment": analysis.get("overall_assessment") or "",
            "summary": analysis.get("summary") or "",
            "findings": list(analysis.get("findings") or []),
            "identified_issues": list(analysis.get("identified_issues") or []),
            "strengths": list(analysis.get("strengths") or []),
            "suggested_adjustments": list(analysis.get("suggested_adjustments") or []),
            "visualization_notes": viz_notes,
            "weaknesses": list(analysis.get("weaknesses") or []),
            "confidence_level": analysis.get("confidence_level"),
        },
        "decision": {
            "continue": bool(cont),
            "should_continue": bool(cont),
            "reason": decision.get("reason") or decision.get("rationale") or "",
            "expected_improvement": decision.get("expected_improvement") or "",
            "focus_areas": list(decision.get("focus_areas") or []),
            "next_plan_adjustments": list(decision.get("next_plan_adjustments") or []),
        },
        "metrics": metrics,
        "duration_seconds": float(it.get("duration_seconds") or 0),
        "error_message": it.get("error_message") or "",
        "created_at": str(it.get("created_at") or ""),
    }


def project_experiment(project_id: str, experiment_id: str) -> Dict[str, Any]:
    """从 shaxiang SQLite 投影为 AISci 前端/Pipeline 使用的 experiment dict。"""

    def _inner() -> Dict[str, Any]:
        svc = get_service()
        bundle = svc.get_experiment_with_iterations(experiment_id)
        if not bundle:
            raise ShaxiangBridgeError(f"shaxiang 实验不存在: {experiment_id}")
        exp = bundle.get("experiment") or {}
        if hasattr(exp, "model_dump"):
            exp = exp.model_dump()
        status = exp.get("status") or "created"
        if hasattr(status, "value"):
            status = status.value
        plan = exp.get("initial_plan")
        if plan and not isinstance(plan, dict):
            plan = _dump_plan(plan)
        elif isinstance(plan, dict) and "analysis_script" not in plan and plan.get("title"):
            plan = _dump_plan(plan)

        data_config = exp.get("data_config") or exp.get("current_data_config")
        iterations = [
            _normalize_iteration(it)
            for it in (bundle.get("iterations") or [])
            if isinstance(it, dict)
        ]

        return {
            "id": exp.get("id") or experiment_id,
            "project_id": project_id,
            "shaxiang_experiment_id": exp.get("id") or experiment_id,
            "title": exp.get("title") or "",
            "research_goal": exp.get("research_goal") or "",
            "hypothesis": exp.get("hypothesis") or "",
            "constraints": list(exp.get("constraints") or []),
            "executor_type": exp.get("executor_type") or "sandbox",
            "max_iterations": int(exp.get("max_iterations") or 10),
            "current_iteration": int(exp.get("current_iteration") or 0),
            "phase": exp.get("phase") or "created",
            "status": str(status),
            "run_mode": exp.get("run_mode") or "smoke_only",
            "quality_mode": exp.get("quality_mode") or "draft",
            "dataset_recommendations": _normalize_recs(exp.get("dataset_recommendations")),
            "data_config": data_config if isinstance(data_config, dict) else None,
            "initial_plan": plan if isinstance(plan, dict) else _dump_plan(plan),
            "human_feedback": exp.get("human_feedback"),
            "feedback_status": exp.get("feedback_status") or "none",
            "iterations": iterations,
            "created_at": exp.get("created_at") or "",
            "updated_at": exp.get("updated_at") or "",
            "provider": "shaxiang",
        }

    return _run_in_shaxiang(_inner)


def create_experiment(
    project_id: str,
    *,
    hypothesis: str,
    research_goal: str = "",
    constraints: Optional[List[str]] = None,
    executor_type: str = "sandbox",
    max_iterations: int = 10,
    skip_dataset_recommend: bool = False,
) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        from storage.sqlite_store import SQLiteRepository

        hyp = (hypothesis or "").strip()
        goal = (research_goal or hyp).strip()
        sx = svc.create_experiment(
            title=hyp[:30] + ("…" if len(hyp) > 30 else ""),
            research_goal=goal,
            constraints=list(constraints or []),
            executor_type=executor_type or "sandbox",
            max_iterations=max(1, min(20, int(max_iterations or 10))),
        )
        sx.hypothesis = hyp
        repo = SQLiteRepository(svc.config.storage.db_path)

        if (executor_type or "sandbox") == "sandbox":
            if skip_dataset_recommend:
                # 已有数据：不调用推荐，直接进入可绑定数据阶段
                sx.dataset_recommendations = []
                sx.phase = "data_recommended"
                repo.update_experiment(sx)
            else:
                repo.update_experiment(sx)
                svc.recommend_datasets(sx.id)
        else:
            repo.update_experiment(sx)
            svc.start_experiment(sx.id)
        return project_experiment(project_id, sx.id)

    return _run_in_shaxiang(_inner)


def recommend_datasets(
    project_id: str, experiment_id: str, human_feedback: Optional[str] = None
) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.recommend_datasets(experiment_id, human_feedback=human_feedback or None)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def verify_data_config(data_config: Dict[str, Any], sample_size: int = 5000) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        import json

        svc = get_service()
        out = svc.verify_data_config(data_config, sample_size=sample_size)
        # 若自适应回退了 Profile，同步写回 data_config 字段，供调用方直接落库
        if isinstance(out, dict) and isinstance(out.get("recovered_profile"), dict):
            out = {
                **out,
                "data_config": {
                    **dict(data_config or {}),
                    "profile_name": "AutoDetect",
                    "profile_json": json.dumps(out["recovered_profile"], ensure_ascii=False),
                },
            }
        return out

    return _run_in_shaxiang(_inner)


def auto_detect_profile(directory_path: str, hypothesis_hint: str = "") -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        profile = svc.auto_detect_profile(directory_path, hypothesis_hint=hypothesis_hint or "")
        if hasattr(profile, "to_dict"):
            return profile.to_dict()
        if hasattr(profile, "model_dump"):
            return profile.model_dump()
        if isinstance(profile, dict):
            return profile
        return {}

    return _run_in_shaxiang(_inner)


def _normalize_directory_path(directory_path: str) -> str:
    raw = (directory_path or "").strip().strip('"').strip("'").strip()
    return str(Path(raw).expanduser()) if raw else ""


def auto_detect_and_verify(
    directory_path: str,
    hypothesis_hint: str = "",
    sample_size: int = 5000,
) -> Dict[str, Any]:
    """目录 AutoDetect：启发式 Profile 优先，LLM 仅作补充；返回可落库的 data_config。"""
    import json

    path = _normalize_directory_path(directory_path)
    if not path or not Path(path).is_dir():
        raise ValueError(f"目录不存在: {directory_path}")

    def _inner() -> Dict[str, Any]:
        from pathlib import Path as _Path

        svc = get_service()
        root = _Path(path)
        has_csv = any(root.rglob("*.csv"))
        has_tsv = any(root.rglob("*.tsv"))
        has_txt = any(p for p in root.rglob("*.txt") if "readme" not in p.name.lower())
        excludes = [
            r"(?i)^readme(\.|$)",
            r"(?i)\.md$",
            r"^\.DS_Store$",
            r"(?i)\.rdata$",
            r"(?i)^license(\.|$)",
        ]
        base = {
            "modality": "tabular",
            "comment_prefix": "",
            "exclude_patterns": excludes,
            "skip_rows": 0,
        }
        candidates: List[Dict[str, Any]] = []
        if has_csv:
            candidates.append({
                **base, "name": "Heuristic_csv", "scan_pattern": "**/*.csv",
                "file_extensions": [".csv"], "delimiter": ",", "has_header": True,
            })
            candidates.append({
                **base, "name": "Heuristic_csv_noheader", "scan_pattern": "**/*.csv",
                "file_extensions": [".csv"], "delimiter": ",", "has_header": False,
            })
        if has_tsv:
            candidates.append({
                **base, "name": "Heuristic_tsv", "scan_pattern": "**/*.tsv",
                "file_extensions": [".tsv"], "delimiter": "\t", "has_header": True,
            })
        if has_txt:
            candidates.append({
                **base, "name": "Heuristic_txt_space", "scan_pattern": "**/*.txt",
                "file_extensions": [".txt"], "delimiter": r"\s+", "has_header": True,
            })
        table_exts = [x for x, ok in ((".csv", has_csv), (".tsv", has_tsv), (".txt", has_txt)) if ok]
        if table_exts:
            candidates.append({
                **base, "name": "Heuristic_tables", "scan_pattern": "**/*",
                "file_extensions": table_exts, "delimiter": ",", "has_header": True,
            })

        # 启发式已能出数值列时跳过 LLM，避免误判拖垮整条链路
        errors: List[str] = []
        best: Optional[tuple] = None

        def _try_profile(profile_dict: Dict[str, Any]) -> None:
            nonlocal best
            verify_cfg = {
                "source_type": "directory",
                "source_path": path,
                "profile_json": json.dumps(profile_dict, ensure_ascii=False),
                "preprocessing_steps": [],
                "sample_size": sample_size,
                "profile_name": "AutoDetect",
            }
            try:
                preview = svc.verify_data_config(verify_cfg, sample_size=sample_size)
            except Exception as exc:
                errors.append(f"{profile_dict.get('name') or 'profile'}: {exc}")
                return
            recovered = preview.get("recovered_profile") if isinstance(preview, dict) else None
            use_profile = recovered if isinstance(recovered, dict) and recovered else profile_dict
            if isinstance(recovered, dict) and recovered:
                verify_cfg = {
                    **verify_cfg,
                    "profile_json": json.dumps(use_profile, ensure_ascii=False),
                }
            n_num = len((preview or {}).get("numeric_columns") or [])
            media_ok = bool((preview or {}).get("media_path_column"))
            if n_num <= 0 and not media_ok:
                errors.append(f"{use_profile.get('name')}: 无数值列")
                return
            score = (
                n_num,
                int((preview or {}).get("row_count") or 0),
                int((preview or {}).get("column_count") or 0),
            )
            if best is None or score > best[0]:
                best = (score, use_profile, preview, verify_cfg)

        for cand in candidates:
            _try_profile(cand)
            if best is not None and best[0][0] > 0:
                break

        if best is None:
            try:
                llm_profile = svc.auto_detect_profile(path, hypothesis_hint=hypothesis_hint or "")
                if hasattr(llm_profile, "to_dict"):
                    llm_profile = llm_profile.to_dict()
                elif hasattr(llm_profile, "model_dump"):
                    llm_profile = llm_profile.model_dump()
                if isinstance(llm_profile, dict) and llm_profile:
                    _try_profile(llm_profile)
            except Exception as exc:
                errors.append(f"LLM识别: {exc}")
                logger.warning("AutoDetect LLM 失败: %s", exc)

        if best is None:
            detail = "；".join(errors[-5:]) if errors else "未知原因"
            raise ValueError(
                "试加载后没有可用数值列，无法可靠设计分析脚本。"
                f"已尝试启发式/LLM 识别仍失败。{detail}"
            )

        _, profile_dict, preview, verify_cfg = best
        data_config = {
            **verify_cfg,
            "row_count": preview.get("row_count"),
            "columns": preview.get("columns") or [],
        }
        return {
            "profile": profile_dict,
            "preview": preview,
            "data_config": data_config,
        }

    return _run_in_shaxiang(_inner)


def apply_analysis_script(
    project_id: str,
    experiment_id: str,
    script_content: str,
    *,
    title: Optional[str] = None,
    methodology: Optional[str] = None,
) -> Dict[str, Any]:
    """将参考脚本直接写入 initial_plan.analysis_script（不跑 LLM 设计）。"""

    def _inner() -> Dict[str, Any]:
        from schemas.experiment import ExperimentPlan, Hypothesis

        svc = get_service()
        experiment = svc.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        content = (script_content or "").strip()
        if len(content) < 40:
            raise ValueError("脚本内容过短")

        plan = experiment.initial_plan
        if plan is None:
            plan = ExperimentPlan(
                title=title or "FL Starter Pack 参考脚本",
                description="由 FL Starter Pack 模板注入",
                hypothesis=Hypothesis(
                    statement=experiment.hypothesis or "FL pilot",
                    rationale="starter pack template",
                    expected_outcome="metrics.json",
                ),
                methodology=methodology or "local FL pilot template",
                analysis_script=content,
                parameters={"script": content},
                success_criteria=["写出 metrics.json"],
            )
        else:
            if hasattr(plan, "model_copy"):
                plan = plan.model_copy(deep=True)
            plan.analysis_script = content
            params = dict(getattr(plan, "parameters", None) or {})
            params["script"] = content
            plan.parameters = params
            if title:
                plan.title = title
            if methodology:
                plan.methodology = methodology
        experiment.initial_plan = plan
        if experiment.phase in {"created", "data_recommended", "data_uploaded", "hypothesis_submitted"}:
            experiment.phase = "script_designed"
        svc.repository.update_experiment(experiment)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def design_script(
    project_id: str,
    experiment_id: str,
    data_config: Dict[str, Any],
    human_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        import json

        svc = get_service()
        cfg = dict(data_config or {})
        preview = svc.verify_data_config(cfg)
        recovered = preview.get("recovered_profile") if isinstance(preview, dict) else None
        if isinstance(recovered, dict) and recovered:
            cfg = {
                **cfg,
                "profile_name": "AutoDetect",
                "profile_json": json.dumps(recovered, ensure_ascii=False),
            }
            # 写回实验，避免下次仍用失败 Profile
            try:
                exp = svc.repository.get_experiment(experiment_id)
                if exp is not None:
                    exp.data_config = {
                        **(exp.data_config or {}),
                        **cfg,
                        "row_count": preview.get("row_count"),
                        "columns": preview.get("columns") or [],
                    }
                    svc.repository.update_experiment(exp)
            except Exception as exc:
                logger.warning("写回 recovered profile 失败: %s", exc)
        svc.design_script(experiment_id, cfg, human_feedback=human_feedback)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def redesign_script(
    project_id: str, experiment_id: str, feedback: Optional[str] = None
) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.redesign_script_from_feedback(experiment_id, feedback=feedback)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def set_run_mode(project_id: str, experiment_id: str, run_mode: str) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.set_run_mode(experiment_id, run_mode)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def set_quality_mode(project_id: str, experiment_id: str, quality_mode: str) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.set_quality_mode(experiment_id, quality_mode)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def submit_feedback(project_id: str, experiment_id: str, feedback: str) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.submit_feedback(experiment_id, feedback)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def run_iteration(project_id: str, experiment_id: str) -> Dict[str, Any]:
    """执行一轮；返回 {record, experiment}。"""

    def _inner() -> Dict[str, Any]:
        svc = get_service()
        record = svc.run_iteration(experiment_id)
        if hasattr(record, "__dict__") and not isinstance(record, dict):
            raw = {
                "iteration_number": getattr(record, "iteration_number", 0),
                "plan": getattr(record, "plan", None) or {},
                "result": getattr(record, "result", None) or {},
                "analysis": getattr(record, "analysis", None) or {},
                "decision": getattr(record, "decision", None) or {},
                "metrics": getattr(record, "metrics", None) or {},
                "status": getattr(record, "status", "success"),
                "error_message": getattr(record, "error_message", "") or "",
                "duration_seconds": float(getattr(record, "duration_seconds", 0) or 0),
                "created_at": str(getattr(record, "created_at", "") or ""),
            }
        else:
            raw = dict(record) if isinstance(record, dict) else {}
        exp = project_experiment(project_id, experiment_id)
        return {"record": _normalize_iteration(raw), "experiment": exp}

    return _run_in_shaxiang(_inner)


def run_to_completion(project_id: str, experiment_id: str) -> Dict[str, Any]:
    def _inner() -> Dict[str, Any]:
        svc = get_service()
        svc.run_full_experiment(experiment_id)
        return project_experiment(project_id, experiment_id)

    return _run_in_shaxiang(_inner)


def delete_experiment(experiment_id: str) -> None:
    def _inner() -> None:
        svc = get_service()
        try:
            svc.delete_experiment(experiment_id)
        except Exception as exc:
            logger.warning("删除 shaxiang 实验失败 %s: %s", experiment_id, exc)

    _run_in_shaxiang(_inner)


# 兼容旧 import 名（调用方应改用上方强类型函数）
def try_recommend_datasets(*_a, **_k):
    raise ShaxiangBridgeError("请使用 recommend_datasets，不再支持静默 mock")


def try_design_script(*_a, **_k):
    raise ShaxiangBridgeError("请使用 design_script，不再支持静默 mock")


def try_run_iteration(*_a, **_k):
    raise ShaxiangBridgeError("请使用 run_iteration，不再支持静默 mock")
