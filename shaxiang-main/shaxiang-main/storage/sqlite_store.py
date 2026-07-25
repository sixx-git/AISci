import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from schemas.experiment import Experiment, ExperimentStatus
from storage.repository import Repository, IterationRecord


class SQLiteRepository(Repository):
    """SQLite 持久化实现"""

    def __init__(self, db_path: str = "data/experiments.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                research_goal TEXT NOT NULL,
                constraints TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'created',
                executor_type TEXT NOT NULL DEFAULT 'simulation',
                max_iterations INTEGER NOT NULL DEFAULT 10,
                current_iteration INTEGER NOT NULL DEFAULT 0,
                initial_plan TEXT,
                hypothesis TEXT NOT NULL DEFAULT '',
                dataset_recommendations TEXT,
                current_data_config TEXT,
                phase TEXT NOT NULL DEFAULT 'created',
                data_config TEXT,
                human_feedback TEXT,
                feedback_status TEXT NOT NULL DEFAULT 'none',
                run_mode TEXT NOT NULL DEFAULT 'smoke_only',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS iterations (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL REFERENCES experiments(id),
                iteration_number INTEGER NOT NULL,
                plan_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}',
                analysis_json TEXT,
                decision_json TEXT,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                duration_seconds REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(experiment_id, iteration_number)
            );

            CREATE INDEX IF NOT EXISTS idx_iterations_experiment
                ON iterations(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_iterations_number
                ON iterations(experiment_id, iteration_number);
        """)
        # 迁移：为旧数据库添加新列（忽略已存在的列错误）
        migration_cols = [
            ("hypothesis", "TEXT NOT NULL DEFAULT ''"),
            ("dataset_recommendations", "TEXT"),
            ("current_data_config", "TEXT"),
            ("phase", "TEXT NOT NULL DEFAULT 'created'"),
            ("data_config", "TEXT"),
            ("human_feedback", "TEXT"),
            ("feedback_status", "TEXT NOT NULL DEFAULT 'none'"),
            ("run_mode", "TEXT NOT NULL DEFAULT 'smoke_only'"),
            ("quality_mode", "TEXT NOT NULL DEFAULT 'draft'"),
        ]
        for col_name, col_def in migration_cols:
            try:
                conn.execute(f"ALTER TABLE experiments ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        conn.commit()
        conn.close()

    # --- 实验 ---

    def save_experiment(self, experiment: Experiment) -> str:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO experiments
                   (id, title, research_goal, constraints, status, executor_type,
                    max_iterations, current_iteration, initial_plan, hypothesis,
                    dataset_recommendations, current_data_config, phase,
                    data_config, human_feedback, feedback_status, run_mode,
                    quality_mode,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    experiment.id,
                    experiment.title,
                    experiment.research_goal,
                    json.dumps(experiment.constraints, ensure_ascii=False),
                    experiment.status.value,
                    experiment.executor_type,
                    experiment.max_iterations,
                    experiment.current_iteration,
                    json.dumps(experiment.initial_plan.model_dump(), ensure_ascii=False)
                    if experiment.initial_plan else None,
                    getattr(experiment, 'hypothesis', ''),
                    json.dumps(experiment.dataset_recommendations, ensure_ascii=False)
                    if getattr(experiment, 'dataset_recommendations', None) else None,
                    json.dumps(experiment.current_data_config, ensure_ascii=False)
                    if getattr(experiment, 'current_data_config', None) else None,
                    getattr(experiment, 'phase', 'created'),
                    json.dumps(experiment.data_config, ensure_ascii=False)
                    if getattr(experiment, 'data_config', None) else None,
                    getattr(experiment, 'human_feedback', None),
                    getattr(experiment, 'feedback_status', 'none'),
                    getattr(experiment, 'run_mode', None) or 'smoke_only',
                    getattr(experiment, 'quality_mode', None) or 'draft',
                    experiment.created_at,
                    experiment.updated_at,
                ),
            )
            conn.commit()
            return experiment.id
        finally:
            conn.close()

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_experiment(row)
        finally:
            conn.close()

    def list_experiments(self, status: str = None) -> list[Experiment]:
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM experiments WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM experiments ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_experiment(r) for r in rows]
        finally:
            conn.close()

    def update_experiment(self, experiment: Experiment) -> None:
        experiment.updated_at = datetime.now().isoformat()
        self.save_experiment(experiment)

    def delete_experiment(self, experiment_id: str) -> None:
        """删除实验及其所有迭代记录（级联删除）"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM iterations WHERE experiment_id = ?", (experiment_id,))
            conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
            conn.commit()
        finally:
            conn.close()

    # --- 迭代记录 ---

    def save_iteration(self, experiment_id: str, record: IterationRecord) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO iterations
                   (id, experiment_id, iteration_number, plan_json, result_json,
                    analysis_json, decision_json, metrics_json, status,
                    error_message, duration_seconds, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    experiment_id,
                    record.iteration_number,
                    json.dumps(record.plan, ensure_ascii=False),
                    json.dumps(record.result, ensure_ascii=False),
                    json.dumps(record.analysis, ensure_ascii=False),
                    json.dumps(record.decision, ensure_ascii=False),
                    json.dumps(record.metrics, ensure_ascii=False),
                    record.status,
                    record.error_message,
                    record.duration_seconds,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_iterations(self, experiment_id: str) -> list[IterationRecord]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM iterations WHERE experiment_id = ? ORDER BY iteration_number",
                (experiment_id,),
            ).fetchall()
            return [self._row_to_iteration(r) for r in rows]
        finally:
            conn.close()

    def get_latest_iteration(self, experiment_id: str) -> Optional[IterationRecord]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM iterations WHERE experiment_id = ? ORDER BY iteration_number DESC LIMIT 1",
                (experiment_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_iteration(row)
        finally:
            conn.close()

    def get_metrics_history(self, experiment_id: str) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT iteration_number, metrics_json FROM iterations WHERE experiment_id = ? ORDER BY iteration_number",
                (experiment_id,),
            ).fetchall()
            result = []
            for r in rows:
                metrics = json.loads(r["metrics_json"])
                metrics["iteration"] = r["iteration_number"]
                result.append(metrics)
            return result
        finally:
            conn.close()

    # --- 内部辅助 ---

    def _row_to_experiment(self, row) -> Experiment:
        # 必须用当前 schemas 模块中的类：bridge 热重载会替换 schemas.*，
        # 若继续用本文件顶部缓存的旧 Experiment，会把新 ExperimentPlan 判为类型不匹配。
        from schemas.experiment import Experiment as ExperimentCls
        from schemas.experiment import ExperimentPlan, ExperimentStatus as StatusCls

        initial_plan = None
        if row["initial_plan"]:
            try:
                raw_plan = json.loads(row["initial_plan"])
                # 先走 dict，避免跨 reload 的 BaseModel 实例身份冲突
                if isinstance(raw_plan, dict):
                    initial_plan = ExperimentPlan.model_validate(raw_plan)
                else:
                    initial_plan = None
            except Exception:
                initial_plan = None

        return ExperimentCls(
            id=row["id"],
            title=row["title"],
            research_goal=row["research_goal"],
            constraints=json.loads(row["constraints"]),
            status=StatusCls(row["status"]),
            executor_type=row["executor_type"],
            max_iterations=row["max_iterations"],
            current_iteration=row["current_iteration"],
            # 传 dict 再校验，兼容热重载后的类替换
            initial_plan=initial_plan.model_dump() if initial_plan is not None else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            hypothesis=row["hypothesis"] if "hypothesis" in row.keys() else "",
            dataset_recommendations=json.loads(row["dataset_recommendations"]) if row["dataset_recommendations"] else None,
            current_data_config=json.loads(row["current_data_config"]) if row["current_data_config"] else None,
            phase=row["phase"] if "phase" in row.keys() else "created",
            data_config=json.loads(row["data_config"]) if row["data_config"] else None,
            human_feedback=row["human_feedback"] if "human_feedback" in row.keys() else None,
            feedback_status=row["feedback_status"] if "feedback_status" in row.keys() else "none",
            run_mode=(
                row["run_mode"]
                if "run_mode" in row.keys() and row["run_mode"]
                else "smoke_only"
            ),
            quality_mode=(
                row["quality_mode"]
                if "quality_mode" in row.keys() and row["quality_mode"]
                else "draft"
            ),
        )

    def _row_to_iteration(self, row) -> IterationRecord:
        return IterationRecord(
            iteration_number=row["iteration_number"],
            plan=json.loads(row["plan_json"]),
            result=json.loads(row["result_json"]),
            analysis=json.loads(row["analysis_json"]) if row["analysis_json"] else {},
            decision=json.loads(row["decision_json"]) if row["decision_json"] else {},
            metrics=json.loads(row["metrics_json"]),
            status=row["status"],
            error_message=row["error_message"] or "",
            duration_seconds=row["duration_seconds"] or 0,
        )
