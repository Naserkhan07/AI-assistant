import tempfile
from nixi.config import NixiConfig
from nixi.core.llm_client import NixiLLMClient

def test_offline_client():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_PROVIDER": "offline"})
        llm = NixiLLMClient(config=cfg)
        assert not llm.is_online()
        # offline chat_stream should yield something without network
        chunks = list(llm.chat_stream([{"role": "user", "content": "hello"}]))
        assert len(chunks) >= 1 and isinstance(chunks[0], str)

def test_vision_local_only():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_LOCAL_ONLY": "true"})
        llm = NixiLLMClient(config=cfg)
        result = llm.analyze_screen(b"fake_jpeg_bytes", prompt="what is this?")
        assert "local-only" in result.lower() or "offline" in result.lower()

def test_tool_loop_no_tools():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_PROVIDER": "offline"})
        llm = NixiLLMClient(config=cfg)
        reply = llm.tool_loop([{"role": "user", "content": "hello"}], tools={})
        assert isinstance(reply, str) and len(reply) > 0
