import pytest

from safecodeloop.llm import LLMError, MockLLM


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


def test_llm_response_contains_provider_metadata_without_secrets():
    llm = MockLLM(["done"], provider="mock-provider")

    response = llm.generate([{"role": "user", "content": "task"}])

    assert response.content == "done"
    assert response.provider == "mock-provider"
    assert response.metadata == {"script_index": 0}
