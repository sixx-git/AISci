import uuid
import logging
from typing import Optional

from config.settings import load_config, AppConfig
from llm.client import LLMClient
from storage.sqlite_store import SQLiteRepository
from storage.repository import Repository, IterationRecord
from core.planner import ExperimentPlanner
from core.executor import ExperimentExecutor
from core.analyzer import ResultAnalyzer
from core.reflector import IterationReflector
from core.engine import IterationEngine, EngineConfig
from core.dataset_profiler import DatasetProfiler
from schemas.experiment import Experiment, ExperimentStatus
from executors.dataset_profile import DatasetProfile

logger = logging.getLogger(__name__)


class ExperimentService:
    """业务逻辑门面 - 为 API 和 Web 提供统一接口"""

    _instance: Optional['ExperimentService'] = None

    def __init__(self, config: AppConfig = None):
        self.config = config or load_config()
        self._init_components()

    @classmethod
    def get_instance(cls) -> 'ExperimentService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def _init_components(self):
        """初始化所有组件"""
        self.llm_client = LLMClient(self.config.llm)
        self.repository: Repository = SQLiteRepository(self.config.storage.db_path)
        self.planner = ExperimentPlanner(self.llm_client, self.repository)
        self.analyzer = ResultAnalyzer(self.llm_client, self.repository)
        self.reflector = IterationReflector(self.llm_client, self.repository)
        self.executor = ExperimentExecutor()
        self.engine = IterationEngine(
            planner=self.planner,
            executor=self.executor,
            analyzer=self.analyzer,
            reflector=self.reflector,
            repository=self.repository,
            config=EngineConfig.from_env(),
        )
        self.dataset_profiler = DatasetProfiler(self.llm_client)

    def create_experiment(
        self,
        title: str,
        research_goal: str,
        constraints: list[str] = None,
        executor_type: str = "simulation",
        max_iterations: int = 10,
    ) -> Experiment:
        """创建新实验"""
        experiment = Experiment(
            id=str(uuid.uuid4()),
            title=title or research_goal[:30],
            research_goal=research_goal,
            constraints=constraints or [],
            status=ExperimentStatus.CREATED,
            executor_type=executor_type,
            max_iterations=max_iterations,
        )
        self.repository.save_experiment(experiment)
        logger.info(f"创建实验: {experiment.title} (ID: {experiment.id})")
        return experiment

    def start_experiment(self, experiment_id: str) -> Experiment:
        """启动实验（生成初始方案）"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        return self.engine.start_experiment(experiment)

    def run_iteration(self, experiment_id: str) -> IterationRecord:
        """执行一轮迭代"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        return self.engine.run_single_iteration(experiment)

    def run_full_experiment(self, experiment_id: str, callback=None) -> Experiment:
        """持续运行直到完成"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        return self.engine.run_to_completion(experiment, callback=callback)

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        return self.repository.get_experiment(experiment_id)

    def get_experiment_with_iterations(self, experiment_id: str) -> Optional[dict]:
        """返回实验及所有迭代记录"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            return None
        iterations = self.repository.get_iterations(experiment_id)
        return {
            "experiment": experiment.model_dump(),
            "iterations": [
                {
                    "iteration_number": it.iteration_number,
                    "plan": it.plan,
                    "result": it.result,
                    "analysis": it.analysis,
                    "decision": it.decision,
                    "metrics": it.metrics,
                    "status": it.status,
                    "error_message": it.error_message,
                    "duration_seconds": it.duration_seconds,
                }
                for it in iterations
            ],
        }

    def get_improvement_metrics(self, experiment_id: str) -> list[dict]:
        """获取改进趋势数据"""
        return self.repository.get_metrics_history(experiment_id)

    # ========== 假设驱动迭代 API ==========

    def recommend_datasets(self, experiment_id: str, human_feedback: str = None):
        """Phase 1: 根据假设推荐数据集"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        # 设置人工反馈
        if human_feedback:
            experiment.human_feedback = human_feedback
            self.repository.update_experiment(experiment)
        return self.engine.run_data_iteration(experiment, phase="recommend")

    def design_script(self, experiment_id: str, data_config: dict, human_feedback: str = None):
        """Phase 2: 根据上传数据设计分析脚本；可附带人工反馈做高自由度重设计。

        human_feedback:
          - None: 不改动已有 feedback（兼容旧调用）
          - "" / 空白: 清空 feedback（用于通用模式去掉误注入的 FL 上下文）
          - 非空: 写入并标记 submitted
        """
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        experiment.current_data_config = data_config
        experiment.phase = "data_uploaded"
        if human_feedback is not None:
            text = human_feedback.strip()
            experiment.human_feedback = text or None
            experiment.feedback_status = "submitted" if text else "none"
        self.repository.update_experiment(experiment)
        return self.engine.run_data_iteration(experiment, phase="design")

    def redesign_script_from_feedback(self, experiment_id: str, feedback: str = None):
        """
        按人工反馈立即重设计脚本（design 阶段 + IDE 式 smoke→patch）。
        也可不点此按钮：提交反馈后直接「执行下一轮」同样会脚本级迭代。
        """
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        text = (feedback or experiment.human_feedback or "").strip()
        if not text:
            raise ValueError("请先填写人工反馈（修改方向、脚本片段、图表问题等）")
        experiment.human_feedback = text
        experiment.feedback_status = "submitted"
        data_config = (
            getattr(experiment, "current_data_config", None)
            or getattr(experiment, "data_config", None)
            or {}
        )
        if not data_config:
            raise ValueError("缺少数据配置，请先上传/确认数据后再重设计脚本")
        experiment.current_data_config = data_config
        self.repository.update_experiment(experiment)
        return self.engine.run_data_iteration(experiment, phase="design")

    def set_run_mode(self, experiment_id: str, run_mode: str) -> Experiment:
        """设置实验运行模式: smoke_only | full"""
        mode = (run_mode or "").strip().lower()
        if mode not in {"smoke_only", "full"}:
            raise ValueError("run_mode 必须是 smoke_only 或 full")
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        experiment.run_mode = mode
        self.repository.update_experiment(experiment)
        logger.info("实验 %s run_mode=%s", experiment_id[:8], mode)
        return experiment

    def set_quality_mode(self, experiment_id: str, quality_mode: str) -> Experiment:
        """设置质量模式: draft | strict"""
        from core.quality_mode import normalize_quality_mode

        mode = normalize_quality_mode(quality_mode)
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        experiment.quality_mode = mode
        self.repository.update_experiment(experiment)
        logger.info("实验 %s quality_mode=%s", experiment_id[:8], mode)
        return experiment

    def submit_feedback(self, experiment_id: str, feedback: str):
        """提交人工反馈（标记为待落实，下一轮迭代或重设计会解锁脚本）"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        experiment.human_feedback = feedback
        experiment.feedback_status = "submitted"
        # 若因等待人工确认而暂停，提交反馈后允许继续
        if experiment.status == ExperimentStatus.PAUSED:
            experiment.status = ExperimentStatus.CREATED
            if getattr(experiment, "phase", "") == "needs_human_review":
                experiment.phase = "script_designed"
        self.repository.update_experiment(experiment)
        return experiment

    def run_data_iteration(self, experiment_id: str, phase: str = "recommend"):
        """执行假设驱动的单阶段迭代"""
        experiment = self.repository.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")
        return self.engine.run_data_iteration(experiment, phase=phase)

    def list_all_experiments(self, status: str = None) -> list[Experiment]:
        return self.repository.list_experiments(status=status)

    def auto_detect_profile(self, directory_path: str, hypothesis_hint: str = "") -> DatasetProfile:
        """自动识别数据集格式并生成 Profile"""
        return self.dataset_profiler.generate_profile(
            directory_path=directory_path,
            hypothesis_hint=hypothesis_hint,
        )

    def verify_data_config(self, data_config: dict, sample_size: int = 5000) -> dict:
        """
        试加载数据并返回列契约预览。
        失败时抛出异常，供 AutoDetect / 设计脚本前阻断。
        支持 tabular（需数值列）与 image/audio manifest（需路径列+可读样本）。
        """
        from pathlib import Path
        from core.script_validator import load_metadata_with_contract

        # 从 profile_json 读取 modality，媒体默认更小采样
        modality_hint = "tabular"
        raw_pj = (data_config or {}).get("profile_json") or ""
        if isinstance(raw_pj, str) and raw_pj.strip().startswith("{"):
            try:
                import json
                modality_hint = (json.loads(raw_pj).get("modality") or "tabular").lower()
            except Exception:
                pass
        if modality_hint in {"image", "audio", "mixed"} and sample_size > 500:
            sample_size = min(sample_size, 200)

        recovered_profile = None
        load_error = None
        try:
            metadata = load_metadata_with_contract(data_config, sample_size=sample_size)
        except Exception as exc:
            metadata = {"error": str(exc), "columns": [], "numeric_columns": []}
            load_error = str(exc)

        modality = (metadata.get("modality") or modality_hint or "tabular").lower()
        path_col = metadata.get("media_path_column")
        source_type = str((data_config or {}).get("source_type") or "")
        media_ok = False
        if (modality in {"image", "audio", "mixed", "media"} or path_col) and not load_error:
            sample_paths = metadata.get("sample_paths") or []
            readable = sum(1 for p in (sample_paths or [])[:5] if Path(str(p)).exists())
            media_ok = bool(path_col and sample_paths and readable > 0)

        # 目录数据：只要没有数值列 / 加载失败，就做表格回退。
        # 不能因「误判成媒体且 media_ok」而跳过——否则会带着 0 数值列放行或误报。
        needs_tabular_recover = source_type == "directory" and (
            bool(load_error)
            or bool(metadata.get("error"))
            or not metadata.get("columns")
            or not metadata.get("numeric_columns")
        )
        if needs_tabular_recover:
            recovered = self._recover_tabular_numeric_profile(
                data_config, sample_size=max(sample_size, 2000)
            )
            if recovered is not None:
                metadata, recovered_profile = recovered
                load_error = None
                modality = (metadata.get("modality") or "tabular").lower()
                path_col = metadata.get("media_path_column")
                media_ok = False

        if metadata.get("error"):
            raise ValueError(metadata["error"])
        if load_error and not metadata.get("columns"):
            raise ValueError(load_error)
        if not metadata.get("columns"):
            raise ValueError("试加载成功但未得到任何列，Profile 可能不正确")

        has_numeric = bool(metadata.get("numeric_columns"))
        if has_numeric:
            pass
        elif media_ok and (modality in {"image", "audio", "mixed", "media"} or path_col):
            if not metadata.get("suggested_target_columns") and "label" not in (metadata.get("columns") or []):
                raise ValueError("媒体数据集未找到标签列（如 label），请调整 Profile 或目录结构")
        else:
            raise ValueError(
                "试加载后没有数值列，无法可靠设计分析脚本。"
                "请改用预置 Profile，或重新 AutoDetect。"
            )

        result = {
            "ok": True,
            "row_count": metadata.get("row_count"),
            "column_count": metadata.get("column_count"),
            "columns": metadata.get("columns"),
            "dtypes": metadata.get("dtypes"),
            "numeric_columns": metadata.get("numeric_columns"),
            "non_numeric_columns": metadata.get("non_numeric_columns"),
            "suggested_target_columns": metadata.get("suggested_target_columns"),
            "modality": modality,
            "media_path_column": path_col,
            "sample_paths": metadata.get("sample_paths"),
            "label_distribution": metadata.get("label_distribution"),
            "files_scanned": metadata.get("files_scanned"),
            "files_used": metadata.get("files_used"),
            "scanned_files": metadata.get("scanned_files"),
            "used_files": metadata.get("used_files"),
            "combine_meta": metadata.get("combine_meta"),
            "preview": metadata,
        }
        if recovered_profile is not None:
            result["recovered_profile"] = recovered_profile
            result["profile_recovered"] = True
        return result

    def _recover_tabular_numeric_profile(
        self, data_config: dict, sample_size: int = 5000
    ):
        """无数值列时尝试常见表格 Profile 变体，返回 (metadata, profile_dict) 或 None。

        故意不继承 LLM Profile 的字段（skip_rows / 错误 modality 等会污染回退）。
        """
        import json
        from pathlib import Path

        from core.script_validator import load_metadata_with_contract

        cfg = dict(data_config or {})
        if (cfg.get("source_type") or "") != "directory":
            return None
        root = Path(str(cfg.get("source_path") or "")).expanduser()
        if not root.is_dir():
            return None

        has_csv = any(root.rglob("*.csv"))
        has_tsv = any(root.rglob("*.tsv"))
        has_txt = any(
            p for p in root.rglob("*.txt") if "readme" not in p.name.lower()
        )
        excludes = [
            r"(?i)^readme(\.|$)",
            r"(?i)\.md$",
            r"^\.DS_Store$",
            r"(?i)\.rdata$",
            r"(?i)^license(\.|$)",
        ]
        base_fields = {
            "modality": "tabular",
            "comment_prefix": "",
            "exclude_patterns": excludes,
            "skip_rows": 0,
        }
        variants = []
        if has_csv:
            variants.extend(
                [
                    {
                        **base_fields,
                        "name": "AutoDetected_csv",
                        "scan_pattern": "**/*.csv",
                        "file_extensions": [".csv"],
                        "delimiter": ",",
                        "has_header": True,
                    },
                    {
                        **base_fields,
                        "name": "AutoDetected_csv_noheader",
                        "scan_pattern": "**/*.csv",
                        "file_extensions": [".csv"],
                        "delimiter": ",",
                        "has_header": False,
                    },
                    {
                        **base_fields,
                        "name": "AutoDetected_csv_semi",
                        "scan_pattern": "**/*.csv",
                        "file_extensions": [".csv"],
                        "delimiter": ";",
                        "has_header": True,
                    },
                ]
            )
        if has_tsv:
            variants.append(
                {
                    **base_fields,
                    "name": "AutoDetected_tsv",
                    "scan_pattern": "**/*.tsv",
                    "file_extensions": [".tsv"],
                    "delimiter": "\t",
                    "has_header": True,
                }
            )
        if has_txt:
            variants.append(
                {
                    **base_fields,
                    "name": "AutoDetected_txt_space",
                    "scan_pattern": "**/*.txt",
                    "file_extensions": [".txt"],
                    "delimiter": r"\s+",
                    "has_header": True,
                }
            )
        table_exts = [
            x
            for x, ok in ((".csv", has_csv), (".tsv", has_tsv), (".txt", has_txt))
            if ok
        ]
        if table_exts:
            variants.append(
                {
                    **base_fields,
                    "name": "AutoDetected_tables",
                    "scan_pattern": "**/*",
                    "file_extensions": table_exts,
                    "delimiter": ",",
                    "has_header": True,
                }
            )
        # 目录扫不到扩展名时仍尝试常见组合（隐藏扩展名 / 大小写异常）
        if not variants:
            variants = [
                {
                    **base_fields,
                    "name": "AutoDetected_csv",
                    "scan_pattern": "**/*.csv",
                    "file_extensions": [".csv"],
                    "delimiter": ",",
                    "has_header": True,
                },
                {
                    **base_fields,
                    "name": "AutoDetected_tables",
                    "scan_pattern": "**/*",
                    "file_extensions": [".csv", ".txt", ".tsv"],
                    "delimiter": ",",
                    "has_header": True,
                },
            ]

        best = None
        for profile in variants:
            trial = {
                **cfg,
                "profile_name": "AutoDetect",
                "profile_json": json.dumps(profile, ensure_ascii=False),
            }
            try:
                meta = load_metadata_with_contract(trial, sample_size=sample_size)
            except Exception:
                continue
            if meta.get("error") or not meta.get("columns"):
                continue
            n_num = len(meta.get("numeric_columns") or [])
            if n_num <= 0:
                continue
            score = (
                n_num,
                int(meta.get("row_count") or 0),
                int(meta.get("column_count") or 0),
            )
            if best is None or score > best[0]:
                best = (score, meta, profile)

        if best is None:
            return None
        _, meta, profile = best
        return meta, profile

    def delete_experiment(self, experiment_id: str) -> None:
        """删除实验及其所有关联数据"""
        self.repository.delete_experiment(experiment_id)
        logger.info(f"删除实验: {experiment_id}")
