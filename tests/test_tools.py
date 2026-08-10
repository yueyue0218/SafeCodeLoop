from safecodeloop.actions import Action
from safecodeloop.tools import ToolRegistry, ToolResult


def test_unregistered_tool_returns_structured_error():
    registry = ToolRegistry()

    result = registry.dispatch(Action(type="read_file", arguments={"path": "README.md"}))

    assert result.ok is False
    assert result.error == "unregistered tool: read_file"
    assert result.data == {}


def test_registered_tool_receives_action_arguments():
    registry = ToolRegistry()
    seen = {}

    def fake_read_file(arguments):
        seen.update(arguments)
        return ToolResult(ok=True, data={"content": "hello"})

    registry.register("read_file", fake_read_file)
    result = registry.dispatch(Action(type="read_file", arguments={"path": "README.md"}))

    assert seen == {"path": "README.md"}
    assert result.ok is True
    assert result.data == {"content": "hello"}


def test_tool_result_can_be_serialized_into_observation():
    result = ToolResult(ok=True, data={"files": ["README.md"]})

    assert result.to_observation("list_files") == {
        "kind": "tool_result",
        "tool": "list_files",
        "ok": True,
        "data": {"files": ["README.md"]},
        "error": "",
    }


def test_tool_exception_becomes_structured_error():
    registry = ToolRegistry()

    def broken_tool(arguments):
        raise RuntimeError("boom")

    registry.register("read_file", broken_tool)
    result = registry.dispatch(Action(type="read_file", arguments={"path": "README.md"}))

    assert result.ok is False
    assert result.error == "tool read_file failed: boom"
