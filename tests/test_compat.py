from nixi.compat.optional import load, NullModule, is_available
from nixi.compat.fakes import FakePsutil, FakePyAutoGUI, FakePyperclip
from nixi.platform.capabilities import capability_report, has_module
from nixi.platform.system import beep, system_stats, run_shell

def test_null_module():
    m = NullModule("fake_mod")
    assert not m
    assert m.anything is not None
    assert m.anything() is None

def test_load_missing():
    mod = load("this_module_does_not_exist_12345")
    assert isinstance(mod, NullModule)
    assert not is_available(mod)

def test_load_present():
    import os
    assert is_available(load("os"))

def test_fake_psutil():
    assert FakePsutil.cpu_percent() == 0.0
    assert FakePsutil.virtual_memory().percent == 50.0
    assert list(FakePsutil.process_iter()) == []

def test_fake_pyautogui():
    g = FakePyAutoGUI()
    assert g.size() == (1920, 1080)

def test_fake_pyperclip():
    c = FakePyperclip()
    c.copy("hello")
    assert c.paste() == "hello"

def test_capability_report():
    r = capability_report()
    assert "windows" in r and "qt" in r

def test_beep_no_crash():
    assert isinstance(beep(), bool)

def test_system_stats_shape():
    s = system_stats()
    assert "cpu_percent" in s and "ram_percent" in s

def test_run_shell_is_a_blocked_compatibility_stub():
    out = run_shell("echo hello", timeout=5)
    assert "shell execution is disabled" in out.lower()
