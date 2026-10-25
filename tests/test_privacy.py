import tempfile
from nixi.config import NixiConfig
from nixi.privacy import VisionGuard, redact_pii

def test_redact_pii():
    assert redact_pii("contact a@b.com") == "contact [EMAIL]"
    assert redact_pii("call 9876543210") != "call 9876543210"
    assert "REDACTED" in redact_pii("password: hunter2")

def test_vision_default_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp})
        g = VisionGuard(cfg)
        assert not g.check("VS Code").allowed
        assert "disabled" in g.check("VS Code").reason.lower()

def test_vision_blocklist():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "VISION_ENABLED": "true", "VISION_REQUIRE_CONSENT": "false"})
        g = VisionGuard(cfg)
        assert not g.check("HDFC NetBanking").allowed
        assert g.check("VS Code - main.py").allowed

def test_consent_required():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "VISION_ENABLED": "true", "VISION_REQUIRE_CONSENT": "true", "VISION_CONSENT_GRANTED": "false"})
        g = VisionGuard(cfg)
        assert not g.check("VS Code").allowed
        g.grant_consent(True)
        assert g.check("VS Code").allowed or "Blocked" in g.check("HDFC Bank").reason

def test_region_parsing():
    assert VisionGuard.parse_region("10,20,300,200") == (10, 20, 300, 200)
    assert VisionGuard.parse_region("") is None
    assert VisionGuard.parse_region("bad") is None
    assert VisionGuard.parse_region("0,0,0,0") is None

def test_indicator_called():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "VISION_ENABLED": "true", "VISION_REQUIRE_CONSENT": "false"})
        calls = []
        g = VisionGuard(cfg, indicator=lambda a, t: calls.append((a, t)))
        g.check("VS Code")
        assert calls and calls[0][0] is True
