from types import SimpleNamespace

from nixi.core.app_launcher import AppLauncher
from nixi.platform import system


def test_open_shell_ui_is_blocked():
    ok, message = AppLauncher.launch("PowerShell")
    assert not ok
    assert "background" in message.lower()


def test_windows_command_uses_hidden_powershell(monkeypatch):
    class StartupInfo:
        dwFlags = 0
        wShowWindow = 1

    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr(system.subprocess, "STARTUPINFO", StartupInfo, raising=False)
    monkeypatch.setattr(system.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(
        system.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="ok", stderr="", returncode=0),
    )

    result = system.run_shell("Get-Date")

    assert result == "ok"
    # Inspect captured arguments by replacing run with a recorder.
    calls = {}

    def capture(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return SimpleNamespace(stdout="ok", stderr="", returncode=0)

    monkeypatch.setattr(system.subprocess, "run", capture)
    assert system.run_shell("Get-Date") == "ok"
    kwargs = calls["kwargs"]
    assert kwargs["capture_output"] is True
    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].wShowWindow == 0
    assert "powershell.exe" in calls["args"][0][0].lower()
