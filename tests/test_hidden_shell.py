from nixi.core.app_launcher import AppLauncher
from nixi.platform import system


def test_open_shell_ui_is_blocked():
    ok, message = AppLauncher.launch("PowerShell")
    assert not ok
    assert "shell windows" in message.lower()
    assert "shell commands are disabled" in message.lower()


def test_arbitrary_shell_execution_is_disabled(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No shell process should be started")

    monkeypatch.setattr(system.subprocess, "run", forbidden)
    result = system.run_shell("Get-Date")
    assert "disabled" in result.lower()
