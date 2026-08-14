from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any


REDACTION_MARKER = "[REDACTED]"
MIN_KNOWN_SECRET_LENGTH = 8

_SECRET_PATTERNS = (
    re.compile(
        r"(\b(?:authorization\s*[:=]\s*)?bearer\s+)([^\s\"']+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"((?:[\"']?)\b(?:openai_api_key|api[_-]?key|access[_-]?token|token|password|secret)\b(?:[\"']?)\s*[:=]\s*[\"'])([^\"']*)(?=[\"'])",
        re.IGNORECASE,
    ),
    re.compile(
        r"((?:[\"']?)\b(?:openai_api_key|api[_-]?key|access[_-]?token|token|password|secret)\b(?:[\"']?)\s*[:=]\s*)([^\s\"',;}]+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})\b"),
)


class SecretRedactor:
    def __init__(self, known_secrets: Iterable[str] = ()):
        self._known_secrets: list[str] = []
        for secret in known_secrets:
            self.add_secret(secret)

    def add_secret(self, secret: str | None) -> None:
        if not isinstance(secret, str) or len(secret) < MIN_KNOWN_SECRET_LENGTH:
            return
        if secret == REDACTION_MARKER or secret in self._known_secrets:
            return
        self._known_secrets.append(secret)
        self._known_secrets.sort(key=len, reverse=True)

    def redact_text(self, text: str) -> str:
        redacted = str(text)
        for secret in self._known_secrets:
            redacted = redacted.replace(secret, REDACTION_MARKER)
        for pattern in _SECRET_PATTERNS:
            if pattern.groups >= 2:
                redacted = pattern.sub(rf"\1{REDACTION_MARKER}", redacted)
            else:
                redacted = pattern.sub(REDACTION_MARKER, redacted)
        return redacted

    def redact(self, value: Any) -> Any:
        return redact_value(value, redactor=self)


def redact_secrets(text: str, known_secrets: Iterable[str] = ()) -> str:
    return SecretRedactor(known_secrets).redact_text(text)


def redact_value(value: Any, redactor: SecretRedactor | None = None) -> Any:
    active = redactor or SecretRedactor()
    if isinstance(value, str):
        return active.redact_text(value)
    if isinstance(value, dict):
        return {
            active.redact_text(key) if isinstance(key, str) else key: redact_value(
                item, active
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, active) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item, active) for item in value)
    if isinstance(value, set):
        return {redact_value(item, active) for item in value}
    return value
