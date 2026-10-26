import json

import pytest

from nixi.integrations import ollama_system_one
from nixi.integrations.ollama_system_one import OllamaSystemOneServer


class FakeOllamaResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return json.dumps({
            "model": "qwen2.5:3b",
            "choices": [{"message": {"content": json.dumps(self.body)}}],
        }).encode()


def request_data():
    return {
        "state": {"request": "Find public design accounts"},
        "questions": {
            "route": {
                "type": "choice",
                "instructions": {"task": "Choose a supported platform."},
                "criteria": {"instagram_search": "Instagram search", "unsupported": "Anything else"},
            }
        },
    }


def test_bridge_translates_a_valid_finite_choice(monkeypatch):
    monkeypatch.setattr(ollama_system_one, "urlopen", lambda request, timeout: FakeOllamaResponse({
        "answers": {"route": {"choice": "instagram_search", "confidence": 0.91}},
    }))
    server = OllamaSystemOneServer("http://127.0.0.1:11434/v1", "qwen2.5:3b")

    response = server.decide(request_data())

    assert response["model"] == "qwen2.5:3b"
    assert response["answers"]["route"] == {
        "type": "choice", "choice": "instagram_search", "confidence": 0.91,
    }


def test_bridge_rejects_model_invented_action(monkeypatch):
    monkeypatch.setattr(ollama_system_one, "urlopen", lambda request, timeout: FakeOllamaResponse({
        "answers": {"route": {"choice": "post_something", "confidence": 0.99}},
    }))
    server = OllamaSystemOneServer("http://127.0.0.1:11434/v1", "qwen2.5:3b")

    with pytest.raises(RuntimeError, match="unknown choice"):
        server.decide(request_data())


def test_bridge_only_binds_loopback_and_starts_endpoint():
    server = OllamaSystemOneServer("http://127.0.0.1:11434/v1", "qwen2.5:3b")
    endpoint = server.start()
    try:
        assert endpoint.startswith("http://127.0.0.1:")
        assert endpoint.endswith("/v1/systemone")
    finally:
        server.stop()
