from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop
from safecodeloop.tools import ToolRegistry, ToolResult


def test_feedback_loop_lets_llm_correct_after_test_failure(tmp_path):
    registry = ToolRegistry()
    test_runs = 0

    def write_file(arguments):
        path = tmp_path / arguments["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return ToolResult(ok=True, data={"path": arguments["path"]})

    def run_command(arguments):
        nonlocal test_runs
        test_runs += 1
        if test_runs == 1:
            return ToolResult(
                ok=False,
                data={
                    "exit_code": 1,
                    "stdout": "FAILED tests/test_calc.py::test_add - AssertionError",
                    "stderr": "",
                },
                error="command exited with code 1",
            )
        return ToolResult(ok=True, data={"exit_code": 0, "stdout": "1 passed", "stderr": ""})

    registry.register("write_file", write_file)
    registry.register("run_validation", run_command)
    llm = MockLLM(
        [
            '{"type": "write_file", "path": "calc.py", "content": "def add(a, b):\\n    return a - b\\n"}',
            '{"type": "run_validation", "command": "python -m pytest"}',
            '{"type": "write_file", "path": "calc.py", "content": "def add(a, b):\\n    return a + b\\n"}',
            '{"type": "run_validation", "command": "python -m pytest"}',
            '{"type": "finish", "message": "fixed"}',
        ]
    )
    loop = AgentLoop(
        llm=llm,
        max_steps=5,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
        validator=Validator(),
    )

    result = loop.run("fix the failing add function")

    assert result.status == "success"
    assert result.final_message == "fixed"
    assert test_runs == 2
    assert result.steps[1].observation["kind"] == "feedback"
    assert result.steps[1].observation["feedback_kind"] == "test_failure"
    assert "feedback_kind': 'test_failure" in llm.calls[2][-1]["content"]
    assert (tmp_path / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_regular_command_returns_tool_observation_not_feedback(tmp_path):
    registry = ToolRegistry()
    registry.register(
        "run_command",
        lambda arguments: ToolResult(
            ok=True,
            data={"exit_code": 0, "stdout": "clean", "stderr": ""},
        ),
    )
    loop = AgentLoop(
        llm=MockLLM(
            [
                '{"type": "run_command", "command": "git status --short"}',
                '{"type": "finish", "message": "inspected"}',
            ]
        ),
        max_steps=2,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
        validator=Validator(),
    )

    result = loop.run("inspect repository status")

    assert result.status == "success"
    assert result.steps[0].observation["kind"] == "tool_result"
    assert result.steps[0].observation["tool"] == "run_command"


def test_loop_logs_full_feedback_but_sends_bounded_context_to_llm(tmp_path):
    marker = "FAILED tests/test_large.py::test_value - AssertionError"
    raw_output = "prefix" * 300 + "\n" + marker + "\n" + "suffix" * 300
    registry = ToolRegistry()
    registry.register(
        "run_validation",
        lambda arguments: ToolResult(
            ok=False,
            data={"exit_code": 1, "stdout": raw_output, "stderr": ""},
            error="command exited with code 1",
        ),
    )
    llm = MockLLM(
        [
            '{"type": "run_validation", "command": "python -m pytest"}',
            '{"type": "finish", "message": "observed"}',
        ]
    )
    loop = AgentLoop(
        llm=llm,
        max_steps=2,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
        validator=Validator(max_context_details_chars=240),
    )

    result = loop.run("inspect a large failure")

    assert result.steps[0].observation["details"] == raw_output
    feedback_message = llm.calls[1][-1]["content"]
    assert marker in feedback_message
    assert len(feedback_message) < 600
    assert "details_truncated" in feedback_message


def _validation_registry(tmp_path, results):
    registry = ToolRegistry()

    def write_file(arguments):
        path = tmp_path / arguments["path"]
        path.write_text(arguments["content"], encoding="utf-8")
        return ToolResult(ok=True, data={"path": arguments["path"]})

    queued = iter(results)
    registry.register("write_file", write_file)
    registry.register("run_validation", lambda arguments: next(queued))
    return registry


def _failed_validation(summary="FAILED tests/test_app.py::test_value - AssertionError"):
    return ToolResult(
        ok=False,
        data={"exit_code": 1, "stdout": summary, "stderr": ""},
        error="command exited with code 1",
    )


def test_finish_after_failed_validation_is_rejected(tmp_path):
    loop = AgentLoop(
        llm=MockLLM(
            [
                '{"type": "run_validation", "command": "python -m pytest"}',
                '{"type": "finish", "message": "done"}',
                '{"type": "finish", "message": "still done"}',
            ]
        ),
        max_steps=3,
        tool_registry=_validation_registry(tmp_path, [_failed_validation()]),
        validator=Validator(),
    )

    result = loop.run("fix the failing implementation")

    assert result.status != "success"
    assert result.steps[1].observation["kind"] == "completion_rejected"
    assert "validation has not passed" in result.steps[1].observation["reason"]


def test_write_requires_validation_before_finish(tmp_path):
    loop = AgentLoop(
        llm=MockLLM(
            [
                '{"type": "write_file", "path": "app.py", "content": "value = 1\\n"}',
                '{"type": "finish", "message": "done"}',
            ]
        ),
        max_steps=2,
        tool_registry=_validation_registry(tmp_path, []),
        validator=Validator(),
    )

    result = loop.run("change app.py")

    assert result.status != "success"
    assert result.steps[1].observation["kind"] == "completion_rejected"
    assert "workspace changes require validation" in result.steps[1].observation["reason"]


def test_validation_budget_stops_additional_runs(tmp_path):
    loop = AgentLoop(
        llm=MockLLM(
            ['{"type": "run_validation", "command": "python -m pytest"}'] * 3
        ),
        max_steps=3,
        tool_registry=_validation_registry(
            tmp_path,
            [_failed_validation("failure one"), _failed_validation("failure two")],
        ),
        validator=Validator(),
        max_validations=2,
        max_repeated_failures=3,
    )

    result = loop.run("fix tests")

    assert result.status == "validation_budget_exhausted"
    assert result.steps[-1].observation["kind"] == "validation_control"


def test_repeated_identical_failure_opens_circuit(tmp_path):
    repeated = _failed_validation()
    loop = AgentLoop(
        llm=MockLLM(
            ['{"type": "run_validation", "command": "python -m pytest"}'] * 2
        ),
        max_steps=2,
        tool_registry=_validation_registry(tmp_path, [repeated, repeated]),
        validator=Validator(),
        max_validations=4,
        max_repeated_failures=2,
    )

    result = loop.run("fix tests")

    assert result.status == "repeated_validation_failure"
    assert result.steps[-1].observation["failure_count"] == 2


def test_validation_pass_after_write_allows_finish(tmp_path):
    passed = ToolResult(ok=True, data={"exit_code": 0, "stdout": "1 passed", "stderr": ""})
    loop = AgentLoop(
        llm=MockLLM(
            [
                '{"type": "write_file", "path": "app.py", "content": "value = 1\\n"}',
                '{"type": "run_validation", "command": "python -m pytest"}',
                '{"type": "finish", "message": "verified"}',
            ]
        ),
        max_steps=3,
        tool_registry=_validation_registry(tmp_path, [passed]),
        validator=Validator(),
    )

    result = loop.run("change app.py")

    assert result.status == "success"
    assert result.final_message == "verified"


def test_validation_action_without_validator_remains_a_tool_result(tmp_path):
    registry = ToolRegistry()
    registry.register(
        "run_validation",
        lambda arguments: ToolResult(ok=True, data={"exit_code": 0, "stdout": "ok", "stderr": ""}),
    )
    loop = AgentLoop(
        llm=MockLLM(
            [
                '{"type": "run_validation", "command": "custom check"}',
                '{"type": "finish", "message": "done"}',
            ]
        ),
        max_steps=2,
        tool_registry=registry,
    )

    result = loop.run("run a custom check")

    assert result.status == "success"
    assert result.steps[0].observation["kind"] == "tool_result"
