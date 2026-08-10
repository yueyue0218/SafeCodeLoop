import sys

from safecodeloop.actions import Action
from safecodeloop.tools import create_command_tool_registry


def test_command_tool_runs_command_and_captures_stdout(tmp_path):
    registry = create_command_tool_registry(tmp_path)

    result = registry.dispatch(
        Action(type="run_command", arguments={"command": f"{sys.executable} -c \"print('hello')\""})
    )

    assert result.ok is True
    assert result.data["exit_code"] == 0
    assert result.data["stdout"].strip() == "hello"
    assert result.data["stderr"] == ""


def test_command_tool_captures_stderr_and_exit_code(tmp_path):
    registry = create_command_tool_registry(tmp_path)
    command = f"{sys.executable} -c \"import sys; print('bad', file=sys.stderr); sys.exit(3)\""

    result = registry.dispatch(Action(type="run_command", arguments={"command": command}))

    assert result.ok is False
    assert result.data["exit_code"] == 3
    assert result.data["stdout"] == ""
    assert result.data["stderr"].strip() == "bad"
    assert result.error == "command exited with code 3"


def test_command_tool_timeout_returns_structured_result(tmp_path):
    registry = create_command_tool_registry(tmp_path, timeout_seconds=0.1)
    command = f"{sys.executable} -c \"import time; time.sleep(2)\""

    result = registry.dispatch(Action(type="run_command", arguments={"command": command}))

    assert result.ok is False
    assert result.error == "command timed out"
    assert result.data["timeout_seconds"] == 0.1


def test_command_tool_runs_in_workspace(tmp_path):
    registry = create_command_tool_registry(tmp_path)
    command = f"{sys.executable} -c \"from pathlib import Path; Path('created.txt').write_text('ok')\""

    result = registry.dispatch(Action(type="run_command", arguments={"command": command}))

    assert result.ok is True
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "ok"


def test_command_tool_requires_command_argument(tmp_path):
    registry = create_command_tool_registry(tmp_path)

    result = registry.dispatch(Action(type="run_command", arguments={}))

    assert result.ok is False
    assert result.error == "missing required field: command"
