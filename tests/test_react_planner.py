import tempfile
from unittest.mock import MagicMock
from nixi.agent.react_planner import ReActPlanner
from nixi.config import NixiConfig

def test_is_complex_goal():
    assert ReActPlanner.is_complex_agent_goal("clean up my downloads")
    assert ReActPlanner.is_complex_agent_goal("do X and then do Y")
    assert not ReActPlanner.is_complex_agent_goal("what is 2+2?")

def test_callback_order():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        llm = MagicMock()
        llm.chat_stream.return_value = iter(["hello world"])
        planner = ReActPlanner(llm_client=llm)
        # mock tools to avoid real FS
        planner.tools.organize_folder = MagicMock(return_value="organized!")
        calls = []
        def on_progress(curr, total, label):
            calls.append((curr, total, label))
        ok, summary = planner.plan_and_execute("clean up my downloads", on_step_progress=on_progress)
        assert ok and calls[0] == (1, 1, "Organizing Downloads folder (undoable; no deletions)...")
        # signature must be (curr, total, label) not (label, curr, total)
        assert isinstance(calls[0][0], int)

def test_returns_tuple():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        llm = MagicMock()
        llm.chat_stream.return_value = iter(["done"])
        planner = ReActPlanner(llm_client=llm)
        planner.tools.organize_folder = MagicMock(return_value="ok")
        result = planner.plan_and_execute("clean up my downloads")
        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], bool) and isinstance(result[1], str)

def test_vision_copilot_no_crash():
    from nixi.agent.vision_copilot import VisionCopilot
    llm = MagicMock()
    llm.analyze_screen.return_value = "looks like code"
    reader = MagicMock()
    reader.capture_screen.return_value = b"fake"
    cop = VisionCopilot(llm, reader)
    result = cop.debug_active_screen("debug my code")
    assert isinstance(result, str)
