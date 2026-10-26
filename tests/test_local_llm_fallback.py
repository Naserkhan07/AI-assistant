import json

from nixi.config import NixiConfig
from nixi.core.llm_client import NixiLLMClient


class FakeResponse:
    def __init__(self, status_code, lines=()):
        self.status_code = status_code
        self._lines = list(lines)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_lines(self):
        return iter(self._lines)


class GatewayThenOllama:
    def __init__(self, local_status=200):
        self.local_status = local_status
        self.calls = []

    def stream(self, method, url, **kwargs):
        self.calls.append((url, kwargs))
        if "3001" in url:
            return FakeResponse(429)
        if self.local_status != 200:
            return FakeResponse(self.local_status)
        data = {"choices": [{"delta": {"content": "Ollama reply"}}]}
        return FakeResponse(200, ["data: " + json.dumps(data), "data: [DONE]"])


def make_client():
    cfg = NixiConfig.from_env({
        "NIXI_PROVIDER": "freellmapi",
        "FREELLMAPI_URL": "http://127.0.0.1:3001/v1",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
        "OLLAMA_MODEL": "qwen2.5:3b",
        "NIXI_DATA_DIR": "/tmp/nixi-ollama-test",
    })
    return NixiLLMClient(config=cfg)


def test_freellmapi_rate_limit_falls_back_to_local_ollama():
    client = make_client()
    fake = GatewayThenOllama()
    client._client = fake
    answer = "".join(client.chat_stream([{"role": "user", "content": "hello"}], use_cache=False))

    assert answer == "Ollama reply"
    assert len(fake.calls) == 2
    local_url, local_options = fake.calls[1]
    assert local_url.endswith("11434/v1/chat/completions")
    assert local_options["json"]["model"] == "qwen2.5:3b"
    assert "Authorization" not in local_options["headers"]


def test_all_gateway_and_local_failures_still_return_offline_response():
    client = make_client()
    fake = GatewayThenOllama(local_status=503)
    client._client = fake
    answer = "".join(client.chat_stream([{"role": "user", "content": "tell me a joke"}], use_cache=False))

    assert "local model" in answer.lower()
    assert "offline mode" in answer.lower()


def test_local_only_uses_loopback_ollama_without_cloud_fallback():
    cfg = NixiConfig.from_env({
        "NIXI_PROVIDER": "freellmapi",
        "NIXI_LOCAL_ONLY": "true",
        "FREELLMAPI_URL": "https://gateway.invalid/v1",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
        "OLLAMA_MODEL": "qwen2.5:3b",
    })
    client = NixiLLMClient(config=cfg)
    fake = GatewayThenOllama()
    client._client = fake
    answer = "".join(client.chat_stream([{"role": "user", "content": "hello"}], use_cache=False))
    assert answer == "Ollama reply"
    assert len(fake.calls) == 1
    assert "11434" in fake.calls[0][0]


def test_local_only_rejects_remote_ollama_url():
    cfg = NixiConfig.from_env({
        "NIXI_PROVIDER": "freellmapi",
        "NIXI_LOCAL_ONLY": "true",
        "OLLAMA_BASE_URL": "https://example.com/v1",
    })
    assert [spec.name for spec in cfg.provider_specs()] == ["offline"]


def test_local_only_does_not_allow_explicit_remote_client_override():
    cfg = NixiConfig.from_env({"NIXI_LOCAL_ONLY": "true"})
    client = NixiLLMClient(config=cfg, base_url="https://gateway.invalid/v1", model="secret-model")
    assert all(spec.base_url.startswith("http://127.0.0.1") or spec.is_offline for spec in client._providers())

