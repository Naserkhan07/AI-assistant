from nixi.config import NixiConfig, read_env_file, as_bool, as_int, as_csv

def test_defaults():
    c = NixiConfig.from_env({})
    assert c.provider == "freellmapi"
    assert c.vision_enabled is False
    assert c.require_confirmation is True
    assert c.local_only is False

def test_local_only_forces_vision_off():
    c = NixiConfig.from_env({"NIXI_LOCAL_ONLY": "true", "VISION_ENABLED": "true"})
    assert c.local_only is True
    assert c.vision_enabled is False

def test_bool_parsing():
    assert as_bool("true") is True
    assert as_bool("1") is True
    assert as_bool("false") is False
    assert as_bool(None, default=True) is True

def test_int_parsing():
    assert as_int("42", 0) == 42
    assert as_int("bad", 7) == 7

def test_csv():
    assert as_csv("a, b, c") == ("a", "b", "c")
    assert as_csv("") == ()
    assert as_csv(None) == ()

def test_provider_specs_offline():
    c = NixiConfig.from_env({"NIXI_PROVIDER": "offline", "NIXI_DATA_DIR": "/tmp/nixi-test-a"})
    specs = c.provider_specs()
    assert len(specs) == 1 and specs[0].is_offline

def test_provider_specs_chain():
    c = NixiConfig.from_env({"NIXI_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test", "NIXI_DATA_DIR": "/tmp/nixi-test-b"})
    names = [s.name for s in c.provider_specs()]
    assert "openai" in names and "offline" in names

def test_validate():
    c = NixiConfig.from_env({"NIXI_PROVIDER": "openai", "NIXI_DATA_DIR": "/tmp/nixi-test-c"})
    issues = c.validate()
    assert any("API key" in i for i in issues)

def test_mask_secrets():
    c = NixiConfig.from_env({"FREELLMAPI_KEY": "secret123", "NIXI_DATA_DIR": "/tmp/nixi-test-d"})
    d = c.as_dict(mask_secrets=True)
    assert d["api_key"] == "***"
    d2 = c.as_dict(mask_secrets=False)
    assert d2["api_key"] == "secret123"

def test_read_env_missing():
    assert read_env_file("/tmp/__no_such_env__12345") == {}
