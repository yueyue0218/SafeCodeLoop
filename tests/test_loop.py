from safecodeloop.llm import LLMResponse, MockLLM
from safecodeloop.loop import AgentLoop
from safecodeloop.redaction import SecretRedactor


def test_loop_stops_successfully_when_llm_returns_finish():
    llm = MockLLM(['{"type": "finish", "message": "done"}'])
    loop = AgentLoop(llm=llm, max_steps=3)

    result = loop.run("finish the task")

    assert result.status == "success"
    assert result.final_message == "done"
    assert len(result.steps) == 1
    assert result.steps[0].action.type == "finish"
    assert llm.calls[0][0]["role"] == "system"
    assert "Return exactly one JSON action object" in llm.calls[0][0]["content"]
    assert '"type":"finish"' in llm.calls[0][0]["content"]


def test_invalid_llm_output_becomes_parse_error_observation():
    llm = MockLLM(["not json", '{"type": "finish", "message": "recovered"}'])
    loop = AgentLoop(llm=llm, max_steps=3)

    result = loop.run("recover from parse error")

    assert result.status == "success"
    assert result.final_message == "recovered"
    assert len(result.steps) == 2
    assert result.steps[0].observation["kind"] == "parse_error"
    assert "invalid JSON" in result.steps[0].observation["message"]
    assert "parse_error" in llm.calls[1][-1]["content"]
    assert "Return exactly one JSON action object" in llm.calls[1][-1]["content"]


def test_parse_error_feedback_does_not_echo_large_invalid_response():
    invalid = "sensitive-invalid-output-" * 1000
    llm = MockLLM([invalid, '{"type": "finish", "message": "recovered"}'])
    loop = AgentLoop(llm=llm, max_steps=2)

    result = loop.run("recover safely")

    feedback = llm.calls[1][-1]["content"]
    assert result.status == "success"
    assert len(feedback) < 500
    assert "sensitive-invalid-output" not in feedback
    assert "raw_response" not in result.steps[0].observation


def test_loop_returns_max_steps_when_no_finish_action_arrives():
    llm = MockLLM(
        [
            '{"type": "list_files"}',
            '{"type": "list_files"}',
        ]
    )
    loop = AgentLoop(llm=llm, max_steps=2)

    result = loop.run("keep going")

    assert result.status == "max_steps"
    assert result.final_message == "Reached max steps without finish action."
    assert len(result.steps) == 2


def test_loop_redacts_known_secret_at_untrusted_llm_boundary():
    secret = "runtime-opaque-loop-secret"

    class UnredactedLLM:
        def __init__(self):
            self.calls = []

        def generate(self, messages):
            self.calls.append(messages)
            return LLMResponse(
                content=f'{{"type":"finish","message":"{secret}"}}',
                provider="unsafe-test-double",
                metadata={"debug": secret},
            )

    llm = UnredactedLLM()
    loop = AgentLoop(llm=llm, redactor=SecretRedactor([secret]))

    result = loop.run(f"never reveal {secret}")

    assert secret not in str(llm.calls)
    assert secret not in result.final_message
    assert secret not in result.steps[0].llm_response
    assert "[REDACTED]" in result.final_message
