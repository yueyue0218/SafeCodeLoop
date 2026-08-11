from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_PROVIDER = "openai"
ENV_CREDENTIALS_PATH = "SAFECODELOOP_CREDENTIALS_PATH"


class CredentialError(ValueError):
    pass


class CredentialStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_credentials_path()
        self._data = self._load()

    def set_key(self, provider: str, value: str) -> None:
        provider = _normalize_provider(provider)
        if not value:
            raise CredentialError("key value must not be empty")
        self._data[provider] = value
        self._save()

    def get_key(self, provider: str = DEFAULT_PROVIDER) -> str | None:
        return self._data.get(_normalize_provider(provider))

    def clear_key(self, provider: str = DEFAULT_PROVIDER) -> None:
        self._data.pop(_normalize_provider(provider), None)
        self._save()

    def status(self, provider: str = DEFAULT_PROVIDER) -> dict[str, str | bool]:
        provider = _normalize_provider(provider)
        value = self._data.get(provider)
        if value is None:
            return {
                "provider": provider,
                "configured": False,
                "masked_key": "",
                "hint": f"Run `safecodeloop key set {provider} --value <key>` to configure it.",
            }
        return {
            "provider": provider,
            "configured": True,
            "masked_key": mask_secret(value),
            "hint": "",
        }

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise CredentialError("credentials file must contain a JSON object")
        return {str(key): str(value) for key, value in payload.items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")


def default_credentials_path() -> Path:
    override = os.environ.get(ENV_CREDENTIALS_PATH)
    if override:
        return Path(override)
    return Path.home() / ".safecodeloop" / "credentials.json"


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}...{value[-4:]}"


def _normalize_provider(provider: str) -> str:
    provider = provider.strip().lower()
    if not provider:
        raise CredentialError("provider must not be empty")
    return provider
