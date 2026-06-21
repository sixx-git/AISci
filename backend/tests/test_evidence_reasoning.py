"""证据链推理 Skill 集成测试"""
import asyncio
import os
import tempfile
import unittest

from app.services.evidence_reasoning_service import EvidenceReasoningService
from app.skills.evidence_reasoning.counter_evidence_retrieval_skill import CounterEvidenceRetrievalSkill
from app.skills.evidence_reasoning.evidence_retrieval_skill import EvidenceRetrievalSkill
from app.skills.evidence_reasoning.iterative_hypothesis_loop_skill import IterativeHypothesisLoopSkill


MOCK_FACTS = [
    {
        "fact_id": "f1",
        "content": "Transformer attention improves protein structure prediction accuracy",
        "source_paper_title": "AlphaFold2: Accurate protein structure prediction",
        "document_id": "doc-1",
        "source_chunk_id": "c1",
        "year": 2021,
        "doi": "10.1038/s41586-021-03819-2",
    },
    {
        "fact_id": "f2",
        "content": "Graph neural networks capture spatial relationships in molecular data",
        "source_paper_title": "Graph neural networks for molecular property prediction",
        "document_id": "doc-2",
        "source_chunk_id": "c2",
        "year": 2020,
    },
    {
        "fact_id": "f3",
        "content": "A major limitation is that the model fails on rare protein folds",
        "source_paper_title": "Limitations of deep learning in structural biology",
        "document_id": "doc-3",
        "source_chunk_id": "c3",
        "year": 2022,
    },
]

MOCK_CITATION_MAP = [
    {"document_id": "doc-1", "paper_title": "AlphaFold2: Accurate protein structure prediction", "source_type": "paper"},
    {"document_id": "doc-2", "paper_title": "Graph neural networks for molecular property prediction", "source_type": "paper"},
    {"document_id": "doc-3", "paper_title": "Limitations of deep learning in structural biology", "source_type": "paper"},
]

MOCK_LITERATURE = {
    "facts": MOCK_FACTS,
    "citation_map": MOCK_CITATION_MAP,
    "uncertain_points": [],
    "imported_documents": [],
    "retrieved_papers": [],
}


class TestEvidenceReasoningSkills(unittest.TestCase):
    def test_support_evidence_has_verifiable_sources(self):
        skill = EvidenceRetrievalSkill()
        result = asyncio.run(
            skill.run(
                {
                    "hypothesis": "Graph neural networks improve protein structure prediction",
                    "research_question": "How can GNN improve protein structure prediction?",
                    "facts": MOCK_FACTS,
                    "citation_map": MOCK_CITATION_MAP,
                    "imported_papers": [],
                    "uploaded_pdfs": [],
                    "bibtex_docs": [],
                },
                {},
            )
        )
        supporting = result.data.get("supporting_evidence", [])
        self.assertGreaterEqual(len(supporting), 1)
        for ev in supporting:
            self.assertTrue(ev.get("source_title") or ev.get("paper_id"))
            self.assertNotIn((ev.get("source_title") or "").lower(), {"unknown", "placeholder"})

    def test_counter_evidence_empty_when_no_literature(self):
        skill = CounterEvidenceRetrievalSkill()
        result = asyncio.run(
            skill.run(
                {
                    "hypothesis": "Test hypothesis",
                    "facts": MOCK_FACTS[:2],
                    "citation_map": MOCK_CITATION_MAP[:2],
                    "uncertain_points": [],
                },
                {},
            )
        )
        self.assertEqual(result.data.get("count"), 0)
        self.assertIn("文献不足", result.data.get("empty_reason", ""))

    def test_counter_evidence_finds_limitation(self):
        skill = CounterEvidenceRetrievalSkill()
        result = asyncio.run(
            skill.run(
                {
                    "hypothesis": "Deep learning always succeeds in structure prediction",
                    "facts": MOCK_FACTS,
                    "citation_map": MOCK_CITATION_MAP,
                    "uncertain_points": [],
                },
                {},
            )
        )
        counter = result.data.get("counter_evidence", [])
        self.assertGreaterEqual(len(counter), 1)
        self.assertEqual(counter[0].get("stance"), "refute")

    def test_iterative_loop_builds_chain(self):
        skill = IterativeHypothesisLoopSkill()
        result = asyncio.run(
            skill.run(
                {
                    "hypothesis": "Graph neural networks improve protein structure prediction",
                    "rationale": "Literature suggests GNN and attention help structure tasks",
                    "research_question": "How can GNN improve protein structure prediction?",
                    "facts": MOCK_FACTS,
                    "citation_map": MOCK_CITATION_MAP,
                    "uncertain_points": [],
                    "imported_papers": [],
                    "uploaded_pdfs": [],
                    "bibtex_docs": [],
                    "max_rounds": 1,
                },
                {},
            )
        )
        chain = result.data.get("evidence_chain", {})
        self.assertIn("supporting_evidence", chain)
        self.assertIn("counter_evidence", chain)
        self.assertIn("final_version", chain)
        self.assertGreaterEqual(len(chain.get("supporting_evidence", [])), 1)

    def test_service_persists_chain(self):
        service = EvidenceReasoningService()
        with tempfile.TemporaryDirectory() as tmp:
            service.storage_root = tmp
            hypo = {
                "id": "hypo-test",
                "hypothesis": "Graph neural networks improve protein structure prediction",
                "rationale": "Based on literature",
            }
            result = asyncio.run(
                service.run_for_hypothesis(hypo, "GNN for proteins?", MOCK_LITERATURE, max_rounds=1)
            )
            self.assertTrue(result.get("success"))
            chain = result.get("evidence_chain", {})
            self.assertGreaterEqual(chain.get("support_count", 0), 1)

            path = service.save_evidence_chain("proj-test", "hypo-test", chain)
            self.assertTrue(os.path.exists(path))
            loaded = service.load_evidence_chain("proj-test", "hypo-test")
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded.get("supporting_evidence", [])), len(chain.get("supporting_evidence", [])))


if __name__ == "__main__":
    unittest.main()
