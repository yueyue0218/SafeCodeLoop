from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


DEFAULT_PROVIDER = "openai"
DEFAULT_SERVICE = "safecodeloop"


class CredentialError(ValueError):
    pass


class CredentialBackend(Protocol):
    def get(self, provider: str) -> str | None: ...

    def set(self, provider: str, value: str) -> None: ...

    def clear(self, provider: str) -> None: ...


class KeyringBackend:
    def __init__(self, service: str = DEFAULT_SERVICE, keyring_module=None):
        if keyring_module is None:
            try:
                import keyring as keyring_module
            except ImportError as exc:
                raise CredentialError(
                    "OS keyring support is unavailable; install the project dependencies"
                ) from exc
        self.service = service
        self._keyring = keyring_module

    def get(self, provider: str) -> str | None:
        try:
            return self._keyring.get_password(self.service, provider)
        except Exception as exc:
            raise CredentialError("could not read credential from OS keyring") from exc

    def set(self, provider: str, value: str) -> None:
        try:
            self._keyring.set_password(self.service, provider, value)
        except Exception as exc:
            raise CredentialError("could not store credential in OS keyring") from exc

    def clear(self, provider: str) -> None:
        try:
            if self._keyring.get_password(self.service, provider) is not None:
                self._keyring.delete_password(self.service, provider)
        except Exception as exc:
            raise CredentialError("could not clear credential from OS keyring") from exc


class FileCredentialBackend:
    """Explicit development/test fallback; values are stored as plaintext JSON."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def get(self, provider: str) -> str | None:
        return self._load().get(provider)

    def set(self, provider: str, value: str) -> None:
        data = self._load()
        data[provider] = value
        self._save(data)

    def clear(self, provider: str) -> None:
        data = self._load()
        data.pop(provider, None)
        self._save(data)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CredentialError("credentials file must contain valid JSON") from exc
        if not isinstance(payload, dict):
            raise CredentialError("credentials file must contain a JSON object")
        return {str(key): str(value) for key, value in payload.items()}

    def _save(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class CredentialStore:
    def __init__(
        self,
        path: str | Path | None = None,
        backend: CredentialBackend | None = None,
    ):
        if path is not None and backend is not None:
            raise CredentialError("choose either a credential path or backend, not both")
        if backend is not None:
            self.backend = backend
        elif path is not None:
            self.backend = FileCredentialBackend(path)
        else:
            self.backend = KeyringBackend()

    def set_key(self, provider: str, value: str) -> None:
        provider = _normalize_provider(provider)
        if not value:
            raise CredentialError("key value must not be empty")
        self.backend.set(provider, value)

    def get_key(self, provider: str = DEFAULT_PROVIDER) -> str | None:
        return self.backend.get(_normalize_provider(provider))

    def clear_key(self, provider: str = DEFAULT_PROVIDER) -> None:
        self.backend.clear(_normalize_provider(provider))

    def status(self, provider: str = DEFAULT_PROVIDER) -> dict[str, str | bool]:
        provider = _normalize_provider(provider)
        value = self.backend.get(provider)
        if value is None:
            return {
                "provider": provider,
                "configured": False,
                "hint": f"Run `safecodeloop key set {provider}` to configure it securely.",
            }
        return {"provider": provider, "configured": True, "hint": ""}


def _normalize_provider(provider: str) -> str:
    provider = provider.strip().lower()
    if not provider:
        raise CredentialError("provider must not be empty")
    return provider
