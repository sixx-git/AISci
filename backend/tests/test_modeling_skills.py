"""建模 Skill 集成测试"""
import os
import tempfile
import unittest

from app.services.modeling_service import ModelingService


class TestModelingPipeline(unittest.TestCase):
    def test_modeling_pipeline_on_csv(self):
        try:
            import pandas as pd
            from sklearn.datasets import make_classification
        except ImportError:
            self.skipTest("缺少 pandas 或 scikit-learn")

        X, y = make_classification(
            n_samples=200,
            n_features=6,
            n_informative=4,
            n_redundant=0,
            random_state=42,
        )
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
        df["target"] = y

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "sample.csv")
            df.to_csv(csv_path, index=False)

            class FakeDataset:
                id = "ds-test"
                project_id = "proj-test"
                data_type = "tabular"
                file_path = csv_path
                extra_metadata = None

            class FakeQuery:
                def filter(self, *args, **kwargs):
                    return self

                def first(self):
                    return FakeDataset()

                def all(self):
                    return []

            class FakeDB:
                def query(self, model):
                    return FakeQuery()

                def commit(self):
                    pass

            service = ModelingService(FakeDB())
            service.save_result = lambda project_id, dataset_id, payload: os.path.join(tmp, "result.json")
            service._update_dataset_metadata = lambda ds, payload: None

            import asyncio

            result = asyncio.run(
                service.run_modeling_pipeline(
                    dataset_id="ds-test",
                    target_column="target",
                    research_task="分类验证",
                )
            )

            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("target_column"), "target")
            self.assertTrue(result.get("best_model"))
            self.assertGreaterEqual(len(result.get("models", [])), 1)
            self.assertGreaterEqual(len(result.get("self_correction_suggestions", [])), 1)


if __name__ == "__main__":
    unittest.main()
