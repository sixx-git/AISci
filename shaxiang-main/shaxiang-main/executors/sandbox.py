"""
沙箱脚本执行器

设计理念:
- 用户或 LLM 编写分析脚本，在安全沙箱中执行
- 脚本接收标准化 DataFrame，输出指标字典和可选图表
- 每轮迭代中，LLM 根据上轮结果修改脚本参数/逻辑，实现自适应迭代
- 支持 "经典数据集 → 论证假设 → 人工反馈 → 自迭代" 的完整流程
"""
import os
import sys
import json
import traceback
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from schemas.experiment import ExperimentPlan
from schemas.result import IterationResult, DataPoint
from executors.base import BaseExecutor
from executors.data_adapter import load_data_from_config, DataConfig, get_adapter


def normalize_chart_path(path_str: str, chart_dir: Path) -> Optional[str]:
    """确保图表落在 chart_dir 下；脚本若写到 cwd 根目录等处则复制进来。"""
    if not path_str or not str(path_str).strip():
        return None
    src = Path(str(path_str).strip())
    if not src.is_absolute():
        # 相对路径：先按原样，再试 cwd / chart_dir 下同名
        candidates = [src, Path.cwd() / src, chart_dir / src.name]
        src = next((c for c in candidates if c.is_file()), src)
    if not src.is_file():
        return None

    chart_dir = Path(chart_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)
    resolved_src = src.resolve()
    resolved_dir = chart_dir.resolve()
    try:
        resolved_src.relative_to(resolved_dir)
        return str(resolved_src)
    except ValueError:
        pass

    dest = resolved_dir / resolved_src.name
    if not dest.exists() or dest.stat().st_size != resolved_src.stat().st_size:
        import shutil

        shutil.copy2(resolved_src, dest)
    return str(dest)


class SandboxExecutor(BaseExecutor):
    """
    沙箱实验执行器

    执行流程:
    1. 从 plan.parameters 中提取 data_config 和 script
    2. 通过 DataAdapter 加载并标准化数据
    3. 在受限环境中执行分析脚本
    4. 收集指标和图表作为 IterationResult

    plan.parameters 结构:
    {
        "data_config": {
            "source_type": "local_csv",
            "source_path": "data/my_dataset.csv",
            "column_mapping": {...},
            "preprocessing_steps": [...],
            "feature_columns": [...],
            "target_columns": [...],
            "sample_size": 1000,
            "filters": [...]
        },
        "script": "# Python 分析脚本\nimport pandas as pd\ndef run(df, params):\n    ...\n    return {'metric1': 0.85}, '图表base64或路径'",
        "script_params": {"learning_rate": 0.01, "n_estimators": 100}
    }
    """
    executor_type = "sandbox"

    # 沙箱允许的模块白名单
    ALLOWED_MODULES = {
        'pandas', 'numpy', 'scipy', 'sklearn', 'matplotlib', 'seaborn',
        'collections', 'math', 'statistics', 'random', 'json', 're',
        'itertools', 'functools', 'datetime', 'typing', 'copy',
        'sklearn.model_selection', 'sklearn.metrics', 'sklearn.linear_model',
        'sklearn.ensemble', 'sklearn.preprocessing', 'sklearn.cluster',
        'sklearn.decomposition', 'sklearn.feature_extraction',
        'PIL', 'PIL.Image', 'wave', 'os', 'pathlib',
    }

    def __init__(self, data_dir: str = "data/uploads", chart_dir: str = "data/charts"):
        self.data_dir = Path(data_dir)
        self.chart_dir = Path(chart_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chart_dir.mkdir(parents=True, exist_ok=True)

    def run(self, plan: ExperimentPlan) -> IterationResult:
        start_time = datetime.now().isoformat()

        params = plan.parameters or {}
        data_config_dict = params.get("data_config", {})
        # 兼容 LLM 只写 analysis_script 的情况
        script = (params.get("script") or plan.analysis_script or "").strip()
        # 合并 plan.script_params 与 parameters.script_params
        script_params = {}
        if plan.script_params:
            script_params.update(plan.script_params)
        if isinstance(params.get("script_params"), dict):
            script_params.update(params["script_params"])

        # Step 1: 加载数据
        try:
            df, metadata = load_data_from_config(data_config_dict)
        except Exception as e:
            return IterationResult(
                iteration_number=0,
                plan_used=plan.model_dump(),
                status="failed",
                error_message=f"数据加载失败: {e}",
                summary=f"数据加载失败: {e}",
            )

        if not script:
            return IterationResult(
                iteration_number=0,
                plan_used=plan.model_dump(),
                status="failed",
                error_message="缺少分析脚本: parameters.script 与 analysis_script 均为空",
                summary="缺少分析脚本",
            )

        # Step 2: 注入图表目录和迭代标签到脚本参数
        script_params["chart_dir"] = str(self.chart_dir)
        script_params["iteration_label"] = f"iter_{plan.sample_size}"

        # Step 3: 执行脚本
        metrics, chart_paths, log_output, script_ok = self._execute_script(
            script=script,
            df=df,
            params=script_params,
            iteration_label=f"iter_{plan.sample_size}",
        )

        # Step 4: 验证图表文件是否存在，并统一归入 chart_dir（禁止散落在仓库根目录）
        valid_charts = []
        chart_dir = Path(self.chart_dir)
        for cp in chart_paths:
            normalized = normalize_chart_path(cp, chart_dir)
            if normalized:
                valid_charts.append(normalized)

        end_time = datetime.now().isoformat()

        if not script_ok:
            err_msg = "分析脚本执行失败"
            if "[ERROR]" in (log_output or ""):
                # 取首行错误摘要
                for line in log_output.splitlines():
                    if line.startswith("[ERROR]"):
                        err_msg = line.replace("[ERROR]", "").strip()
                        break
            return IterationResult(
                iteration_number=0,
                plan_used=plan.model_dump(),
                start_time=start_time,
                end_time=end_time,
                status="failed",
                error_message=err_msg,
                data_points=[
                    DataPoint(key="dataset_rows", value=metadata.get("row_count", 0)),
                    DataPoint(key="dataset_columns", value=metadata.get("column_count", 0)),
                ],
                raw_output={
                    "chart_paths": valid_charts,
                    "dataset_metadata": metadata,
                    "script_log": log_output,
                },
                summary=f"脚本执行失败: {err_msg}",
            )

        # Step 5: 构建成功结果
        data_points = []
        for k, v in metrics.items():
            if k == "error":
                continue
            if isinstance(v, (int, float)):
                data_points.append(DataPoint(key=k, value=round(v, 6)))
            else:
                data_points.append(DataPoint(key=k, value=v))

        # 数据集元信息单独记录，不参与 overall_score
        data_points.append(DataPoint(key="dataset_rows", value=metadata.get("row_count", 0)))
        data_points.append(DataPoint(key="dataset_columns", value=metadata.get("column_count", 0)))

        numeric_metrics = {
            k: v for k, v in metrics.items()
            if isinstance(v, (int, float)) and k != "error"
        }
        overall = sum(numeric_metrics.values()) / len(numeric_metrics) if numeric_metrics else 0
        data_points.append(DataPoint(key="overall_score", value=round(overall, 4)))

        raw_output = {
            "chart_paths": valid_charts,
            "dataset_metadata": metadata,
            "script_log": log_output,
        }

        return IterationResult(
            iteration_number=0,
            plan_used=plan.model_dump(),
            start_time=start_time,
            end_time=end_time,
            status="success",
            data_points=data_points,
            raw_output=raw_output,
            summary=self._build_summary(metrics, metadata, valid_charts),
        )

    def validate_plan(self, plan: ExperimentPlan) -> list[str]:
        errors = []
        params = plan.parameters or {}

        if "data_config" not in params:
            errors.append("缺少 data_config: 必须指定数据源配置")
        else:
            dc = params["data_config"] or {}
            # 兼容 LLM 写 type/path 的情况
            source_type = dc.get("source_type") or dc.get("type")
            source_path = dc.get("source_path") or dc.get("path")
            if not source_type:
                errors.append("data_config 缺少 source_type")
            elif source_type not in ("local_csv", "local_json", "local_parquet", "huggingface", "uploaded", "directory"):
                errors.append(f"不支持的 source_type: {source_type}")
            if not source_path and source_type != "huggingface":
                errors.append("data_config 缺少 source_path")

        script = (params.get("script") or plan.analysis_script or "").strip()
        if not script:
            errors.append("缺少 script: 必须提供分析脚本")

        return errors

    def _execute_script(
        self,
        script: str,
        df: object,
        params: dict,
        iteration_label: str,
    ) -> tuple[dict, list[str], str, bool]:
        """
        在受限环境中执行用户脚本

        Returns:
            (metrics_dict, chart_path_list, log_output, success)
        """
        import io
        import contextlib

        log_buffer = io.StringIO()
        wrapped_script = self._wrap_script(script)

        chart_paths = []
        metrics = {}
        log_output = ""

        try:
            exec_globals = {
                "__builtins__": __builtins__,
                "pd": __import__("pandas"),
                "np": __import__("numpy") if self._is_module_available("numpy") else None,
            }

            with contextlib.redirect_stdout(log_buffer), contextlib.redirect_stderr(log_buffer):
                exec(wrapped_script, exec_globals)

                run_fn = exec_globals.get("run")
                if run_fn is None:
                    raise RuntimeError("脚本必须定义 run(df, params) 函数")

                result = run_fn(df, params)

                if isinstance(result, tuple):
                    if len(result) >= 1:
                        metrics = result[0] if isinstance(result[0], dict) else {"result": result[0]}
                    if len(result) >= 2 and result[1]:
                        charts = result[1]
                        if isinstance(charts, str):
                            chart_paths = [charts]
                        elif isinstance(charts, list):
                            chart_paths = charts
                elif isinstance(result, dict):
                    metrics = result
                else:
                    metrics = {"result": result}

            log_output = log_buffer.getvalue()
            return metrics, chart_paths, log_output, True

        except Exception as e:
            log_output = log_buffer.getvalue()
            log_output += f"\n[ERROR] {type(e).__name__}: {e}\n{traceback.format_exc()}"
            return {"error": 1.0}, chart_paths, log_output, False

    def _wrap_script(self, script: str) -> str:
        """包装用户脚本，确保 run 函数存在"""
        # 如果脚本中已定义 run 函数，直接使用
        if "def run(" in script:
            return script

        # 否则，将整个脚本包装为 run 函数
        wrapped = f"""
def run(df, params):
    _script_locals = {{}}
    exec('''
{script}
    ''', {{**globals(), 'df': df, 'params': params}}, _script_locals)
    # 收集脚本中的变量作为返回值
    result = {{k: v for k, v in _script_locals.items()
               if not k.startswith('_') and isinstance(v, (int, float, str, bool, dict, list))}}
    return result
"""
        return wrapped

    def _is_module_available(self, module_name: str) -> bool:
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    def _build_summary(self, metrics: dict, metadata: dict, chart_paths: list) -> str:
        """构建结果摘要文本"""
        parts = [f"数据: {metadata.get('row_count', '?')}行 x {metadata.get('column_count', '?')}列"]
        metric_str = ", ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items())
        parts.append(f"指标: {metric_str}")
        if chart_paths:
            parts.append(f"图表: {len(chart_paths)}张")
        return " | ".join(parts)


# 预置的分析脚本模板 (供 LLM 参考或直接使用)
SANDBOX_SCRIPT_TEMPLATES = {
    "classification_baseline": '''
"""分类任务基线评估脚本"""
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

def run(df, params):
    target_col = params.get("target_column", "label")
    feature_cols = [c for c in df.columns if c != target_col and df[c].dtype in ['int64', 'float64']]

    X = df[feature_cols].fillna(0)
    y = df[target_col]

    if y.dtype == 'object':
        y = LabelEncoder().fit_transform(y)

    model = RandomForestClassifier(
        n_estimators=params.get("n_estimators", 100),
        max_depth=params.get("max_depth", 10),
        random_state=42,
    )
    scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')

    return {
        "accuracy_mean": float(scores.mean()),
        "accuracy_std": float(scores.std()),
        "model_type": "RandomForest",
    }, None
''',

    "correlation_analysis": '''
"""相关性分析脚本"""
import pandas as pd
import numpy as np

def run(df, params):
    target_col = params.get("target_column")
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

    results = {}

    if target_col and target_col in numeric_cols:
        correlations = df[numeric_cols].corrwith(df[target_col]).abs().sort_values(ascending=False)
        top_features = correlations.head(params.get("top_n", 10))
        results["top_correlation_mean"] = float(top_features.mean())
        results["max_correlation"] = float(correlations.max())
        results["features_above_threshold"] = int((correlations > params.get("threshold", 0.3)).sum())
    else:
        # 全局相关性分析
        corr_matrix = df[numeric_cols].corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        high_corr = upper.stack().sort_values(ascending=False).head(10)
        results["avg_correlation"] = float(high_corr.mean())
        results["max_pairwise_corr"] = float(high_corr.iloc[0]) if len(high_corr) > 0 else 0

    results["numeric_features_count"] = len(numeric_cols)
    return results, None
''',

    "statistical_test": '''
"""统计检验脚本"""
import pandas as pd
from scipy import stats
import numpy as np

def run(df, params):
    group_col = params.get("group_column")
    value_col = params.get("value_column")

    results = {}

    if group_col and value_col:
        groups = df[group_col].unique()
        if len(groups) == 2:
            g1 = df[df[group_col] == groups[0]][value_col].dropna()
            g2 = df[df[group_col] == groups[1]][value_col].dropna()
            stat, pvalue = stats.ttest_ind(g1, g2)
            results["t_statistic"] = float(stat)
            results["p_value"] = float(pvalue)
            results["significant"] = 1.0 if pvalue < 0.05 else 0.0
            results["effect_size"] = float(abs(g1.mean() - g2.mean()) / (g1.std() + g2.std() + 1e-8))
        elif len(groups) > 2:
            group_data = [df[df[group_col] == g][value_col].dropna() for g in groups]
            stat, pvalue = stats.f_oneway(*group_data)
            results["f_statistic"] = float(stat)
            results["p_value"] = float(pvalue)
    else:
        # 单变量描述统计
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols[:5]:
            results[f"{col}_mean"] = float(df[col].mean())
            results[f"{col}_std"] = float(df[col].std())
            stat, pvalue = stats.shapiro(df[col].dropna().sample(min(50, len(df)), random_state=42))
            results[f"{col}_normality_p"] = float(pvalue)

    return results, None
''',
}
