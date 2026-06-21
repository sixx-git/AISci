"""知识图谱模块测试"""
import asyncio
import unittest

from app.skills.knowledge_graph.evidence_graph_builder_skill import EvidenceGraphBuilderSkill
from app.skills.knowledge_graph.graph_reasoning_skill import GraphReasoningSkill
from app.skills.knowledge_graph.kg_quality_review_skill import KgQualityReviewSkill
from app.skills.knowledge_graph.kg_schema_generation_skill import KgSchemaGenerationSkill
from app.skills.knowledge_graph.scientific_entity_extraction_skill import ScientificEntityExtractionSkill
from app.skills.knowledge_graph.scientific_relation_extraction_skill import ScientificRelationExtractionSkill


SAMPLE_FACTS = [
    {
        "fact_id": "f1",
        "content": "FedAvg evaluates on CIFAR-10 with global accuracy 82%.",
        "source_paper_title": "Communication-Efficient Learning",
        "document_id": "doc1",
        "page_number": 3,
    },
    {
        "fact_id": "f2",
        "content": "FedProx improves performance under Non-IID client distribution.",
        "source_paper_title": "FedProx Paper",
        "document_id": "doc2",
        "page_number": 5,
    },
    {
        "fact_id": "f3",
        "content": "SCaffold reduces client drift measured by drift metric.",
        "source_paper_title": "SCAFFOLD Study",
        "document_id": "doc3",
    },
]

SAMPLE_CITATION = [
    {"document_id": "doc1", "paper_title": "Communication-Efficient Learning", "year": 2017},
    {"document_id": "doc2", "paper_title": "FedProx Paper", "year": 2020},
]


class TestKnowledgeGraphSkills(unittest.TestCase):
    def test_schema_general(self):
        skill = KgSchemaGenerationSkill()
        res = asyncio.run(skill.run({"project_mode": "general"}, {}))
        types = res.data["schema"]["node_types"]
        self.assertIn("Paper", types)
        self.assertIn("Hypothesis", types)

    def test_schema_fl_extra(self):
        skill = KgSchemaGenerationSkill()
        res = asyncio.run(skill.run({"project_mode": "federated_learning"}, {}))
        rels = res.data["schema"]["relation_types"]
        self.assertIn("algorithm_handles_non_iid", rels)
        self.assertIn("FedAlgorithm", res.data["schema"]["node_types"])

    def test_entity_extraction_requires_source(self):
        skill = ScientificEntityExtractionSkill()
        res = asyncio.run(
            skill.run(
                {
                    "facts": SAMPLE_FACTS,
                    "citation_map": SAMPLE_CITATION,
                    "hypotheses": [{"id": "h1", "hypothesis": "FedProx mitigates Non-IID"}],
                },
                {},
            )
        )
        entities = res.data["entities"]
        self.assertGreater(len(entities), 0)
        for e in entities:
            self.assertTrue(e.get("source_ids"))
        labels = [e["label"] for e in entities if e["type"] == "Method"]
        self.assertTrue(any("FedAvg" in l or "FedProx" in l for l in labels))

    def test_relation_extraction(self):
        entity_skill = ScientificEntityExtractionSkill()
        entity_res = asyncio.run(
            entity_skill.run({"facts": SAMPLE_FACTS, "citation_map": SAMPLE_CITATION}, {})
        )
        entities = entity_res.data["entities"]
        rel_skill = ScientificRelationExtractionSkill()
        rel_res = asyncio.run(
            rel_skill.run({"entities": entities, "facts": SAMPLE_FACTS}, {})
        )
        edges = rel_res.data["edges"]
        self.assertGreater(len(edges), 0)
        for e in edges:
            self.assertTrue(e.get("evidence"))
            self.assertTrue(e.get("source_title"))
        relations = {e["relation"] for e in edges}
        self.assertTrue(relations & {"evaluates_on", "uses", "measured_by", "cites"})

    def test_graph_reasoning_non_iid(self):
        entity_skill = ScientificEntityExtractionSkill()
        entities = asyncio.run(
            entity_skill.run({"facts": SAMPLE_FACTS, "citation_map": SAMPLE_CITATION}, {})
        ).data["entities"]
        rel_skill = ScientificRelationExtractionSkill()
        edges = asyncio.run(
            rel_skill.run({"entities": entities, "facts": SAMPLE_FACTS}, {})
        ).data["edges"]
        graph = {"nodes": entities, "edges": edges}
        skill = GraphReasoningSkill()
        res = asyncio.run(
            skill.run({"query": "哪些方法可以缓解 Non-IID？", "graph": graph}, {})
        )
        self.assertIn("Non-IID", res.data.get("answer", "") + str(res.data.get("graph_paths")))

    def test_quality_review(self):
        graph = {
            "nodes": [
                {"id": "a", "type": "Method", "label": "FedAvg", "source_ids": ["f1"]},
                {"id": "b", "type": "Dataset", "label": "CIFAR-10", "source_ids": ["f1"]},
                {"id": "c", "type": "Paper", "label": "Orphan", "source_ids": ["doc9"]},
            ],
            "edges": [
                {
                    "id": "e1", "source": "a", "target": "b", "relation": "evaluates_on",
                    "evidence": "test", "source_title": "Paper A", "confidence": 0.3,
                },
            ],
            "candidate_edges": [],
        }
        skill = KgQualityReviewSkill()
        res = asyncio.run(skill.run({"graph": graph}, {}))
        qr = res.data["quality_report"]
        self.assertGreaterEqual(qr["isolated_count"], 1)
        self.assertGreaterEqual(qr["low_confidence_count"], 1)

    def test_evidence_graph_builder(self):
        skill = EvidenceGraphBuilderSkill()
        res = asyncio.run(
            skill.run(
                {
                    "hypotheses": [{
                        "id": "h1",
                        "hypothesis": "FedProx helps Non-IID",
                        "evidence_chain": {
                            "supporting_evidence": [{
                                "evidence_id": "ev1",
                                "claim": "FedProx outperforms FedAvg",
                                "source_title": "FedProx Paper",
                                "stance": "support",
                                "relevance_score": 0.8,
                            }],
                            "counter_evidence": [],
                        },
                    }],
                },
                {},
            )
        )
        evg = res.data["evidence_graph"]
        self.assertGreater(len(evg["nodes"]), 0)
        self.assertTrue(any(e["relation"] == "supports" for e in evg["edges"]))

    def test_community_summary(self):
        from app.skills.knowledge_graph.graph_community_summary_skill import GraphCommunitySummarySkill

        graph = {
            "nodes": [
                {"id": "a", "type": "Method", "label": "FedAvg", "source_ids": ["f1"]},
                {"id": "b", "type": "Dataset", "label": "CIFAR-10", "source_ids": ["f1"]},
                {"id": "c", "type": "Paper", "label": "Paper A", "source_ids": ["doc1"]},
            ],
            "edges": [
                {"source": "a", "target": "b", "relation": "evaluates_on"},
                {"source": "c", "target": "a", "relation": "cites"},
            ],
        }
        skill = GraphCommunitySummarySkill()
        res = asyncio.run(skill.run({"graph": graph, "research_question": "FL on CIFAR"}, {}))
        self.assertGreaterEqual(res.data["community_count"], 1)
        self.assertTrue(res.data["communities"][0].get("summary"))

    def test_explanation_education_levels(self):
        from app.skills.knowledge_graph.kg_explanation_skill import KgExplanationSkill

        skill = KgExplanationSkill()
        res = asyncio.run(
            skill.run(
                {
                    "query": "什么是 FedAvg？",
                    "graph": {"nodes": [], "edges": []},
                    "graph_paths": [["FedAvg", "evaluates_on", "CIFAR-10"]],
                    "supporting_sources": ["Paper A"],
                    "raw_answer": "找到 1 条关系",
                    "education_level": "primary",
                },
                {},
            )
        )
        self.assertIn("FedAvg", res.data["answer"])

    def test_incremental_update(self):
        from app.skills.knowledge_graph.incremental_graph_update_skill import IncrementalGraphUpdateSkill

        graph = {
            "nodes": [{"id": "n1", "type": "Method", "label": "FedAvg", "source_ids": ["f0"]}],
            "edges": [],
            "candidate_edges": [],
        }
        skill = IncrementalGraphUpdateSkill()
        res = asyncio.run(
            skill.run(
                {
                    "graph": graph,
                    "new_facts": [{
                        "fact_id": "f_new",
                        "content": "FedProx improves on FEMNIST under Non-IID.",
                        "source_paper_title": "FedProx Paper",
                    }],
                },
                {},
            )
        )
        self.assertGreaterEqual(res.data["incremental"]["added_nodes"], 0)


if __name__ == "__main__":
    unittest.main()
