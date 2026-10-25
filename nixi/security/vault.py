"""Encrypted form-fill vault — OS keyring when available, file fallback (Fernet if installed)."""
from __future__ import annotations
import base64, json, os, time
from pathlib import Path
from typing import Any
from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger
log = get_logger("vault")

def _fernet_available():
    try: import cryptography.fernet; return True
    except Exception: return False

class Vault:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.path = Path(self.config.data_dir) / "vault.json"
        self._key: bytes | None = None

    def _derive_key(self) -> bytes:
        # Prefer keyring, else derive from api_token or random file key
        try:
            import keyring
            k = keyring.get_password("nixi", "vault-key")
            if k: return base64.urlsafe_b64decode(k.encode())
        except Exception: pass
        keyfile = Path(self.config.data_dir) / ".vault_key"
        if keyfile.exists():
            try: return base64.urlsafe_b64decode(keyfile.read_text().strip().encode())
            except Exception: pass
        raw = os.urandom(32)
        key = base64.urlsafe_b64encode(raw)
        try:
            keyfile.parent.mkdir(parents=True, exist_ok=True)
            keyfile.write_text(key.decode()); keyfile.chmod(0o600)
            try:
                import keyring; keyring.set_password("nixi","vault-key", key.decode())
            except Exception: pass
        except Exception: pass
        return raw

    def _encrypt(self, plaintext: str) -> str:
        if _fernet_available():
            from cryptography.fernet import Fernet
            raw = self._derive_key()
            f = Fernet(base64.urlsafe_b64encode(raw))
            return f.encrypt(plaintext.encode()).decode()
        # fallback: base64 obfuscation (not real crypto, but avoids plaintext on disk)
        raw = self._derive_key()
        pad = (raw * ((len(plaintext)//len(raw))+1))[:len(plaintext)]
        xored = bytes(a^b for a,b in zip(plaintext.encode(), pad))
        return "b64:" + base64.b64encode(xored).decode()

    def _decrypt(self, token: str) -> str:
        if token.startswith("b64:"):
            raw = self._derive_key()
            data = base64.b64decode(token[4:])
            pad = (raw * ((len(data)//len(raw))+1))[:len(data)]
            return bytes(a^b for a,b in zip(data, pad)).decode()
        if _fernet_available():
            from cryptography.fernet import Fernet
            raw = self._derive_key()
            f = Fernet(base64.urlsafe_b64encode(raw))
            return f.decrypt(token.encode()).decode()
        raise ValueError("Unknown vault token format")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {}
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception: return {}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def put(self, key: str, value: str, kind: str = "generic") -> None:
        data = self._load()
        data[key] = {"token": self._encrypt(value), "kind": kind, "updated_at": time.time()}
        self._save(data); log.info("Vault put %s (%s)", key, kind)
    def get(self, key: str) -> str | None:
        data = self._load()
        entry = data.get(key)
        if not entry: return None
        try: return self._decrypt(entry["token"])
        except Exception as e: log.warning("Vault decrypt failed for %s: %s", key, e); return None
    def delete(self, key: str) -> bool:
        data = self._load()
        if key not in data: return False
        del data[key]; self._save(data); return True
    def list_keys(self) -> list[dict[str, Any]]:
        data = self._load()
        return [{"key": k, "kind": v.get("kind","?"), "updated_at": v.get("updated_at",0)} for k,v in data.items()]
    def is_locked(self) -> bool: return False
