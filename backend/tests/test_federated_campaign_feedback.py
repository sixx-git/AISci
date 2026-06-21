"""联邦 Campaign 反馈注入实验计划测试"""
import unittest

from app.services.federated_experiment_service import FederatedExperimentService


class TestFederatedCampaignFeedback(unittest.TestCase):
    def test_apply_campaign_feedback_injects_steps(self):
        svc = FederatedExperimentService()
        plan = {
            "baselines": ["SplitNN", "VFL-LR"],
            "metrics": ["accuracy"],
            "experimental_steps": ["step1"],
            "methods_summary": "VFL plan",
        }
        actions = [
            {
                "action_id": "vfl_alignment_retry",
                "parameter": "aligned_sample_rate",
                "to_value": 0.95,
                "expected_check": "alignment_success_rate >= 0.85",
                "priority": "critical",
            }
        ]
        updated = svc.apply_campaign_feedback(
            plan,
            validation_feedback=["上一轮 gate 未通过"],
            replan_actions=actions,
            campaign_round=2,
        )
        steps = updated.get("experimental_steps") or []
        self.assertTrue(any("Campaign R2" in s for s in steps))
        self.assertTrue(any("vfl_alignment_retry" in s for s in steps))
        self.assertIn("Campaign R2", updated.get("methods_summary", ""))


if __name__ == "__main__":
    unittest.main()
