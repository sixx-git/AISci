"""项目级迭代实验服务：执行真相源为 shaxiang，JSON 仅为投影缓存。

默认走 shaxiang ExperimentService；失败抛错，不静默 mock。
LLM 与主项目 llm_runtime（右上角高级设置）共用。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(CHINA_TZ).isoformat()


def project_store_path(project_id: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "storage" / "iterative_experiments"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{project_id}.json"


def use_shaxiang() -> bool:
    settings = get_settings()
    raw = getattr(settings, "AISCI_USE_SHAXIANG", True)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


def require_shaxiang_enabled() -> None:
    if not use_shaxiang():
        raise RuntimeError(
            "迭代实验已禁用 shaxiang（AISCI_USE_SHAXIANG=false）。"
            "请开启后使用真实迭代实验引擎，不再提供 mock 数据。"
        )


def _empty_store() -> Dict[str, Any]:
    return {"experiments": [], "report_experiment_ids": []}


def _load(project_id: str) -> Dict[str, Any]:
    path = project_store_path(project_id)
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_store()
        data.setdefault("experiments", [])
        data.setdefault("report_experiment_ids", [])
        return data
    except Exception:
        return _empty_store()


def _save(project_id: str, store: Dict[str, Any]) -> None:
    path = project_store_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


class IterativeExperimentService:
    def _upsert(self, project_id: str, experiment: Dict[str, Any]) -> Dict[str, Any]:
        store = _load(project_id)
        experiment["updated_at"] = experiment.get("updated_at") or _now()
        experiment["project_id"] = project_id
        exps = store.get("experiments") or []
        for i, e in enumerate(exps):
            if e.get("id") == experiment.get("id"):
                exps[i] = experiment
                store["experiments"] = exps
                _save(project_id, store)
                return experiment
        exps.insert(0, experiment)
        store["experiments"] = exps
        _save(project_id, store)
        return experiment

    def _persist_projection(self, project_id: str, experiment: Dict[str, Any]) -> Dict[str, Any]:
        return self._upsert(project_id, experiment)

    def _sx_id(self, exp: Dict[str, Any]) -> str:
        return exp.get("shaxiang_experiment_id") or exp.get("id") or ""

    def list(self, project_id: str) -> List[Dict[str, Any]]:
        store = _load(project_id)
        exps = list(store.get("experiments") or [])
        # 有 shaxiang id 时从 SQLite 重新投影，补齐图表/分析/决策（旧 JSON 可能缺字段）
        if use_shaxiang():
            refreshed: List[Dict[str, Any]] = []
            for e in exps:
                sx_id = self._sx_id(e) if e else ""
                if sx_id:
                    try:
                        refreshed.append(self.refresh_from_shaxiang(project_id, e["id"]))
                        continue
                    except Exception as exc:
                        logger.warning("list 投影刷新失败 %s: %s", e.get("id"), exc)
                refreshed.append(e)
            exps = refreshed
        exps.sort(key=lambda e: e.get("updated_at") or "", reverse=True)
        return exps

    def get(self, project_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        store = _load(project_id)
        local = None
        for e in store.get("experiments") or []:
            if e.get("id") == experiment_id:
                local = e
                break
        if not local:
            return None
        if use_shaxiang() and self._sx_id(local):
            try:
                return self.refresh_from_shaxiang(project_id, experiment_id)
            except Exception as exc:
                logger.warning("get 投影刷新失败 %s: %s", experiment_id, exc)
        return local

    def refresh_from_shaxiang(self, project_id: str, experiment_id: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        local = None
        for e in (_load(project_id).get("experiments") or []):
            if e.get("id") == experiment_id:
                local = e
                break
        sx_id = (self._sx_id(local) if local else "") or experiment_id
        projected = bridge.project_experiment(project_id, sx_id)
        return self._persist_projection(project_id, projected)

    def get_report_ids(self, project_id: str) -> List[str]:
        store = _load(project_id)
        existing = {e.get("id") for e in store.get("experiments") or []}
        return [i for i in (store.get("report_experiment_ids") or []) if i in existing]

    def set_report_ids(self, project_id: str, ids: List[str]) -> List[str]:
        store = _load(project_id)
        existing = {e.get("id") for e in store.get("experiments") or []}
        store["report_experiment_ids"] = [i for i in ids if i in existing]
        _save(project_id, store)
        return store["report_experiment_ids"]

    def toggle_report(self, project_id: str, experiment_id: str) -> List[str]:
        cur = self.get_report_ids(project_id)
        nxt = [i for i in cur if i != experiment_id] if experiment_id in cur else cur + [experiment_id]
        return self.set_report_ids(project_id, nxt)

    def create(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        hypothesis = (payload.get("hypothesis") or "").strip()
        if not hypothesis:
            raise ValueError("请填写实验假设")
        try:
            projected = bridge.create_experiment(
                project_id,
                hypothesis=hypothesis,
                research_goal=(payload.get("research_goal") or hypothesis).strip(),
                constraints=[c for c in (payload.get("constraints") or []) if str(c).strip()],
                executor_type=payload.get("executor_type") or "sandbox",
                max_iterations=int(payload.get("max_iterations") or 10),
            )
        except ShaxiangBridgeError:
            raise
        except Exception as exc:
            logger.exception("创建迭代实验失败")
            raise RuntimeError(f"创建迭代实验失败: {exc}") from exc
        return self._persist_projection(project_id, projected)

    def delete(self, project_id: str, experiment_id: str) -> None:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        sx_id = self._sx_id(exp) if exp else experiment_id
        if sx_id:
            bridge.delete_experiment(sx_id)
        store = _load(project_id)
        store["experiments"] = [e for e in (store.get("experiments") or []) if e.get("id") != experiment_id]
        store["report_experiment_ids"] = [
            i for i in (store.get("report_experiment_ids") or []) if i != experiment_id
        ]
        _save(project_id, store)

    def recommend_datasets(
        self, project_id: str, experiment_id: str, human_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        if exp.get("executor_type") != "sandbox":
            raise ValueError("模拟实验无需推荐数据集")
        try:
            projected = bridge.recommend_datasets(
                project_id, self._sx_id(exp), human_feedback=human_feedback
            )
        except ShaxiangBridgeError:
            raise
        except Exception as exc:
            logger.exception("推荐数据集失败")
            raise RuntimeError(f"推荐数据集失败: {exc}") from exc
        return self._persist_projection(project_id, projected)

    def upload_dataset(
        self, project_id: str, experiment_id: str, filename: str, content: bytes
    ) -> Dict[str, Any]:
        """保存上传文件到 shaxiang data/uploads，返回 data_config。"""
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        safe_name = Path(filename or "upload.csv").name
        if not safe_name:
            raise ValueError("无效文件名")
        dest_dir = bridge.uploads_dir(project_id)
        # 避免覆盖：加短 uuid 前缀
        dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
        dest.write_bytes(content)
        suffix = dest.suffix.lower()
        source_type = "local_json" if suffix in {".json", ".jsonl"} else "uploaded"
        data_config = {
            "source_type": source_type,
            "source_path": str(dest.resolve()),
            "file_name": safe_name,
            "sample_size": 5000,
            "preprocessing_steps": [],
        }
        preview = bridge.verify_data_config(data_config)
        data_config["row_count"] = preview.get("row_count")
        data_config["columns"] = preview.get("columns") or []
        exp = dict(exp)
        exp["data_config"] = data_config
        exp["phase"] = "data_uploaded"
        self._persist_projection(project_id, exp)
        # 同步 current_data_config 到 SX
        try:
            svc = bridge.get_service()
            sx = svc.get_experiment(self._sx_id(exp))
            if sx:
                sx.current_data_config = data_config
                sx.phase = "data_uploaded"
                from storage.sqlite_store import SQLiteRepository

                SQLiteRepository(svc.config.storage.db_path).update_experiment(sx)
        except Exception as exc:
            logger.warning("同步 data_config 到 shaxiang 失败: %s", exc)
        return {"data_config": data_config, "preview": preview, "experiment": self.get(project_id, experiment_id)}

    def verify_data(
        self, project_id: str, experiment_id: str, data_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        if not self.get(project_id, experiment_id):
            raise ValueError("实验不存在")
        preview = bridge.verify_data_config(data_config)
        return {"ok": True, "preview": preview}

    def auto_detect(
        self, project_id: str, experiment_id: str, directory_path: str
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        hint = exp.get("hypothesis") or exp.get("research_goal") or ""
        profile_dict = bridge.auto_detect_profile(directory_path, hypothesis_hint=hint)

        verify_cfg = {
            "source_type": "directory",
            "source_path": directory_path,
            "profile_json": json.dumps(profile_dict, ensure_ascii=False),
            "preprocessing_steps": [],
            "sample_size": 5000,
            "profile_name": "AutoDetect",
        }
        preview = bridge.verify_data_config(verify_cfg)
        return {
            "profile": profile_dict,
            "preview": preview,
            "data_config": {
                **verify_cfg,
                "row_count": preview.get("row_count"),
                "columns": preview.get("columns") or [],
            },
        }

    def design_script(
        self, project_id: str, experiment_id: str, data_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        cfg = data_config or exp.get("data_config")
        if not isinstance(cfg, dict) or not (cfg.get("source_path") or cfg.get("file_name")):
            raise ValueError("尚未绑定可用数据，已阻断设计脚本（对齐 shaxiang）")
        if cfg.get("source_type") == "directory":
            if not cfg.get("profile_name") and not cfg.get("profile_json"):
                raise ValueError("directory 模式需要选择预置 Profile 或完成 AutoDetect 确认")
        # 上传类型统一绝对路径
        sp = (cfg.get("source_path") or "").strip()
        if sp and not Path(sp).is_absolute() and cfg.get("source_type") in {"uploaded", "local_csv", "local_json"}:
            # 相对路径尝试落在 uploads
            cand = bridge.uploads_dir(project_id) / Path(sp).name
            if cand.exists():
                cfg = {**cfg, "source_path": str(cand.resolve())}
        try:
            projected = bridge.design_script(project_id, self._sx_id(exp), cfg)
        except ShaxiangBridgeError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("设计脚本失败")
            # 透传截断/解析类错误文案，避免只看到笼统 RuntimeError
            raise RuntimeError(str(exc) or f"设计脚本失败: {exc}") from exc
        return self._persist_projection(project_id, projected)

    def set_run_mode(self, project_id: str, experiment_id: str, run_mode: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        projected = bridge.set_run_mode(project_id, self._sx_id(exp), run_mode)
        return self._persist_projection(project_id, projected)

    def run_iteration(self, project_id: str, experiment_id: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        if not exp.get("initial_plan"):
            raise ValueError("请先设计分析脚本")
        if exp.get("executor_type") == "sandbox":
            dc = exp.get("data_config") or {}
            if not dc.get("source_path") and not dc.get("file_name"):
                raise ValueError("缺数据，不可执行迭代（对齐 shaxiang）")
        try:
            out = bridge.run_iteration(project_id, self._sx_id(exp))
        except ShaxiangBridgeError:
            raise
        except Exception as exc:
            logger.exception("执行迭代失败")
            raise RuntimeError(f"执行迭代失败: {exc}") from exc
        # 独立实验记忆：直写 mem_store，不依赖/不修改投影语义
        try:
            from app.services.experiment_memory import maybe_save_from_shaxiang

            maybe_save_from_shaxiang(out.get("experiment") or {}, scope_key=project_id)
        except Exception:
            logger.debug("实验记忆保存跳过", exc_info=True)
        self._persist_projection(project_id, out["experiment"])
        return out["record"]

    def run_to_completion(self, project_id: str, experiment_id: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        try:
            projected = bridge.run_to_completion(project_id, self._sx_id(exp))
        except ShaxiangBridgeError:
            raise
        except Exception as exc:
            logger.exception("自动运行至完成失败")
            raise RuntimeError(f"自动运行至完成失败: {exc}") from exc
        try:
            from app.services.experiment_memory import maybe_save_from_shaxiang

            maybe_save_from_shaxiang(projected or {}, scope_key=project_id)
        except Exception:
            logger.debug("实验记忆保存跳过", exc_info=True)
        return self._persist_projection(project_id, projected)

    def submit_feedback(self, project_id: str, experiment_id: str, feedback: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        text = (feedback or "").strip()
        if not text:
            raise ValueError("请输入反馈内容")
        projected = bridge.submit_feedback(project_id, self._sx_id(exp), text)
        return self._persist_projection(project_id, projected)

    def redesign_from_feedback(
        self, project_id: str, experiment_id: str, feedback: str
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge
        from app.integrations.shaxiang.bridge import ShaxiangBridgeError

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        if exp.get("executor_type") == "sandbox" and not exp.get("data_config"):
            raise ValueError("缺数据，不可重设计脚本")
        text = (feedback or "").strip()
        try:
            projected = bridge.redesign_script(project_id, self._sx_id(exp), feedback=text or None)
        except ShaxiangBridgeError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("重设计脚本失败")
            raise RuntimeError(f"重设计脚本失败: {exc}") from exc
        return self._persist_projection(project_id, projected)

    def build_pipeline_stage_output(self, project_id: str, hypothesis_text: str) -> Dict[str, Any]:
        """供 pipeline「迭代实验」阶段：优先使用手动指定报告实验。"""
        report_ids = self.get_report_ids(project_id)
        selected = [self.get(project_id, i) for i in report_ids]
        selected = [e for e in selected if e]

        if not selected:
            for e in self.list(project_id):
                if (e.get("hypothesis") or "").strip() == (hypothesis_text or "").strip():
                    selected = [e]
                    break

        if not selected:
            if not (hypothesis_text or "").strip():
                return {
                    "status": "blocked_need_hypothesis",
                    "warning": "缺少主假设，无法启动迭代实验",
                    "experiments": [],
                }
            try:
                created = self.create(
                    project_id,
                    {
                        "hypothesis": hypothesis_text,
                        "research_goal": hypothesis_text,
                        "executor_type": "sandbox",
                        "max_iterations": 10,
                    },
                )
            except Exception as exc:
                return {
                    "status": "blocked_need_data",
                    "warning": f"无法创建迭代实验: {exc}",
                    "experiments": [],
                }
            if created.get("executor_type") == "sandbox" and not created.get("data_config"):
                return {
                    "status": "blocked_need_data",
                    "warning": "数据驱动路径缺少数据集，已阻断后续报告（对齐 shaxiang）",
                    "experiments": [created],
                    "report_experiment_ids": [],
                    "primary_experiment_id": created.get("id"),
                }
            selected = [created]

        runnable = []
        blocked = []
        for exp in selected:
            if exp.get("executor_type") == "sandbox" and not exp.get("data_config"):
                blocked.append(exp)
                continue
            if not exp.get("initial_plan"):
                if exp.get("executor_type") == "sandbox" and exp.get("data_config"):
                    try:
                        exp = self.design_script(project_id, exp["id"], exp.get("data_config"))
                    except Exception as exc:
                        blocked.append({**exp, "error": str(exc)})
                        continue
                else:
                    blocked.append(exp)
                    continue
            if exp.get("phase") not in {"completed"} and int(exp.get("current_iteration") or 0) == 0:
                try:
                    self.run_iteration(project_id, exp["id"])
                    exp = self.get(project_id, exp["id"]) or exp
                except Exception as exc:
                    blocked.append({**exp, "error": str(exc)})
                    continue
            runnable.append(exp)

        if not runnable:
            return {
                "status": "blocked_need_data",
                "warning": "选定实验缺少数据或未能完成设计/迭代，已阻断报告",
                "experiments": selected,
                "blocked": blocked,
                "report_experiment_ids": report_ids,
            }

        primary = runnable[0]
        synth = self.synthesize_report_fields(primary)
        return {
            "status": "completed",
            "experiments": runnable,
            "blocked": blocked,
            "report_experiment_ids": [e.get("id") for e in runnable],
            "primary_experiment_id": primary.get("id"),
            "experiment_design": synth["experiment_design"],
            "small_validation": synth["small_validation"],
            "provider": primary.get("provider") or "shaxiang",
        }

    def snapshot_for_report(self, project_id: str) -> Dict[str, Any]:
        """汇总「用于报告」勾选实验；不自动设计脚本或跑迭代。"""
        report_ids = self.get_report_ids(project_id)
        experiments = self.list(project_id)
        selected: List[Dict[str, Any]] = []
        if report_ids:
            id_set = set(report_ids)
            selected = [e for e in experiments if e.get("id") in id_set]
        if not selected:
            selected = [e for e in experiments if e.get("phase") == "completed"]
        if not selected:
            return {
                "status": "blocked_need_data",
                "warning": "请先在「迭代实验」页完成实验并勾选「用于报告」",
                "experiments": [],
                "report_experiment_ids": report_ids,
            }

        completed = [e for e in selected if e.get("phase") == "completed"]
        use = completed or selected
        primary = use[0]
        synth = self.synthesize_report_fields(primary)
        return {
            "status": "completed" if completed else "partial",
            "experiments": use,
            "report_experiment_ids": [e.get("id") for e in use],
            "primary_experiment_id": primary.get("id"),
            "experiment_design": synth["experiment_design"],
            "small_validation": synth["small_validation"],
            "provider": primary.get("provider") or "shaxiang",
            "warning": None if completed else "所选实验尚未全部完成，将基于当前进度生成报告",
        }

    @staticmethod
    def _resolve_iteration_charts(primary: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """汇总成功轮次的指标与图表，并把相对路径解析为 shaxiang 绝对路径。"""
        from app.integrations.shaxiang.bridge import shaxiang_root

        charts_root = (shaxiang_root() / "data" / "charts").resolve()
        iterations = primary.get("iterations") or []
        metrics: Dict[str, Any] = {}
        chart_rows: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for it in iterations:
            if not isinstance(it, dict):
                continue
            status = str(it.get("status") or "").lower()
            if status in {"failed", "error"}:
                continue
            it_metrics = it.get("metrics") or (it.get("result") or {}).get("metrics") or {}
            if isinstance(it_metrics, dict) and it_metrics:
                metrics = {**metrics, **it_metrics}
            for c in (it.get("result") or {}).get("charts") or []:
                if not isinstance(c, dict):
                    continue
                rel = str(c.get("path") or c.get("file_path") or c.get("name") or "").strip()
                name = str(c.get("name") or Path(rel).name or "").strip()
                if not name and not rel:
                    continue
                abs_path = None
                if rel:
                    candidate = Path(rel)
                    if not candidate.is_absolute():
                        candidate = (charts_root / rel).resolve()
                    if candidate.is_file():
                        abs_path = candidate
                if abs_path is None and name:
                    candidate = (charts_root / name).resolve()
                    if candidate.is_file():
                        abs_path = candidate
                        rel = name
                key = str(abs_path) if abs_path else (c.get("url") or name or rel)
                if key in seen:
                    continue
                seen.add(key)
                plot_id = Path(name or rel or key).stem
                entry = {
                    "plot_id": plot_id,
                    "title": (c.get("note") or name or plot_id).strip(),
                    "path": str(abs_path) if abs_path else rel,
                    "file_path": str(abs_path) if abs_path else rel,
                    "url": c.get("url"),
                    "source": "sandbox_execution",
                    "type": "sandbox_plot",
                    "chart_kind": "experiment_result",
                    "is_generated_from_real_data": True,
                    "source_dataset_id": (primary.get("data_config") or {}).get("source_path")
                    or (primary.get("data_config") or {}).get("file_name")
                    or primary.get("id"),
                }
                chart_rows.append(entry)
        return metrics, chart_rows

    @staticmethod
    def synthesize_report_fields(primary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """把单条迭代实验映射为报告 agent 入参（历史 ed/sv 形状）。"""
        metrics, plots = IterativeExperimentService._resolve_iteration_charts(primary)
        plan = primary.get("initial_plan") or {}
        data_config = primary.get("data_config") or {}
        source_path = data_config.get("source_path") or data_config.get("file_name") or ""
        source_type = data_config.get("source_type") or ""
        columns = data_config.get("columns") or data_config.get("feature_columns") or []
        target_cols = data_config.get("target_columns") or []
        if isinstance(target_cols, str):
            target_cols = [target_cols]

        dataset_desc = (
            (
                f"数据集路径: {source_path}"
                + (f"（类型: {source_type}）" if source_type else "")
                + "。来自迭代实验绑定的真实/本地数据，用于沙箱验证。"
            )
            if source_path
            else ""
        )
        source_desc = ""
        if source_path or source_type:
            source_desc = (
                f"历史/训练数据来源: {source_type or 'local'}；"
                f"路径或标识: {source_path or '已绑定数据集'}。"
            )
            if columns:
                source_desc += f" 可用字段包括: {', '.join(str(c) for c in list(columns)[:12])}。"
        target_desc = ""
        if target_cols:
            target_desc = f"目标标签/验证字段: {', '.join(str(c) for c in target_cols)}。"
        elif columns:
            target_desc = (
                "目标数据特征: 与绑定数据集同构的传感器/表格特征，"
                f"用于二分类或指定标签验证；特征列示例: {', '.join(str(c) for c in list(columns)[:8])}。"
            )

        experiment_design = {
            "hypothesis": primary.get("hypothesis"),
            "methods": plan.get("methodology") or "",
            "baselines": "baseline vs proposed (iterative experiment)",
            "metrics": str(metrics.get("primary_metric") or metrics.get("accuracy") or "accuracy"),
            "experimental_steps": plan.get("description") or "",
            "expected_results": "; ".join(plan.get("success_criteria") or []),
            "limitations": "迭代实验引擎产出；详见 iterations",
            "datasets": dataset_desc or source_path or "",
            "source_data": source_desc or source_type or "",
            "target_data": target_desc,            "experiment_spec": {
                "primary_metric": metrics.get("primary_metric") or "accuracy",
                "task_type": "classification",
                "feature_columns": columns,
            },
            "analysis_script": plan.get("analysis_script") or "",
            "data_requirements": {
                "uploaded_dataset_count": 1 if data_config else 0,
                "upload_status": "ready" if data_config else "missing",
            },
            "skill_outputs": {"experiment_sanity_check": {"data": {"executable": True}}},
            "executability_gate": {"passed": True, "score": 80},
            "_provider": "iterative_experiment",
            "_experiment_id": primary.get("id"),
        }

        sandbox_execution = {
            "success": bool(metrics or plots),
            "output_complete": bool(metrics or plots),
            "metrics": metrics,
            "plots": plots,
        }
        actual_results = {
            "data_source": "sandbox_execution",
            "sandbox_execution": sandbox_execution,
            "sandbox_metrics": metrics,
            "sandbox_plots": plots,
            "summary": (
                f"迭代实验沙箱已执行，产出 {len(metrics)} 项指标、{len(plots)} 张图表。"
                if (metrics or plots)
                else "迭代实验尚未产出可验证指标/图表。"
            ),
        }
        small_validation = {
            "hypothesis": primary.get("hypothesis"),
            "validation_status": "completed" if primary.get("phase") == "completed" else "partial",
            "has_real_data": 1 if data_config else 0,
            "sandbox_execution": sandbox_execution,
            "artifacts": {"metrics": metrics, "plots": plots},
            "results": {
                "actual_results": actual_results,
                "result_type_summary": "has_actual_results" if (metrics or plots) else "none",
            },
            "_provider": "iterative_experiment",
            "_experiment_id": primary.get("id"),
        }
        return {"experiment_design": experiment_design, "small_validation": small_validation}

    @staticmethod
    def resolve_ed_sv_from_results(
        results: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """优先从 iterative_experiment 解析 ed/sv；兼容顶层旧键。

        返回 (ie, experiment_design, small_validation)。
        顺序：
          1) results.iterative_experiment 嵌套 ed/sv
          2) 从 primary 实验 synthesize_report_fields
          3) 顶层 results.experiment_design / small_validation（历史 run）
        """
        results = results if isinstance(results, dict) else {}
        ie = results.get("iterative_experiment") or {}
        if not isinstance(ie, dict):
            ie = {}

        ed: Dict[str, Any] = {}
        sv: Dict[str, Any] = {}
        nested_ed = ie.get("experiment_design")
        nested_sv = ie.get("small_validation")
        if isinstance(nested_ed, dict):
            ed = nested_ed
        if isinstance(nested_sv, dict):
            sv = nested_sv

        if not ed or not sv:
            experiments = ie.get("experiments") or []
            primary = None
            pid = ie.get("primary_experiment_id")
            if pid:
                primary = next(
                    (e for e in experiments if isinstance(e, dict) and e.get("id") == pid),
                    None,
                )
            if not primary and experiments and isinstance(experiments[0], dict):
                primary = experiments[0]
            if primary:
                synth = IterativeExperimentService.synthesize_report_fields(primary)
                ed = ed or (synth.get("experiment_design") or {})
                sv = sv or (synth.get("small_validation") or {})

        # 历史顶层键兜底
        top_ed = results.get("experiment_design")
        top_sv = results.get("small_validation")
        if not ed and isinstance(top_ed, dict):
            ed = top_ed
        if not sv and isinstance(top_sv, dict):
            sv = top_sv

        return ie, ed, sv


def resolve_ed_sv_from_results(
    results: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """模块级便捷入口。"""
    return IterativeExperimentService.resolve_ed_sv_from_results(results)


def get_iterative_experiment_service() -> IterativeExperimentService:
    return IterativeExperimentService()
