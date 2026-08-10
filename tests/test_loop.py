from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop


def test_loop_stops_successfully_when_llm_returns_finish():
    llm = MockLLM(['{"type": "finish", "message": "done"}'])
    loop = AgentLoop(llm=llm, max_steps=3)

    result = loop.run("finish the task")

    assert result.status == "success"
    assert result.final_message == "done"
    assert len(result.steps) == 1
    assert result.steps[0].action.type == "finish"


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
