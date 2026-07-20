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

        metadata = load_metadata_with_contract(data_config, sample_size=sample_size)
        if metadata.get("error"):
            raise ValueError(metadata["error"])
        if not metadata.get("columns"):
            raise ValueError("试加载成功但未得到任何列，Profile 可能不正确")

        modality = (metadata.get("modality") or modality_hint or "tabular").lower()
        path_col = metadata.get("media_path_column")
        if modality in {"image", "audio", "mixed", "media"} or path_col:
            if not path_col:
                raise ValueError("媒体数据集试加载后缺少 file_path/路径列，请检查 AutoDetect Profile")
            sample_paths = metadata.get("sample_paths") or []
            if not sample_paths:
                raise ValueError("媒体数据集没有可预览的样本路径")
            readable = 0
            for p in sample_paths[:5]:
                if Path(str(p)).exists():
                    readable += 1
            if readable == 0:
                raise ValueError("样本路径均不可读，请检查 manifest 路径解析或目录结构")
            if not metadata.get("suggested_target_columns") and "label" not in (metadata.get("columns") or []):
                raise ValueError("媒体数据集未找到标签列（如 label），请调整 Profile 或目录结构")
        elif not metadata.get("numeric_columns"):
            raise ValueError(
                "试加载后没有数值列，无法可靠设计分析脚本。"
                "请改用预置 Profile，或重新 AutoDetect。"
            )

        return {
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
            "preview": metadata,
        }

    def delete_experiment(self, experiment_id: str) -> None:
        """删除实验及其所有关联数据"""
        self.repository.delete_experiment(experiment_id)
        logger.info(f"删除实验: {experiment_id}")
