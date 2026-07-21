"""文献 bundle 归并测试。"""
from unittest.mock import MagicMock, patch

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
                "gate_passed": True,
                "relevance_score": 8,
            }
        ],
    }
    facts, citation_map, verified = normalize_literature_bundle(lm)
    assert len(facts) == 1
    assert facts[0]["fact_id"] == "paper_fact_001"
    assert facts[0]["source_paper_title"] == "DNA Origami Nanorobots"
    assert len(citation_map) == 1
    assert citation_map[0]["title"] == "DNA Origami Nanorobots"
    assert citation_map[0].get("document_id")  # 外部论文也须有稳定 document_id
    assert len(verified) == 1


def test_source_paper_title_only_gets_synthetic_document_id():
    """回归：仅标题的 source_papers 补入 citation_map 时不得缺 document_id。"""
    from app.agents.literature_mining_agent import LiteratureMiningResponse

    lm = {
        "facts": [
            {
                "fact_id": "f1",
                "content": "Aging hallmarks include genomic instability.",
                "source_chunk_id": "c1",
                "document_id": "doc-1",
            }
        ],
        "citation_map": [{"document_id": "doc-1", "title": "Local Paper", "paper_title": "Local Paper"}],
        "source_papers": [
            "The Hallmarks of Aging",
            "Hallmarks of aging: An expanding universe",
        ],
    }
    enriched = enrich_literature_mining(lm)
    assert all(c.get("document_id") for c in enriched["citation_map"])
    # 必须能通过 LiteratureMiningResponse 校验（此前在此抛 validation error）
    resp = LiteratureMiningResponse(**{**lm, **enriched})
    assert len(resp.citation_map) >= 2


def test_low_score_abstract_not_promoted_to_fact():
    lm = {
        "facts": [],
        "citation_map": [],
        "retrieved_papers": [
            {
                "title": "Unrelated Paper",
                "abstract": "Something about baking bread.",
                "relevance_score": 2,
                "gate_passed": False,
            }
        ],
    }
    with patch("app.core.config.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(
            LIT_RELEVANCE_GATE_ENABLED=True,
            LIT_PAPER_SCORE_CUTOFF=6,
        )
        facts, citation_map, _ = normalize_literature_bundle(lm)
    assert facts == []
    assert len(citation_map) == 1


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
                {
                    "title": "Paper A",
                    "abstract": "Finding A about nanorobots.",
                    "gate_passed": True,
                    "relevance_score": 8,
                },
                {
                    "title": "Paper B",
                    "abstract": "Finding B about drug delivery.",
                    "gate_passed": True,
                    "relevance_score": 7,
                },
            ],
        }
    )
    assert lm["evidence_facts"] == 2
    assert lm["verified_references_count"] == 2
    assert len(lm["facts"]) == 2


def test_enrich_gate_disabled_keeps_legacy_abstract_facts():
    with patch("app.core.config.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(
            LIT_RELEVANCE_GATE_ENABLED=False,
            LIT_PAPER_SCORE_CUTOFF=6,
        )
        lm = enrich_literature_mining(
            {
                "facts": [],
                "retrieved_papers": [
                    {"title": "Paper A", "abstract": "Finding A about nanorobots."},
                ],
            }
        )
    assert lm["evidence_facts"] == 1


def test_source_papers_string_titles():
    lm = {
        "facts": [],
        "citation_map": [],
        "source_papers": ["Membrane-coated nanoparticles", "DNA nanotechnology review"],
    }
    facts, citation_map, _ = normalize_literature_bundle(lm)
    assert len(citation_map) == 2
    assert facts == []


def test_merge_project_library_into_empty_mining():
    from app.services.literature_bundle_service import merge_project_library_into_literature_mining

    class _Doc:
        id = "doc-1"
        title = "Plastic Waste Governance"
        filename = "plastic.pdf"
        authors = "Alice, Bob"
        publication_date = "2024-01-01"
        doi = "10.1000/test"
        abstract = "Global plastic waste flows remain opaque."
        summary = ""
        source_url = None
        pdf_url = None
        external_id = None
        source_type = "upload"
        created_at = None
        extra_metadata = None

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return [_Doc()]

        def count(self):
            return 1

    class _DB:
        def query(self, *a, **k):
            return _Q()

    lm = merge_project_library_into_literature_mining(
        {"facts": [], "citation_map": []},
        db=_DB(),
        project_id="proj-1",
    )
    assert lm["project_library_document_count"] == 1
    assert len(lm["citation_map"]) == 1
    assert lm["citation_map"][0]["title"] == "Plastic Waste Governance"
    assert len(lm["verified_references"]) == 1
    assert any(f.get("source") == "project_library" for f in lm["facts"])


def test_merge_uploaded_pdf_chunks_into_facts_without_abstract():
    """手动上传 PDF 常无 abstract：应用解析 chunk 回填假设生成 facts。"""
    from app.services.literature_bundle_service import merge_project_library_into_literature_mining

    class _Doc:
        id = "doc-upload"
        title = "Marine Plastic Governance"
        filename = "upload.pdf"
        authors = "A"
        publication_date = None
        doi = None
        abstract = ""
        summary = ""
        source_url = None
        pdf_url = None
        external_id = None
        source_type = "upload"
        created_at = None
        extra_metadata = None

    class _Chunk:
        id = "chunk-1"
        document_id = "doc-upload"
        chunk_index = 0
        content = (
            "Global marine plastic pollution requires coordinated international law "
            "and extended producer responsibility schemes across coastal states."
        )
        page_number = 1

    class _Q:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class _DB:
        def query(self, model):
            name = getattr(model, "__name__", str(model))
            if "Chunk" in name:
                return _Q([_Chunk()])
            return _Q([_Doc()])

    lm = merge_project_library_into_literature_mining(
        {"facts": [], "citation_map": []},
        db=_DB(),
        project_id="proj-upload",
    )
    assert len(lm["citation_map"]) == 1
    chunk_facts = [f for f in lm["facts"] if f.get("source") == "project_library_chunk"]
    assert len(chunk_facts) >= 1
    assert "marine plastic" in chunk_facts[0]["content"].lower()
    assert chunk_facts[0]["document_id"] == "doc-upload"


def test_project_documents_prefer_pdf_metadata_over_polluted_title():
    from app.services.literature_bundle_service import project_documents_as_citations

    class _Doc:
        id = "doc-2"
        title = "Industrial Marketing Management 102 (2022) 164–76"
        filename = "main.pdf"
        authors = ". Published by Elsevier Inc. This is an open access article under the CC BY license"
        publication_date = None
        doi = None
        abstract = ""
        source_url = None
        pdf_url = None
        external_id = None
        source_type = "upload"
        created_at = None
        extra_metadata = {
            "pdf_metadata": {
                "title": "Blockchain application in circular marine plastic debris management",
                "author": "Yu Gong",
            }
        }

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return [_Doc()]

    class _DB:
        def query(self, *a, **k):
            return _Q()

    entries = project_documents_as_citations(_DB(), "proj-1")
    assert len(entries) == 1
    assert entries[0]["title"].startswith("Blockchain application")
    assert entries[0]["authors"] == "Yu Gong"
