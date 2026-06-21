"""双模式（general / federated_learning）测试"""
import asyncio
import os
import tempfile
import unittest

import pandas as pd

from app.core.project_modes import (
    ProjectMode,
    get_research_question_template,
    normalize_project_mode,
)
from app.services.federated_experiment_service import FederatedExperimentService
from app.skills.federated_experiment.federated_data_schema_skill import FederatedDataSchemaSkill
from app.skills.federated_experiment.federated_simulation_executor_skill import (
    FederatedSimulationExecutorSkill,
)


class TestProjectModes(unittest.TestCase):
    def test_normalize_defaults_to_general(self):
        self.assertEqual(normalize_project_mode(None), ProjectMode.GENERAL.value)
        self.assertEqual(normalize_project_mode("invalid"), ProjectMode.GENERAL.value)

    def test_fl_research_template(self):
        tpl = get_research_question_template(ProjectMode.FEDERATED_LEARNING.value)
        self.assertIn("Non-IID", tpl["research_question"])
        self.assertIn("FedAvg", tpl["keywords"])

    def test_fl_schema_detection(self):
        columns = [
            "client_id", "method", "non_iid_degree", "global_accuracy",
            "f1_score", "communication_cost_mb", "client_drift",
        ]
        skill = FederatedDataSchemaSkill()
        result = asyncio.run(skill.run({"columns": columns}, {}))
        data = result.data
        self.assertEqual(data["project_mode"], ProjectMode.FEDERATED_LEARNING.value)
        self.assertIn("method", [f.lower() for f in data["detected_fields"]])
        self.assertGreaterEqual(len(data["metrics_fields"]), 3)

    def test_fl_csv_pilot_analysis(self):
        df = pd.DataFrame([
            {"method": "FedAvg", "non_iid_degree": 0.5, "global_accuracy": 0.82, "f1_score": 0.79, "communication_cost_mb": 120, "client_drift": 0.12},
            {"method": "FedProx", "non_iid_degree": 0.5, "global_accuracy": 0.85, "f1_score": 0.81, "communication_cost_mb": 130, "client_drift": 0.10},
            {"method": "SCAFFOLD", "non_iid_degree": 0.5, "global_accuracy": 0.87, "f1_score": 0.83, "communication_cost_mb": 140, "client_drift": 0.08},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fl_results.csv")
            df.to_csv(path, index=False)
            fl_context = asyncio.run(
                FederatedDataSchemaSkill().run({"columns": list(df.columns)}, {})
            ).data
            skill = FederatedSimulationExecutorSkill()
            pilot = asyncio.run(
                skill.run(
                    {
                        "datasets": [{"file_path": path, "data_type": "tabular", "filename": "fl_results.csv"}],
                        "fl_context": fl_context,
                        "experiment_plan": {"baselines": ["FedAvg", "FedProx"]},
                    },
                    {},
                )
            ).data
            self.assertEqual(pilot["execution_mode"], "uploaded_csv")
            self.assertEqual(pilot["best_method"], "SCAFFOLD")
            self.assertGreaterEqual(len(pilot["metric_comparison"]), 2)

    def test_fl_experiment_plan(self):
        service = FederatedExperimentService()
        fl_context = {
            "fl_setting": "horizontal_fl",
            "detected_fields": ["method", "global_accuracy"],
            "metrics_fields": ["global_accuracy", "f1_score"],
        }
        plan = asyncio.run(service.build_experiment_plan("FedAvg improves accuracy under Non-IID", fl_context))
        self.assertIn("FedAvg", plan.get("baselines", []))
        self.assertIn("f1_score", plan.get("metrics", []))
        design = service.build_experiment_design_result("test hypo", fl_context, plan)
        self.assertEqual(design["project_mode"], ProjectMode.FEDERATED_LEARNING.value)


if __name__ == "__main__":
    unittest.main()
