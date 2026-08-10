import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> LLMResponse:
        ...


SECRET_PATTERNS = (
    re.compile(r"(OPENAI_API_KEY\s*=\s*)([^\s]+)", re.IGNORECASE),
    re.compile(r"\b(sk-[A-Za-z0-9_-]+)\b"),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    sanitized = []
    for message in messages:
        sanitized.append(
            {
                **message,
                "content": redact_secrets(str(message.get("content", ""))),
            }
        )
    return sanitized


class MockLLM:
    def __init__(self, responses: list[str], provider: str = "mock"):
        self._responses = list(responses)
        self.provider = provider
        self.calls: list[list[dict[str, str]]] = []
        self._index = 0

    def generate(self, messages: list[dict[str, str]]) -> LLMResponse:
        self.calls.append(redact_messages(messages))
        if self._index >= len(self._responses):
            raise LLMError("mock LLM script exhausted")

        response = LLMResponse(
            content=self._responses[self._index],
            provider=self.provider,
            metadata={"script_index": self._index},
        )
        self._index += 1
        return response
