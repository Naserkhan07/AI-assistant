import tempfile, pathlib
from nixi.config import NixiConfig
from nixi.security import PermissionManager, UndoManager, RiskLevel
from nixi.security.permissions import ActionJournal


def _cfg(tmp):
    return NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_ALLOWED_TOOLS": "", "NIXI_DENIED_TOOLS": "wipe_disk,format_drive"})

def test_deny_list():
    with tempfile.TemporaryDirectory() as tmp:
        pm = PermissionManager(_cfg(tmp), confirm_callback=lambda *a: True)
        d = pm.authorize("wipe_disk", RiskLevel.CRITICAL, {})
        assert not d.allowed

def test_allow_via_confirm():
    with tempfile.TemporaryDirectory() as tmp:
        pm = PermissionManager(_cfg(tmp), confirm_callback=lambda *a: True)
        d = pm.authorize("run_shell", RiskLevel.HIGH, {"command": "echo hi"})
        assert d.allowed and not d.needs_confirmation

def test_deny_via_user():
    with tempfile.TemporaryDirectory() as tmp:
        pm = PermissionManager(_cfg(tmp), confirm_callback=lambda *a: False)
        d = pm.authorize("run_shell", RiskLevel.HIGH, {})
        assert not d.allowed

def test_safe_levels_no_confirm():
    with tempfile.TemporaryDirectory() as tmp:
        pm = PermissionManager(_cfg(tmp), confirm_callback=lambda *a: False)
        d = pm.authorize("web_search", RiskLevel.SAFE, {})
        assert d.allowed and not d.needs_confirmation

def test_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp); cfg.dry_run = True
        pm = PermissionManager(cfg, confirm_callback=lambda *a: True)
        d = pm.authorize("run_shell", RiskLevel.HIGH, {})
        assert d.dry_run

def test_journal():
    with tempfile.TemporaryDirectory() as tmp:
        j = ActionJournal(db_path=pathlib.Path(tmp)/"audit.db", enabled=True)
        j.record("test_action", RiskLevel.SAFE, {}, "allowed", "ok", "result")
        assert len(j.recent(limit=5)) == 1

def test_undo_manager():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        mgr = UndoManager(config=cfg)
        src = pathlib.Path(tmp)/"hello.txt"
        src.write_text("hi")
        msg = mgr.safe_delete(src)
        assert not src.exists()
        assert "trash" in msg.lower() or "Moved" in msg
        msg2 = mgr.undo_last()
        assert src.exists()
        assert src.read_text() == "hi"

def test_local_only_blocks_network():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_LOCAL_ONLY": "true"})
        pm = PermissionManager(cfg, confirm_callback=lambda *a: True)
        d = pm.authorize("web_search", RiskLevel.HIGH, {})
        assert not d.allowed
