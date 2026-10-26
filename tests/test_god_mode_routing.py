from unittest.mock import MagicMock

from nixi.core.god_mode_agent import GodModeAgent


def test_windows_settings_page_has_deterministic_native_route():
    agent = GodModeAgent(MagicMock())
    agent.system.open_settings = MagicMock(return_value="Opened Windows Settings: bluetooth.")
    handled, result = agent.process_command("open Bluetooth settings")
    assert handled
    assert result == "Opened Windows Settings: bluetooth."
    agent.system.open_settings.assert_called_once_with("bluetooth")


def test_shell_command_is_refused_without_execution():
    agent = GodModeAgent(MagicMock())
    handled, result = agent.process_command("powershell Get-Process")
    assert handled
    assert "don't run PowerShell" in result
