import tempfile, pathlib
from nixi.config import NixiConfig
from nixi.agent.knowledge import KnowledgeStore

def test_index_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_KNOWLEDGE_DIRS": tmp})
        store = KnowledgeStore(config=cfg)
        doc = pathlib.Path(tmp) / "hello.md"
        doc.write_text("# Hello\nThis is a test document about Nixi assistant.")
        n = store.index_file(doc)
        assert n >= 1
        results = store.search("Nixi assistant")
        assert len(results) >= 1
        assert "Nixi" in results[0]["text"]
        # re-index unchanged should be 0
        assert store.index_file(doc) == 0

def test_pii_redacted_in_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        store = KnowledgeStore(config=cfg)
        doc = pathlib.Path(tmp) / "secrets.md"
        doc.write_text("Contact admin@example.com for help")
        store.index_file(doc)
        results = store.search("Contact")
        assert results
        assert "admin@example.com" not in results[0]["text"]

def test_stats():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        store = KnowledgeStore(config=cfg)
        s = store.stats()
        assert "documents" in s and "chunks" in s
