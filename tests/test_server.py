import tempfile, threading, time, json, urllib.request
from nixi.config import NixiConfig
from nixi.server import NixiServer

def _fetch(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())

def test_health_endpoint():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_API_ENABLED": "true", "NIXI_API_HOST": "127.0.0.1", "NIXI_API_PORT": "18765"})
        srv = NixiServer(config=cfg)
        msg = srv.start()
        assert "listening" in msg.lower(), msg
        try:
            status, data = _fetch("http://127.0.0.1:18765/health")
            assert status == 200
            assert "diagnostics" in data or "status" in data
            # 404
            try:
                _fetch("http://127.0.0.1:18765/nonexistent")
                assert False, "should 404"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            srv.stop()
            assert not srv.is_running

def test_auth():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = NixiConfig.from_env({"NIXI_DATA_DIR": tmp, "NIXI_API_ENABLED": "true", "NIXI_API_HOST": "127.0.0.1", "NIXI_API_PORT": "18766", "NIXI_API_TOKEN": "secret123"})
        srv = NixiServer(config=cfg)
        srv.start()
        try:
            try:
                _fetch("http://127.0.0.1:18766/health")
                assert False
            except urllib.error.HTTPError as e:
                assert e.code == 401
            # with token
            req = urllib.request.Request("http://127.0.0.1:18766/health", headers={"Authorization": "Bearer secret123"})
            with urllib.request.urlopen(req, timeout=3) as r:
                assert r.status == 200
        finally:
            srv.stop()
