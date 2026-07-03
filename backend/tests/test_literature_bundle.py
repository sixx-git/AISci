"""文献 bundle 归并测试。"""
from app.services.literature_bundle_service import enrich_literature_mining, normalize_literature_bundle


def test_normalize_retrieved_papers_to_facts_and_citations():
    lm = {
        "facts": [],
        "citation_map": [],
        "retrieved_papers": [
            {
                "title": "DNA Origami Nanorobots",
                "authors": ["Alice", "Bob"],
                "year": 2024,
                "abstract": "Nanorobots show targeted delivery in blood models.",
                "arxiv_id": "2401.00001",
            }
        ],
    }
    facts, citation_map, verified = normalize_literature_bundle(lm)
    assert len(facts) == 1
    assert facts[0]["fact_id"] == "paper_fact_001"
    assert facts[0]["source_paper_title"] == "DNA Origami Nanorobots"
    assert len(citation_map) == 1
    assert citation_map[0]["title"] == "DNA Origami Nanorobots"
    assert len(verified) == 1


def test_normalize_pdf_skill_facts():
    lm = {
        "facts": [],
        "citation_map": [],
        "skill_outputs": {
            "pdf_evidence_extraction": {
                "success": True,
                "data": {
                    "facts": [
                        {
                            "fact_id": "evfact_001",
                            "content": "Red blood cell membrane coating improves immune escape.",
                            "chunk_id": "chunk-abc",
                            "document_id": "doc-1",
                            "source_title": "Uploaded Paper",
                        }
                    ]
                },
            }
        },
    }
    facts, _, _ = normalize_literature_bundle(lm)
    assert len(facts) == 1
    assert facts[0]["source_chunk_id"] == "chunk-abc"
    assert facts[0]["source_paper_title"] == "Uploaded Paper"


def test_enrich_updates_counts():
    lm = enrich_literature_mining(
        {
            "facts": [],
            "retrieved_papers": [
                {"title": "Paper A", "abstract": "Finding A about nanorobots."},
                {"title": "Paper B", "abstract": "Finding B about drug delivery."},
            ],
        }
    )
    assert lm["evidence_facts"] == 2
    assert lm["verified_references_count"] == 2
    assert len(lm["facts"]) == 2


def test_source_papers_string_titles():
    lm = {
        "facts": [],
        "citation_map": [],
        "source_papers": ["Membrane-coated nanoparticles", "DNA nanotechnology review"],
    }
    facts, citation_map, _ = normalize_literature_bundle(lm)
    assert len(citation_map) == 2
    assert facts == []
