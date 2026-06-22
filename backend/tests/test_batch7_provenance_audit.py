"""Batch 7 — 假设溯源 / LLM 修订 / 审计链 / data_citation"""
import csv
import os
import tempfile
import unittest

from app.core.data_citation import collect_citation_ids_from_hypothesis, resolve_data_citation
from app.core.hypothesis_provenance import build_hypothesis_provenance_timeline
from app.services.audit_chain_service import AuditChainService
from app.skills.data_finder.dataset_merge_skill import DatasetMergeSkill
from app.skills.evidence_reasoning.hypothesis_revision_skill import HypothesisRevisionSkill


class TestBatch7ProvenanceTimeline(unittest.TestCase):
    def test_timeline_steps(self):
        facts = [
            {
                "fact_id": "f1",
                "content": "FL improves accuracy",
                "source_paper_title": "Paper A",
                "document_id": "doc_1",
                "chunk_id": "chunk_1",
            }
        ]
        hypo = {
            "supporting_fact_ids": ["f1"],
            "data_evidence_ids": ["mm_1"],
            "dataset_field_refs": ["accuracy", "cite_abc123"],
            "data_citation_ids": ["cite_abc123"],
            "verifiable_spec": {"claim": "H", "primary_metric": "accuracy"},
        }
        row_prov = [{"data_citation_id": "cite_abc123", "table_row_id": "t1_row_1", "source_title": "Paper A"}]
        timeline = build_hypothesis_provenance_timeline(
            hypo,
            facts=facts,
            multimodal_facts=[{"fact_id": "mm_1", "modality": "image", "content": "chart up"}],
            row_provenance=row_prov,
        )
        steps = [t["step"] for t in timeline]
        self.assertIn("literature_facts", steps)
        self.assertIn("multimodal", steps)
        self.assertIn("dataset", steps)
        self.assertIn("verifiable_spec", steps)
        lit = next(t for t in timeline if t["step"] == "literature_facts")
        self.assertEqual(lit["items"][0]["document_id"], "doc_1")


class TestBatch7HypothesisRevision(unittest.IsolatedAsyncioTestCase):
    async def test_rule_fallback_revision(self):
        skill = HypothesisRevisionSkill()
        res = await skill.run(
            {
                "hypothesis": "联邦学习提升准确率",
                "supporting_evidence": [{"stance": "support", "source_title": "Paper", "claim": "good"}],
                "counter_evidence": [{"stance": "refute", "claim": "non-iid hurts"}],
            },
            {},
        )
        data = res.data or {}
        self.assertIn("revised_hypothesis", data)
        self.assertTrue(data.get("revision_mode") in ("rule", "llm"))


class TestBatch7AuditChain(unittest.TestCase):
    def test_append_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = AuditChainService(storage_root=tmp)
            svc.append_record("run_1", "closed_loop_event", {"type": "discovery_r2", "score": 7.5})
            svc.append_record("run_1", "quality_trend_entry", {"stage": "discovery_r2", "score": 7.5})
            chain = svc.read_chain("run_1")
            self.assertEqual(len(chain), 2)
            bundle = svc.export_audit_bundle(
                "run_1",
                meta={"quality_trend": [{"stage": "a"}], "closed_loop_events": [], "closed_loop_decisions": []},
            )
            self.assertEqual(bundle["record_count"], 2)
            self.assertEqual(len(bundle["quality_trend"]), 1)


class TestBatch7DataCitation(unittest.IsolatedAsyncioTestCase):
    async def test_merge_row_citation_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "t1.csv")
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["x", "y"])
                w.writerow(["1", "2"])

            skill = DatasetMergeSkill()
            res = await skill.run(
                {
                    "tables": [{
                        "table_id": "tbl_1",
                        "csv_path": csv_path,
                        "source_title": "Paper",
                    }],
                    "alignments": [{"table_id": "tbl_1", "mapping": {}}],
                    "provenance": [{"record_id": "tbl_1", "source_title": "Paper"}],
                    "output_dir": tmp,
                },
                {},
            )
            data = res.data or {}
            self.assertEqual(data.get("row_count"), 1)
            row_prov = data.get("row_provenance") or []
            self.assertEqual(len(row_prov), 1)
            self.assertTrue(row_prov[0].get("data_citation_id", "").startswith("cite_"))
            self.assertTrue(row_prov[0].get("table_row_id", "").startswith("tbl_1_row_"))

    def test_resolve_citation(self):
        prov = [{"data_citation_id": "cite_x", "source_title": "T"}]
        row = [{"data_citation_id": "cite_y", "table_row_id": "r1", "source_title": "Row"}]
        hit = resolve_data_citation("cite_y", provenance=prov, row_provenance=row)
        self.assertEqual(hit.get("level"), "row")
        hypo = {"dataset_field_refs": ["cite_x"], "data_citation_ids": ["cite_y"]}
        ids = collect_citation_ids_from_hypothesis(hypo)
        self.assertIn("cite_x", ids)
        self.assertIn("cite_y", ids)


if __name__ == "__main__":
    unittest.main()
