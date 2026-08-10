from pathlib import Path

from safecodeloop.actions import Action
from safecodeloop.tools import create_file_tool_registry


def test_list_files_returns_workspace_relative_paths(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')", encoding="utf-8")
    registry = create_file_tool_registry(tmp_path)

    result = registry.dispatch(Action(type="list_files", arguments={}))

    assert result.ok is True
    assert result.data["files"] == ["README.md", "src/app.py"]


def test_read_file_returns_contents(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    registry = create_file_tool_registry(tmp_path)

    result = registry.dispatch(Action(type="read_file", arguments={"path": "README.md"}))

    assert result.ok is True
    assert result.data == {"path": "README.md", "content": "hello"}


def test_write_file_creates_parent_directories_inside_workspace(tmp_path):
    registry = create_file_tool_registry(tmp_path)

    result = registry.dispatch(
        Action(type="write_file", arguments={"path": "src/generated/app.py", "content": "print('ok')"})
    )

    assert result.ok is True
    assert result.data == {"path": "src/generated/app.py", "bytes_written": 11}
    assert (tmp_path / "src" / "generated" / "app.py").read_text(encoding="utf-8") == "print('ok')"


def test_write_file_outside_workspace_is_denied(tmp_path):
    registry = create_file_tool_registry(tmp_path)
    outside = Path("..") / "outside.txt"

    result = registry.dispatch(
        Action(type="write_file", arguments={"path": str(outside), "content": "nope"})
    )

    assert result.ok is False
    assert "outside workspace" in result.error
    assert not (tmp_path.parent / "outside.txt").exists()


def test_read_file_outside_workspace_is_denied(tmp_path):
    registry = create_file_tool_registry(tmp_path)

    result = registry.dispatch(Action(type="read_file", arguments={"path": "../secret.txt"}))

    assert result.ok is False
    assert "outside workspace" in result.error
