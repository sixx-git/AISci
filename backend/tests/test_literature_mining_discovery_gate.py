"""文献挖掘：本地文献足够跳过 discovery；检索无结果不再二次 discovery。"""
from unittest.mock import MagicMock, patch

from app.agents.literature_mining_agent import LiteratureMiningAgent, LiteratureMiningResponse


def test_should_run_discovery_false_when_enough_docs():
    agent = LiteratureMiningAgent()
    db = MagicMock()
    doc_q = MagicMock()
    doc_q.filter.return_value.filter.return_value.count.return_value = 5
    proj_q = MagicMock()
    proj = MagicMock()
    proj.config = {}
    proj_q.filter.return_value.first.return_value = proj
    db.query.side_effect = [doc_q, proj_q]

    assert agent._should_run_literature_discovery(db, "proj-1") is False


def test_should_run_discovery_true_when_few_docs():
    agent = LiteratureMiningAgent()
    db = MagicMock()
    doc_q = MagicMock()
    doc_q.filter.return_value.filter.return_value.count.return_value = 1
    proj_q = MagicMock()
    proj = MagicMock()
    proj.config = {}
    proj_q.filter.return_value.first.return_value = proj
    db.query.side_effect = [doc_q, proj_q]

    assert agent._should_run_literature_discovery(db, "proj-1") is True


@patch("app.agents.literature_mining_agent.search_vector_store", return_value=[])
@patch("app.agents.literature_mining_agent.get_vector_store")
def test_mine_skips_discovery_when_gate_false(mock_vs_factory, _mock_search):
    agent = LiteratureMiningAgent()
    db = MagicMock()
    vs = MagicMock()
    vs.has_index.return_value = True
    mock_vs_factory.return_value = vs

    with patch.object(agent, "_should_run_literature_discovery", return_value=False), patch.object(
        agent, "_discover_and_import_literature"
    ) as mock_disc:
        resp = agent.mine("proj-1", "RQ", top_k=5, db=db)

    mock_disc.assert_not_called()
    assert isinstance(resp, LiteratureMiningResponse)
    assert "未能从文献库中匹配到相关片段" in (resp.warning or "")


@patch("app.agents.literature_mining_agent.search_vector_store", return_value=[])
@patch("app.agents.literature_mining_agent.get_vector_store")
def test_mine_no_second_discovery_when_search_empty(mock_vs_factory, _mock_search):
    agent = LiteratureMiningAgent()
    db = MagicMock()
    vs = MagicMock()
    vs.has_index.return_value = True
    mock_vs_factory.return_value = vs

    with patch.object(agent, "_should_run_literature_discovery", return_value=True), patch.object(
        agent,
        "_discover_and_import_literature",
        return_value=({"papers": [], "search_queries": ["alt-q"]}, {"imported": 0}),
    ) as mock_disc:
        resp = agent.mine("proj-2", "RQ", top_k=5, db=db)

    assert mock_disc.call_count == 1
    assert "未能从文献库中匹配到相关片段" in (resp.warning or "")
