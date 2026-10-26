from nixi.integrations.jev_social import JevSocialIntegration
from nixi.integrations.ollama_system_one import OllamaSystemOneServer


def test_jev_result_output_is_bounded_and_http_sources_only():
    report = {
        "status": "completed",
        "result": {
            "items": [
                {"title": "Public post", "caption": "  a  bounded\ncaption ", "url": "https://instagram.com/p/abc"},
                {"title": "Bad source", "url": "javascript:alert(1)"},
            ]
        },
    }
    text = JevSocialIntegration._format_result(report, limit=1)
    assert "Public post — a bounded caption" in text
    assert "https://instagram.com/p/abc" in text
    assert "javascript:" not in text
    assert "does not post" in text


def test_system_one_bridge_rejects_non_loopback_ollama_targets():
    import pytest

    with pytest.raises(ValueError, match="loopback"):
        OllamaSystemOneServer("https://example.com/v1", "model")
    with pytest.raises(ValueError, match="loopback"):
        OllamaSystemOneServer("http://192.0.2.10:11434/v1", "model")


def test_browser_controller_serializes_work_on_one_persistent_thread():
    import threading
    from nixi.automation.browser import BrowserController

    browser = BrowserController()
    thread_ids = []
    browser._open_url = lambda url: thread_ids.append(threading.get_ident()) or f"opened {url}"
    try:
        assert browser.open_url("https://example.com") == "opened https://example.com"
        assert browser.open_url("https://example.org") == "opened https://example.org"
        assert len(set(thread_ids)) == 1
        assert thread_ids[0] != threading.get_ident()
    finally:
        browser.close()
