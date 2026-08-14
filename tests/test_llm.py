import json
from urllib.error import HTTPError, URLError

import pytest

from safecodeloop.llm import LLMError, MockLLM, OpenAICompatibleLLM


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RecordingTransport:
    def __init__(self, payload=None, error=None):
        self.payload = (
            {"choices": [{"message": {"content": "done"}}]}
            if payload is None
            else payload
        )
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return FakeHTTPResponse(self.payload)


def test_openai_compatible_llm_sends_chat_completion_request():
    transport = RecordingTransport()
    llm = OpenAICompatibleLLM(
        api_key="sk-private-value",
        model="glm-5.2",
        base_url="https://njusehub.info/v1/",
        timeout=12,
        transport=transport,
    )

    response = llm.generate([{"role": "user", "content": "return JSON"}])

    request, timeout = transport.calls[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://njusehub.info/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-private-value"
    assert request.headers["Content-type"] == "application/json"
    assert payload == {
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "return JSON"}],
        "stream": False,
    }
    assert timeout == 12
    assert response.content == "done"
    assert response.provider == "openai-compatible"
    assert "sk-private-value" not in str(response.metadata)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "authentication failed"), (429, "rate limit exceeded"), (500, "HTTP 500")],
)
def test_openai_compatible_llm_reports_safe_http_errors(status, expected):
    error = HTTPError("https://example.invalid", status, "failure", {}, None)
    llm = OpenAICompatibleLLM("secret", "model", transport=RecordingTransport(error=error))

    with pytest.raises(LLMError, match=expected):
        llm.generate([{"role": "user", "content": "task"}])


def test_openai_compatible_llm_reports_timeout_without_secret():
    llm = OpenAICompatibleLLM(
        "sk-do-not-leak",
        "model",
        transport=RecordingTransport(error=URLError(TimeoutError("timed out"))),
    )

    with pytest.raises(LLMError, match="timed out") as exc_info:
        llm.generate([{"role": "user", "content": "task"}])

    assert "sk-do-not-leak" not in str(exc_info.value)


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}],
)
def test_openai_compatible_llm_rejects_invalid_response(payload):
    llm = OpenAICompatibleLLM("secret", "model", transport=RecordingTransport(payload=payload))

    with pytest.raises(LLMError, match="invalid chat completion response"):
        llm.generate([{"role": "user", "content": "task"}])


def test_mock_llm_returns_scripted_responses_in_order():
    llm = MockLLM(["first action", "second action"])

    assert llm.generate([{"role": "user", "content": "task"}]).content == "first action"
    assert llm.generate([{"role": "user", "content": "next"}]).content == "second action"


def test_mock_llm_raises_clear_error_when_script_exhausted():
    llm = MockLLM(["only response"])
    llm.generate([{"role": "user", "content": "task"}])

    with pytest.raises(LLMError, match="mock LLM script exhausted"):
        llm.generate([{"role": "user", "content": "again"}])


def test_mock_llm_records_call_history():
    llm = MockLLM(["done"])
    messages = [{"role": "user", "content": "write a parser"}]

    llm.generate(messages)

    assert llm.calls == [messages]


def test_mock_llm_redacts_secret_like_context_in_call_history():
    llm = MockLLM(["done"])

    llm.generate([{"role": "user", "content": "OPENAI_API_KEY=sk-test-secret"}])

    assert "sk-test-secret" not in llm.calls[0][0]["content"]
    assert "[REDACTED]" in llm.calls[0][0]["content"]


def test_mock_llm_redacts_secret_like_response_before_it_reaches_the_loop():
    llm = MockLLM(['{"type":"finish","message":"sk-model-leak-value"}'])

    response = llm.generate([{"role": "user", "content": "task"}])

    assert "sk-model-leak-value" not in response.content
    assert "[REDACTED]" in response.content


def test_real_provider_redacts_known_key_from_body_and_response():
    secret = "runtime-opaque-provider-secret"
    transport = RecordingTransport(
        payload={
            "choices": [
                {
                    "message": {
                        "content": f'{{"type":"finish","message":"{secret}"}}'
                    }
                }
            ]
        }
    )
    llm = OpenAICompatibleLLM(secret, "model", transport=transport)

    response = llm.generate([{"role": "user", "content": f"do not echo {secret}"}])

    request_payload = json.loads(transport.calls[0][0].data)
    assert secret not in request_payload["messages"][0]["content"]
    assert secret not in response.content
    assert "[REDACTED]" in response.content


def test_llm_response_contains_provider_metadata_without_secrets():
    llm = MockLLM(["done"], provider="mock-provider")

    response = llm.generate([{"role": "user", "content": "task"}])

    assert response.content == "done"
    assert response.provider == "mock-provider"
    assert response.metadata == {"script_index": 0}
