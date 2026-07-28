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


def _resolve_project_fl_gate(project_id: str) -> Tuple[bool, str, Optional[str]]:
    """返回 (is_federated_learning, fl_setting, profile_id)。

    通用项目一律 is_fl=False，避免 FL Pack 文案/模板泄漏进 general 模式。
    """
    from app.core.database import SessionLocal, init_db
    from app.core.project_modes import is_federated_learning_mode
    from app.models.project import Project
    from app.services.fl_pack_service import FlPackService

    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if not proj:
            return False, "both", None
        if not is_federated_learning_mode(getattr(proj, "project_mode", None)):
            return False, "both", None
        setting = "both"
        profile_id = None
        if isinstance(proj.config, dict):
            setting = FlPackService.get_fl_setting_from_config(proj.config)
            profile_id = FlPackService.get_experiment_profile_id_from_config(proj.config)
        return True, setting, profile_id
    finally:
        db.close()


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
        from app.integrations.shaxiang.bridge import rehydrate_experiment_charts

        hydrated = rehydrate_experiment_charts(local)
        if hydrated is not local:
            self._upsert(project_id, hydrated)
        return hydrated

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
        from app.integrations.shaxiang.bridge import rehydrate_experiment_charts

        projected = rehydrate_experiment_charts(projected)
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
                skip_dataset_recommend=bool(payload.get("skip_dataset_recommend")),
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
        feedback = human_feedback or ""
        try:
            from app.services.fl_pack_service import fl_pack_enabled, get_fl_pack_service

            is_fl, setting, profile_id = _resolve_project_fl_gate(project_id)
            if fl_pack_enabled() and is_fl:
                svc = get_fl_pack_service()
                ctx = svc.scripts_context_for_llm(
                    fl_setting=setting, profile_id=profile_id
                )
                pack_hints = svc.dataset_guidance_hints(fl_setting=setting)[:5]
                hint_lines = [
                    f"- {h.get('name')}: {h.get('download_url')} ({h.get('description', '')[:80]})"
                    for h in pack_hints
                ]
                extra = ctx
                if hint_lines:
                    extra += "\n[FL Pack 数据集]\n" + "\n".join(hint_lines)
                feedback = (feedback + "\n" + extra).strip() if feedback else extra
        except Exception:
            pass
        try:
            projected = bridge.recommend_datasets(
                project_id, self._sx_id(exp), human_feedback=feedback or None
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

    @staticmethod
    def _heuristic_directory_profiles(directory_path: str) -> List[Dict[str, Any]]:
        """不依赖 LLM 的表格 Profile 候选（目录内有什么扩展名就试什么）。"""
        root = Path(directory_path)
        if not root.is_dir():
            return []
        has_csv = any(root.rglob("*.csv"))
        has_tsv = any(root.rglob("*.tsv"))
        has_txt = any(p for p in root.rglob("*.txt") if "readme" not in p.name.lower())
        excludes = [
            r"(?i)^readme(\.|$)",
            r"(?i)\.md$",
            r"^\.DS_Store$",
            r"(?i)\.rdata$",
        ]
        base = {
            "modality": "tabular",
            "comment_prefix": "",
            "exclude_patterns": excludes,
        }
        out: List[Dict[str, Any]] = []
        if has_csv:
            out.append({
                **base,
                "name": "Heuristic_csv",
                "scan_pattern": "**/*.csv",
                "file_extensions": [".csv"],
                "delimiter": ",",
                "has_header": True,
            })
            out.append({
                **base,
                "name": "Heuristic_csv_noheader",
                "scan_pattern": "**/*.csv",
                "file_extensions": [".csv"],
                "delimiter": ",",
                "has_header": False,
            })
        if has_tsv:
            out.append({
                **base,
                "name": "Heuristic_tsv",
                "scan_pattern": "**/*.tsv",
                "file_extensions": [".tsv"],
                "delimiter": "\t",
                "has_header": True,
            })
        if has_txt:
            out.append({
                **base,
                "name": "Heuristic_txt_space",
                "scan_pattern": "**/*.txt",
                "file_extensions": [".txt"],
                "delimiter": r"\s+",
                "has_header": True,
            })
        if has_csv or has_tsv or has_txt:
            out.append({
                **base,
                "name": "Heuristic_tables",
                "scan_pattern": "**/*",
                "file_extensions": [x for x, ok in ((".csv", has_csv), (".tsv", has_tsv), (".txt", has_txt)) if ok],
                "delimiter": ",",
                "has_header": True,
            })
        return out

    def auto_detect(
        self, project_id: str, experiment_id: str, directory_path: str
    ) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        path = (directory_path or "").strip().strip('"').strip("'").strip()
        path = str(Path(path).expanduser()) if path else ""
        if not path or not Path(path).is_dir():
            raise ValueError(f"目录不存在: {directory_path}")

        hint = exp.get("hypothesis") or exp.get("research_goal") or ""
        # 启发式优先（在 bridge 内，且 verify 层可热更新回退）
        out = bridge.auto_detect_and_verify(path, hypothesis_hint=hint)
        data_config = out.get("data_config") or {}
        if not isinstance(data_config, dict) or not data_config.get("source_path"):
            raise ValueError("自动识别未返回可用 data_config")

        exp = {**exp, "data_config": data_config, "phase": "data_uploaded"}
        self._upsert(project_id, exp)
        try:
            from app.integrations.shaxiang.bridge import get_service, shaxiang_workdir

            with shaxiang_workdir():
                svc = get_service()
                sx = svc.repository.get_experiment(self._sx_id(exp))
                if sx is not None:
                    sx.data_config = data_config
                    sx.current_data_config = data_config
                    if getattr(sx, "phase", None) in {
                        None, "created", "data_recommended", "hypothesis_submitted"
                    }:
                        sx.phase = "data_uploaded"
                    svc.repository.update_experiment(sx)
        except Exception as exc:
            logger.warning("AutoDetect 同步 shaxiang data_config 失败: %s", exc)

        return {
            "profile": out.get("profile") or {},
            "preview": out.get("preview") or {},
            "data_config": data_config,
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
            fl_feedback = None
            try:
                from app.services.fl_pack_service import fl_pack_enabled, get_fl_pack_service

                is_fl, setting, profile_id = _resolve_project_fl_gate(project_id)
                if fl_pack_enabled() and is_fl:
                    fl_feedback = get_fl_pack_service().scripts_context_for_llm(
                        fl_setting=setting, profile_id=profile_id
                    )
                else:
                    # 通用模式显式传空串，清空历史误注入的 FL Pack 反馈，避免再次污染脚本
                    fl_feedback = ""
            except Exception:
                fl_feedback = ""
            projected = bridge.design_script(
                project_id, self._sx_id(exp), cfg, human_feedback=fl_feedback
            )
        except ShaxiangBridgeError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("设计脚本失败")
            # 透传截断/解析类错误文案，避免只看到笼统 RuntimeError
            raise RuntimeError(str(exc) or f"设计脚本失败: {exc}") from exc
        return self._persist_projection(project_id, projected)

    def list_fl_script_templates(self, project_id: str) -> List[Dict[str, Any]]:
        from app.services.fl_pack_service import fl_pack_enabled, get_fl_pack_service

        if not fl_pack_enabled():
            return []
        is_fl, setting, profile_id = _resolve_project_fl_gate(project_id)
        if not is_fl:
            return []
        from app.core.database import SessionLocal, init_db
        from app.models.project import Project

        if SessionLocal is None:
            init_db()
        db = SessionLocal()
        try:
            proj = db.query(Project).filter(Project.id == project_id).first()
            if proj and isinstance(proj.config, dict):
                pack = (proj.config.get("fl_pack") or {})
                cached = pack.get("script_templates")
                if isinstance(cached, list) and cached:
                    return cached[:3]
        finally:
            db.close()
        return get_fl_pack_service().list_script_templates(
            fl_setting=setting, limit=3, profile_id=profile_id
        )

    def apply_fl_script_template(
        self, project_id: str, experiment_id: str, script_id: str
    ) -> Dict[str, Any]:
        """将 FL Pack 参考脚本写入实验 analysis_script（仅联邦项目）。"""
        require_shaxiang_enabled()
        is_fl, _, _ = _resolve_project_fl_gate(project_id)
        if not is_fl:
            raise ValueError("当前项目为通用模式，不可应用 FL 参考脚本模板")
        from app.integrations.shaxiang import bridge
        from app.services.fl_pack_service import get_fl_pack_service

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        meta = get_fl_pack_service().read_script_content(script_id)
        projected = bridge.apply_analysis_script(
            project_id,
            self._sx_id(exp),
            meta["content"],
            title=f"FL模板: {meta.get('recommended_when') or meta.get('id')}",
            methodology=f"FL Starter Pack · {meta.get('path')}",
        )
        return self._persist_projection(project_id, projected)

    def set_run_mode(self, project_id: str, experiment_id: str, run_mode: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        projected = bridge.set_run_mode(project_id, self._sx_id(exp), run_mode)
        return self._persist_projection(project_id, projected)

    def set_quality_mode(self, project_id: str, experiment_id: str, quality_mode: str) -> Dict[str, Any]:
        require_shaxiang_enabled()
        from app.integrations.shaxiang import bridge

        exp = self.get(project_id, experiment_id)
        if not exp:
            raise ValueError("实验不存在")
        projected = bridge.set_quality_mode(project_id, self._sx_id(exp), quality_mode)
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

    @staticmethod
    def _iteration_evidence_score(exp: Dict[str, Any]) -> int:
        """按已有轮次/指标/图/失败反例丰富度打分，用于挑选报告主实验。"""
        iterations = [it for it in (exp.get("iterations") or []) if isinstance(it, dict)]
        score = 10 * len(iterations)
        if exp.get("phase") == "completed":
            score += 5
        for it in iterations:
            status = str(it.get("status") or "").lower()
            metrics = it.get("metrics") or (it.get("result") or {}).get("metrics") or {}
            charts = (it.get("result") or {}).get("charts") or []
            if isinstance(metrics, dict) and metrics:
                score += 50
            if isinstance(charts, list) and charts:
                score += 30 * len(charts)
            if status in {"failed", "error"} or it.get("error_message"):
                score += 20  # 失败轮次也可作反例
            elif status in {"success", "partial", "ok", "completed"}:
                score += 15
        return score

    def snapshot_for_report(self, project_id: str) -> Dict[str, Any]:
        """汇总「用于报告」勾选实验；不自动设计脚本或跑迭代。

        未跑满 max_iterations 也可：只要勾选，即用当前已有轮次的指标/图表；
        失败轮次一并纳入，可作为方法无法验证假设的反例证据。
        """
        report_ids = self.get_report_ids(project_id)
        experiments = self.list(project_id)
        selected: List[Dict[str, Any]] = []
        if report_ids:
            id_set = set(report_ids)
            selected = [e for e in experiments if e.get("id") in id_set]
        if not selected:
            # 无勾选时：优先有轮次证据的实验，再退回已完成
            with_iters = [
                e for e in experiments
                if isinstance(e, dict) and (e.get("iterations") or e.get("current_iteration"))
            ]
            selected = with_iters or [e for e in experiments if e.get("phase") == "completed"]
        if not selected:
            return {
                "status": "blocked_need_data",
                "warning": "请先在「迭代实验」页至少跑若干轮并勾选「用于报告」",
                "experiments": [],
                "report_experiment_ids": report_ids,
            }

        # 勾选即用：不要求 phase=completed；按证据丰富度选主实验
        use = list(selected)
        primary = max(use, key=self._iteration_evidence_score)
        synth = self.synthesize_report_fields(primary)
        completed = [e for e in use if e.get("phase") == "completed"]
        cur = int(primary.get("current_iteration") or 0)
        mx = int(primary.get("max_iterations") or 0)
        partial = not completed or (mx > 0 and cur < mx)
        warning = None
        if partial:
            warning = (
                f"所选实验未跑满计划轮次（当前约 {cur}/{mx or '?'}），"
                "将基于已完成轮次的指标/图表生成报告；失败轮次将作为反例写入。"
            )
        return {
            "status": "completed" if completed and not partial else "partial",
            "experiments": use,
            "report_experiment_ids": [e.get("id") for e in use],
            "primary_experiment_id": primary.get("id"),
            "experiment_design": synth["experiment_design"],
            "small_validation": synth["small_validation"],
            "provider": primary.get("provider") or "shaxiang",
            "warning": warning,
        }

    @staticmethod
    def _append_chart_rows(
        *,
        primary: Dict[str, Any],
        charts_root: Path,
        chart_items: Any,
        chart_rows: List[Dict[str, Any]],
        seen: set,
        iteration_number: int,
        iteration_status: str,
        overall_assessment: str = "",
    ) -> int:
        """解析一轮图表并追加；返回新增张数。

        显著问题轮次的图标记为 exclude_from_report，稍后统一过滤。
        """
        added = 0
        if not isinstance(chart_items, list):
            return 0
        assessment = (overall_assessment or "").strip().lower()
        # 执行失败或显著问题 → 默认不进入报告（稍后可保留 1 张诊断图）
        exclude = (
            iteration_status in {"failed", "error"}
            or assessment == "significant_issue"
        )
        diagnostic = exclude  # 标记来源，便于挑选一张反例图
        for c in chart_items:
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
            from app.services.report_content_sanitizer import (
                academic_chart_caption,
                academic_chart_title,
            )

            note = str(c.get("note") or "")
            title = academic_chart_title(
                name=name or plot_id,
                note=note,
                iteration_number=int(iteration_number or 0),
                iteration_status=str(iteration_status or ""),
            )
            caption = academic_chart_caption(note)
            if diagnostic:
                title = f"【反例/失败轮诊断】{title}"
            entry = {
                "plot_id": plot_id,
                "title": title,
                "caption": caption,
                "description": caption,
                "path": str(abs_path) if abs_path else rel,
                "file_path": str(abs_path) if abs_path else rel,
                "url": c.get("url"),
                "source": "sandbox_execution",
                "type": "sandbox_plot",
                "chart_kind": "experiment_result" if not diagnostic else "diagnostic_counterexample",
                "iteration_number": iteration_number,
                "iteration_status": iteration_status,
                "overall_assessment": assessment,
                "quality_flag": "significant_issue" if exclude else (assessment or "ok"),
                "exclude_from_report": exclude,
                "is_diagnostic_candidate": diagnostic,
                "is_generated_from_real_data": True,
                "source_dataset_id": (primary.get("data_config") or {}).get("source_path")
                or (primary.get("data_config") or {}).get("file_name")
                or primary.get("id"),
            }
            chart_rows.append(entry)
            added += 1
        return added

    @staticmethod
    def _resolve_iteration_evidence(
        primary: Dict[str, Any],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
        """汇总全部已跑轮次（含失败）的指标、图表与反例证据。

        不要求跑满 max_iterations；失败轮次也纳入（可作方法不适用之反例）。
        """
        from app.integrations.shaxiang.bridge import shaxiang_root

        charts_root = (shaxiang_root() / "data" / "charts").resolve()
        iterations = primary.get("iterations") or []
        metrics: Dict[str, Any] = {}
        chart_rows: List[Dict[str, Any]] = []
        seen: set[str] = set()
        successful_rounds: List[Dict[str, Any]] = []
        failed_rounds: List[Dict[str, Any]] = []

        for it in iterations:
            if not isinstance(it, dict):
                continue
            status = str(it.get("status") or "").lower()
            if status in {"ok", "completed"}:
                status = "success"
            it_num = int(it.get("iteration_number") or 0)
            it_metrics = it.get("metrics") or (it.get("result") or {}).get("metrics") or {}
            if not isinstance(it_metrics, dict):
                it_metrics = {}
            analysis = it.get("analysis") if isinstance(it.get("analysis"), dict) else {}
            result = it.get("result") if isinstance(it.get("result"), dict) else {}
            decision = it.get("decision") if isinstance(it.get("decision"), dict) else {}
            plan_obj = it.get("plan") if isinstance(it.get("plan"), dict) else {}
            charts = result.get("charts") or []
            n_charts = IterativeExperimentService._append_chart_rows(
                primary=primary,
                charts_root=charts_root,
                chart_items=charts,
                chart_rows=chart_rows,
                seen=seen,
                iteration_number=it_num,
                iteration_status=status,
                overall_assessment=str(analysis.get("overall_assessment") or ""),
            )
            # 成功/部分成功：合并指标；失败但有指标也保留（标明来源）
            if it_metrics:
                if status in {"failed", "error"}:
                    for k, v in it_metrics.items():
                        metrics[f"failed_iter{it_num}_{k}"] = v
                else:
                    metrics = {**metrics, **it_metrics}

            plan_one_liner = str(
                plan_obj.get("description")
                or plan_obj.get("methodology")
                or plan_obj.get("title")
                or ""
            ).strip()[:280]
            decision_reason = str(
                decision.get("reason")
                or decision.get("rationale")
                or analysis.get("suggested_adjustments")
                or ""
            ).strip()
            if isinstance(analysis.get("suggested_adjustments"), list):
                decision_reason = decision_reason or "；".join(
                    str(x) for x in analysis.get("suggested_adjustments")[:3] if x
                )

            round_summary = {
                "iteration_number": it_num,
                "status": status,
                "metrics": it_metrics,
                "chart_count": n_charts,
                "summary": (result.get("summary") or analysis.get("summary") or "")[:500],
                "error_message": str(it.get("error_message") or "")[:800],
                "findings": list(analysis.get("findings") or [])[:8],
                "identified_issues": list(analysis.get("identified_issues") or [])[:8],
                "weaknesses": list(analysis.get("weaknesses") or [])[:6],
                "overall_assessment": str(analysis.get("overall_assessment") or "")[:400],
                "plan_summary": plan_one_liner,
                "decision_reason": decision_reason[:400],
                "decision_continue": decision.get("continue"),
            }
            is_failed = status in {"failed", "error"} or bool(it.get("error_message"))
            if is_failed:
                failed_rounds.append(round_summary)
            else:
                successful_rounds.append(round_summary)

        cur = int(primary.get("current_iteration") or len(iterations) or 0)
        mx = int(primary.get("max_iterations") or 0)
        evidence = {
            "progress": {
                "current_iteration": cur,
                "max_iterations": mx,
                "phase": primary.get("phase") or "",
                "ran_rounds": len(iterations),
                "completed_full_plan": bool(
                    primary.get("phase") == "completed" or (mx > 0 and cur >= mx)
                ),
            },
            "successful_rounds": successful_rounds,
            "failed_rounds": failed_rounds,
            "has_positive_evidence": bool(
                any(
                    (isinstance(r.get("metrics"), dict) and r.get("metrics"))
                    or int(r.get("chart_count") or 0) > 0
                    for r in successful_rounds
                )
                or (metrics and not all(str(k).startswith("failed_iter") for k in metrics))
                or any(
                    str(p.get("iteration_status") or "").lower() not in {"failed", "error"}
                    for p in chart_rows
                    if isinstance(p, dict)
                )
            ),
            "has_negative_evidence": bool(failed_rounds),
            "counterexample_note": (
                "部分迭代失败或未达成功标准，可作为「当前方法难以充分验证该假设」的反例证据；"
                "报告中应如实描述失败原因与局限，勿编造成功指标。"
                if failed_rounds
                else ""
            ),
            "excluded_charts_count": len(
                [p for p in chart_rows if isinstance(p, dict) and p.get("exclude_from_report")]
            ),
        }
        # 显著问题 / 失败轮次：默认剔除；保留最多 1 张诊断图供讨论锚定
        report_plots: List[Dict[str, Any]] = []
        diagnostic_kept = False
        for p in chart_rows:
            if not isinstance(p, dict):
                continue
            if not p.get("exclude_from_report"):
                report_plots.append(p)
                continue
            if not diagnostic_kept and p.get("is_diagnostic_candidate"):
                kept = dict(p)
                kept["exclude_from_report"] = False
                kept["quality_flag"] = "diagnostic_counterexample"
                kept["chart_kind"] = "diagnostic_counterexample"
                report_plots.append(kept)
                diagnostic_kept = True
        evidence["diagnostic_chart_kept"] = diagnostic_kept
        evidence["excluded_charts_count"] = max(
            0,
            int(evidence.get("excluded_charts_count") or 0) - (1 if diagnostic_kept else 0),
        )
        return metrics, report_plots, evidence

    @staticmethod
    def _resolve_iteration_charts(primary: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """兼容旧调用：返回 (metrics, plots)。"""
        metrics, plots, _ = IterativeExperimentService._resolve_iteration_evidence(primary)
        return metrics, plots

    @staticmethod
    def _build_narrative_brief(
        *,
        primary: Dict[str, Any],
        evidence: Dict[str, Any],
        metrics: Dict[str, Any],
        has_positive: bool,
        has_negative: bool,
        partial_run: bool,
        smoke: bool,
        draftish: bool,
    ) -> Dict[str, Any]:
        """从迭代轮次构建科研叙事简报（只重组事实，不编造指标）。"""
        successful = evidence.get("successful_rounds") or []
        failed = evidence.get("failed_rounds") or []
        progress = evidence.get("progress") or {}
        timeline: List[Dict[str, Any]] = []
        for r in list(successful) + list(failed):
            if not isinstance(r, dict):
                continue
            it_num = int(r.get("iteration_number") or 0)
            status = str(r.get("status") or "").lower()
            failed_round = status in {"failed", "error"} or bool(r.get("error_message"))
            key_metrics = {}
            raw_m = r.get("metrics") if isinstance(r.get("metrics"), dict) else {}
            for k, v in list(raw_m.items())[:6]:
                if str(k).startswith("failed_iter"):
                    continue
                key_metrics[str(k)] = v
            timeline.append(
                {
                    "iteration_number": it_num,
                    "status": status,
                    "failed_round": failed_round,
                    "plan_summary": str(r.get("plan_summary") or "")[:280],
                    "decision_reason": str(r.get("decision_reason") or "")[:400],
                    "overall_assessment": str(r.get("overall_assessment") or "")[:200],
                    "key_metrics": key_metrics,
                    "summary": str(r.get("summary") or "")[:300],
                }
            )
        timeline.sort(key=lambda x: int(x.get("iteration_number") or 0))

        adjustment_chain: List[str] = []
        for t in timeline:
            reason = str(t.get("decision_reason") or "").strip()
            plan = str(t.get("plan_summary") or "").strip()
            n = t.get("iteration_number")
            if reason:
                adjustment_chain.append(f"第{n}轮：{reason[:200]}")
            elif plan and t.get("failed_round"):
                adjustment_chain.append(f"第{n}轮尝试「{plan[:120]}」未达成功标准")

        failed_metrics_summary: Dict[str, Any] = {}
        for k, v in (metrics or {}).items():
            if str(k).startswith("failed_iter"):
                failed_metrics_summary[str(k)] = v
        # 也从失败轮直接摘
        for r in failed:
            if not isinstance(r, dict):
                continue
            n = r.get("iteration_number")
            rm = r.get("metrics") if isinstance(r.get("metrics"), dict) else {}
            if rm:
                failed_metrics_summary[f"round_{n}"] = {str(k): v for k, v in list(rm.items())[:8]}

        # evidence_verdict 规则
        if not timeline and not has_positive and not has_negative:
            verdict = "blocked"
        elif has_negative and not has_positive:
            verdict = "contradicted"
        elif smoke or partial_run or draftish or (has_positive and has_negative):
            verdict = "inconclusive"
        elif has_positive and not has_negative and not partial_run:
            verdict = "supported"
        else:
            verdict = "inconclusive"

        return {
            "evidence_verdict": verdict,
            "iteration_timeline": timeline,
            "adjustment_chain": adjustment_chain[:12],
            "failed_round_metrics_summary": failed_metrics_summary,
            "hypothesis": str(primary.get("hypothesis") or "")[:500],
            "progress": progress,
            "notes": {
                "partial_run": partial_run,
                "smoke": smoke,
                "draft_needs_adjustment": draftish,
                "has_positive_evidence": has_positive,
                "has_negative_evidence": has_negative,
            },
        }

    @staticmethod
    def synthesize_report_fields(primary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """把单条迭代实验映射为报告 agent 入参（历史 ed/sv 形状）。

        未跑满计划轮次时仍注入已有结果；失败轮次写入 counterexamples。
        报告侧不注入 analysis_script / 绝对路径 / smoke 运维键。
        """
        from app.services.report_content_sanitizer import (
            clean_iteration_summary,
            display_path_for_report,
            filter_report_metrics,
            humanize_error_message,
            method_boundary_note,
        )

        raw_metrics, plots, evidence = IterativeExperimentService._resolve_iteration_evidence(primary)
        metrics = filter_report_metrics(raw_metrics if isinstance(raw_metrics, dict) else {})
        plan = primary.get("initial_plan") or {}
        data_config = primary.get("data_config") or {}
        source_path = data_config.get("source_path") or data_config.get("file_name") or ""
        source_display = display_path_for_report(source_path)
        source_type = data_config.get("source_type") or ""
        columns = data_config.get("columns") or data_config.get("feature_columns") or []
        target_cols = data_config.get("target_columns") or []
        if isinstance(target_cols, str):
            target_cols = [target_cols]

        progress = evidence.get("progress") or {}
        failed_rounds = evidence.get("failed_rounds") or []
        successful_rounds = evidence.get("successful_rounds") or []
        # 净化失败轮次中的堆栈与 smoke 前缀
        cleaned_failed: List[Dict[str, Any]] = []
        for r in failed_rounds:
            if not isinstance(r, dict):
                continue
            rr = dict(r)
            if rr.get("error_message"):
                rr["error_message"] = humanize_error_message(rr.get("error_message"))
            if rr.get("summary"):
                rr["summary"] = clean_iteration_summary(rr.get("summary"))
            cleaned_failed.append(rr)
        failed_rounds = cleaned_failed
        cleaned_ok: List[Dict[str, Any]] = []
        for r in successful_rounds:
            if not isinstance(r, dict):
                continue
            rr = dict(r)
            if rr.get("summary"):
                rr["summary"] = clean_iteration_summary(rr.get("summary"))
            cleaned_ok.append(rr)
        successful_rounds = cleaned_ok

        has_positive = bool(metrics or plots) or bool(successful_rounds)
        has_negative = bool(failed_rounds)
        has_usable = has_positive or has_negative
        partial_run = not progress.get("completed_full_plan")
        smoke = "smoke" in str((raw_metrics or {}).get("run_scope") or "").lower()

        dataset_desc = (
            (
                f"数据集: {source_display}"
                + (f"（类型: {source_type}）" if source_type else "")
                + "。来自迭代实验绑定的真实/本地数据，用于初步实验验证。"
            )
            if source_display
            else ""
        )
        source_desc = ""
        if source_display or source_type:
            source_desc = (
                f"历史/训练数据来源: {source_type or 'local'}；"
                f"数据集标识: {source_display or '已绑定数据集'}。"
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

        limitations = "迭代实验引擎产出；详见 iterations。"
        if smoke:
            limitations += " 当前为 smoke/小样本可行性验证，不得外推为全量结论。"
        if partial_run:
            limitations += (
                f" 当前仅完成 {progress.get('current_iteration')}/{progress.get('max_iterations') or '?'} 轮，"
                "报告基于已跑轮次，非最终全量结论。"
            )
        if has_negative:
            limitations += " 含失败轮次，可作为方法验证失败或假设不适用之反例。"
        # 草稿模式：需调整轮次仍可入报告，但须写明优劣
        draftish = any(
            str(r.get("overall_assessment") or "").lower() == "needs_adjustment"
            for r in successful_rounds
            if isinstance(r, dict)
        )
        if draftish:
            limitations += (
                " 部分轮次评估为「需调整」：报告须并列写清优点、局限与可改进点，"
                "不得包装为最终严谨结论。"
            )
        excluded_n = int((evidence.get("excluded_charts_count") or 0))
        if excluded_n:
            limitations += f" 已剔除 {excluded_n} 张显著问题/失败轮次图表，不写入正文图区。"

        boundary = method_boundary_note(
            {"sandbox_execution": {"partial_run": partial_run, "metrics": raw_metrics}},
            {"experiment_spec": {"feature_columns": columns}},
        )
        methods_text = str(plan.get("methodology") or "").strip()
        if methods_text and boundary not in methods_text:
            methods_text = f"{methods_text}\n\n【验证边界】{boundary}"
        elif not methods_text:
            methods_text = f"【验证边界】{boundary}"

        experiment_design = {
            "hypothesis": primary.get("hypothesis"),
            "methods": methods_text,
            "baselines": "baseline vs proposed (iterative experiment)",
            "metrics": str(metrics.get("primary_metric") or metrics.get("accuracy") or "accuracy"),
            "experimental_steps": plan.get("description") or "",
            "expected_results": "; ".join(plan.get("success_criteria") or []),
            "limitations": limitations,
            "datasets": dataset_desc or source_display or "",
            "source_data": source_desc or source_type or "",
            "target_data": target_desc,
            "method_boundary": boundary,
            "experiment_spec": {
                "primary_metric": metrics.get("primary_metric") or "accuracy",
                "task_type": "classification",
                "feature_columns": columns,
            },
            # 不向报告 LLM 注入分析脚本全文，避免代码痕迹泄漏
            "analysis_script": "",
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
            "success": has_positive,
            "output_complete": bool(progress.get("completed_full_plan")) and has_positive,
            "sandbox_incomplete": partial_run,
            "partial_run": partial_run,
            "metrics": metrics,
            "plots": plots,
            "iteration_progress": progress,
        }
        if has_positive and has_negative:
            summary = (
                f"已跑 {progress.get('ran_rounds', 0)} 轮（计划 {progress.get('max_iterations') or '?'}）："
                f"产出 {len(metrics)} 项指标、{len(plots)} 张图表；"
                f"另有 {len(failed_rounds)} 轮失败可作反例。"
            )
        elif has_positive:
            summary = (
                f"已跑 {progress.get('ran_rounds', 0)} 轮（计划 {progress.get('max_iterations') or '?'}），"
                f"产出 {len(metrics)} 项指标、{len(plots)} 张图表。"
                + ("（未跑满计划轮次，以下为阶段性结果。）" if partial_run else "")
            )
        elif has_negative:
            summary = (
                f"已跑 {progress.get('ran_rounds', 0)} 轮，暂无成功指标/图表，"
                f"但有 {len(failed_rounds)} 轮失败记录，可作为该方法难以验证假设的反例。"
            )
        else:
            summary = "迭代实验尚未产出可引用的指标、图表或失败反例。"
        if smoke:
            summary = "小样本可行性验证（smoke）。" + summary
        summary = clean_iteration_summary(summary)

        if has_positive:
            result_type = "has_actual_results"
        elif has_negative:
            result_type = "has_negative_evidence"
        else:
            result_type = "none"

        # 供证据检测保留 run_scope，但正文 metrics 已过滤
        evidence_for_flags = dict(evidence)
        evidence_for_flags["failed_rounds"] = failed_rounds
        evidence_for_flags["successful_rounds"] = successful_rounds

        actual_results = {
            "data_source": "sandbox_execution",
            "sandbox_execution": sandbox_execution,
            "sandbox_metrics": metrics,
            "sandbox_plots": plots,
            "iteration_evidence": evidence_for_flags,
            "failed_iterations": failed_rounds,
            "successful_iterations": successful_rounds,
            "counterexamples": failed_rounds,
            "summary": summary,
        }

        narrative_brief = IterativeExperimentService._build_narrative_brief(
            primary=primary,
            evidence=evidence_for_flags,
            metrics=raw_metrics if isinstance(raw_metrics, dict) else {},
            has_positive=has_positive,
            has_negative=has_negative,
            partial_run=partial_run,
            smoke=smoke,
            draftish=draftish,
        )

        small_validation = {
            "hypothesis": primary.get("hypothesis"),
            "validation_status": "completed" if progress.get("completed_full_plan") else "partial",
            "has_real_data": 1 if data_config else 0,
            "narrative_brief": narrative_brief,
            "sandbox_execution": {
                **sandbox_execution,
                # evidence_flags 读 raw run_scope
                "metrics": {
                    **metrics,
                    **({"run_scope": raw_metrics.get("run_scope")} if isinstance(raw_metrics, dict) and raw_metrics.get("run_scope") else {}),
                },
            },
            "artifacts": {"metrics": metrics, "plots": plots},
            "results": {
                "actual_results": actual_results,
                "result_type_summary": result_type,
                "warnings": (
                    [evidence.get("counterexample_note")]
                    if evidence.get("counterexample_note")
                    else []
                ),
            },
            "_provider": "iterative_experiment",
            "_experiment_id": primary.get("id"),
            "_has_usable_evidence": has_usable,
        }

        # Phase4：仅联邦学习项目可挂 FL 本地 pilot / VFL gate（通用模式禁止混入）
        try:
            from app.core.config import get_settings
            from app.core.project_modes import is_federated_learning_mode
            from app.services.fl_pack_service import FlPackService, fl_pack_enabled, get_fl_pack_service

            settings = get_settings()
            project_id = str(primary.get("project_id") or "")
            is_fl = False
            if project_id:
                is_fl, _, _ = _resolve_project_fl_gate(project_id)
            else:
                # 无 project_id 时不以关键词猜测为联邦，避免污染通用报告
                is_fl = is_federated_learning_mode(primary.get("project_mode"))

            if fl_pack_enabled() and is_fl:
                fl_svc = get_fl_pack_service()
                fl_ctx = FlPackService.infer_fl_context_from_columns(
                    [str(c) for c in columns],
                    project_mode="federated_learning",
                )
                small_validation["fl_context"] = fl_ctx
                gate = fl_svc.maybe_attach_vfl_gate(fl_ctx)
                small_validation["federated_pilot"] = {
                    "alignment_gate": gate,
                    "execution_mode": "local_pack",
                }
                if getattr(settings, "AISCI_FL_LOCAL_PILOT_ENABLED", True) and not metrics:
                    pilot = fl_svc.run_local_fedavg_pilot()
                    small_validation["federated_pilot"]["local_fedavg"] = pilot
                    if pilot.get("success") and isinstance(pilot.get("metrics"), dict):
                        pm = pilot["metrics"]
                        merged_metrics = {**metrics, **{k: v for k, v in pm.items() if k != "history"}}
                        sandbox_execution["metrics"] = merged_metrics
                        sandbox_execution["success"] = True
                        actual_results["sandbox_metrics"] = merged_metrics
                        actual_results["fl_local_pilot"] = pm
                        small_validation["artifacts"]["metrics"] = merged_metrics
                        small_validation["results"]["result_type_summary"] = "has_actual_results"
                        small_validation["_has_usable_evidence"] = True
        except Exception as exc:
            logger.warning("[FL Pack] synthesize pilot/gate 跳过: %s", exc)

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
