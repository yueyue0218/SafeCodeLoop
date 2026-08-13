from safecodeloop.actions import Action
from safecodeloop.approval import ApprovalStore
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop
from safecodeloop.tools import ToolRegistry, ToolResult, create_command_tool_registry, create_file_tool_registry


SIGNING_KEY = b"test-only-approval-signing-key"


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
        approval_store=ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY),
    )

    result = loop.run("install dependency")

    assert result.status == "needs_approval"
    assert result.final_message == "dependency install requires approval"
    assert result.steps[0].observation["kind"] == "guardrail_result"
    assert result.steps[0].observation["status"] == "needs_approval"
    assert result.approval_id
    assert ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY).get(result.approval_id).status == "pending"


def test_approved_action_executes_once_and_feedback_returns_to_loop(tmp_path):
    called = []
    registry = ToolRegistry()

    def run_command(arguments):
        called.append(arguments["command"])
        return ToolResult(ok=True, data={"exit_code": 0, "stdout": "installed", "stderr": ""})

    registry.register("run_command", run_command)
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "dependency install requires approval")
    store.approve(record.id)
    llm = MockLLM(['{"type": "finish", "message": "resumed"}'])
    loop = AgentLoop(
        llm=llm,
        max_steps=1,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
        approval_store=store,
    )

    result = loop.resume(record.id, "install dependency")

    assert result.status == "success"
    assert result.final_message == "resumed"
    assert called == ["python -m pip install requests"]
    assert store.get(record.id).status == "consumed"
    assert "approved_tool_result" in llm.calls[0][-1]["content"]


def test_rejected_approval_never_calls_tool(tmp_path):
    called = False
    registry = ToolRegistry()

    def run_command(arguments):
        nonlocal called
        called = True
        return ToolResult(ok=True)

    registry.register("run_command", run_command)
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "approval required")
    store.reject(record.id)
    loop = AgentLoop(
        llm=MockLLM(['{"type":"finish"}']),
        tool_registry=registry,
        approval_store=store,
    )

    try:
        loop.resume(record.id, "install dependency")
    except ValueError as exc:
        assert "rejected" in str(exc)
    else:
        raise AssertionError("expected rejected approval to fail")
    assert called is False


def test_resumed_failed_validation_cannot_finish_successfully(tmp_path):
    registry = ToolRegistry()
    registry.register(
        "run_validation",
        lambda arguments: ToolResult(
            ok=False,
            data={
                "exit_code": 1,
                "stdout": "FAILED tests/test_app.py::test_value - AssertionError",
                "stderr": "",
            },
            error="command exited with code 1",
        ),
    )
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_validation", arguments={"command": "python -m pip install --version"})
    record = store.create(action, "dependency install requires approval")
    store.approve(record.id)
    loop = AgentLoop(
        llm=MockLLM(['{"type": "finish", "message": "done"}']),
        max_steps=1,
        tool_registry=registry,
        guardrail_engine=GuardrailEngine(tmp_path),
        validator=Validator(),
        approval_store=store,
    )

    result = loop.resume(record.id, "validate dependency state")

    assert result.status != "success"
    assert result.steps[1].observation["kind"] == "completion_rejected"
