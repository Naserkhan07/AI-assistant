import tempfile, pathlib
from nixi.agent.memory import AgentMemory
from nixi.config import NixiConfig

def test_facts_crud():
    with tempfile.TemporaryDirectory() as tmp:
        mem = AgentMemory(db_path=pathlib.Path(tmp)/"mem.db", config=NixiConfig.from_env({"NIXI_DATA_DIR": tmp}))
        assert mem.set_fact("color", "blue")
        assert mem.get_fact("color") == "blue"
        assert mem.search_facts("blue")
        assert mem.get_all_facts()
        assert mem.delete_fact("color")
        assert mem.get_fact("color") is None

def test_extract_memory():
    with tempfile.TemporaryDirectory() as tmp:
        mem = AgentMemory(db_path=pathlib.Path(tmp)/"mem.db", config=NixiConfig.from_env({"NIXI_DATA_DIR": tmp}))
        result = mem.try_extract_memory("remember that my favorite language is Python")
        assert result is not None
        assert mem.get_fact("favorite language") == "Python"

def test_secret_not_persisted():
    with tempfile.TemporaryDirectory() as tmp:
        mem = AgentMemory(db_path=pathlib.Path(tmp)/"mem2.db", config=NixiConfig.from_env({"NIXI_DATA_DIR": tmp}))
        # should not persist secrets
        assert mem.try_extract_memory("remember that my password is hunter2") is None

def test_conversation():
    with tempfile.TemporaryDirectory() as tmp:
        mem = AgentMemory(db_path=pathlib.Path(tmp)/"mem3.db", config=NixiConfig.from_env({"NIXI_DATA_DIR": tmp}))
        mem.add_message("user", "hello")
        mem.add_message("assistant", "hi there")
        hist = mem.get_history(limit=10)
        assert len(hist) >= 2
        mem.clear_history()
        assert mem.get_history() == []
