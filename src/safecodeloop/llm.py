import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


class OpenAICompatibleLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60,
        transport=None,
    ):
        if not api_key:
            raise LLMError("API credential is not configured")
        if not model:
            raise LLMError("model must not be empty")
        if timeout <= 0:
            raise LLMError("timeout must be positive")
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or urlopen

    def generate(self, messages: list[dict[str, str]]) -> LLMResponse:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._transport(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 401:
                raise LLMError("LLM authentication failed") from exc
            if exc.code == 429:
                raise LLMError("LLM rate limit exceeded") from exc
            raise LLMError(f"LLM request failed with HTTP {exc.code}") from exc
        except (TimeoutError, URLError) as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                raise LLMError("LLM request timed out") from exc
            raise LLMError("LLM network request failed") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMError("LLM returned invalid JSON") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("invalid chat completion response") from exc
        if not isinstance(content, str):
            raise LLMError("invalid chat completion response")

        usage = body.get("usage", {})
        metadata = {"model": body.get("model", self.model)}
        if isinstance(usage, dict):
            metadata["usage"] = usage
        return LLMResponse(
            content=content,
            provider="openai-compatible",
            metadata=metadata,
        )
