from safecodeloop.actions import Action
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop
from safecodeloop.tools import ToolRegistry, ToolResult, create_command_tool_registry, create_file_tool_registry


def test_blocked_action_does_not_call_tool(tmp_path):
    called = False
    registry = ToolRegistry()

    def run_command(arguments):
        nonlocal called
        called = True
        return ToolResult(ok=True)

    registry.register("run_command", run_command)
    llm = MockLLM(['{"type": "run_command", "command": "rm -rf /"}'])
    loop = AgentLoop(
        llm=llm,
        max_steps=1,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
    )

    result = loop.run("try a dangerous command")

    assert result.status == "blocked"
    assert called is False
    assert result.steps[0].observation["kind"] == "guardrail_result"
    assert result.steps[0].observation["status"] == "blocked"


def test_allowed_write_file_action_updates_workspace(tmp_path):
    registry = create_file_tool_registry(tmp_path)
    llm = MockLLM(
        [
            '{"type": "write_file", "path": "notes/out.txt", "content": "hello"}',
            '{"type": "finish", "message": "done"}',
        ]
    )
    loop = AgentLoop(
        llm=llm,
        max_steps=2,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
    )

    result = loop.run("write a file")

    assert result.status == "success"
    assert (tmp_path / "notes" / "out.txt").read_text(encoding="utf-8") == "hello"
    assert result.steps[0].observation["kind"] == "tool_result"
    assert result.steps[0].observation["ok"] is True
    assert "tool_result" in llm.calls[1][-1]["content"]


def test_needs_approval_action_stops_before_running_tool(tmp_path):
    registry = create_command_tool_registry(tmp_path)
    llm = MockLLM(['{"type": "run_command", "command": "python -m pip install requests"}'])
    loop = AgentLoop(
        llm=llm,
        max_steps=1,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
    )

    result = loop.run("install dependency")

    assert result.status == "needs_approval"
    assert result.final_message == "dependency install requires approval"
    assert result.steps[0].observation["kind"] == "guardrail_result"
    assert result.steps[0].observation["status"] == "needs_approval"
