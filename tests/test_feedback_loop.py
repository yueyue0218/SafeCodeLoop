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
    registry.register("run_command", run_command)
    llm = MockLLM(
        [
            '{"type": "write_file", "path": "calc.py", "content": "def add(a, b):\\n    return a - b\\n"}',
            '{"type": "run_command", "command": "python -m pytest"}',
            '{"type": "write_file", "path": "calc.py", "content": "def add(a, b):\\n    return a + b\\n"}',
            '{"type": "run_command", "command": "python -m pytest"}',
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
