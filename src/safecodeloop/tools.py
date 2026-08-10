import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from safecodeloop.actions import Action


ToolHandler = Callable[[dict[str, Any]], "ToolResult"]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_observation(self, tool_name: str) -> dict[str, Any]:
        return {
            "kind": "tool_result",
            "tool": tool_name,
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
        }


class ToolRegistry:
    def __init__(self):
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if not name:
            raise ValueError("tool name must not be empty")
        self._handlers[name] = handler

    def dispatch(self, action: Action) -> ToolResult:
        handler = self._handlers.get(action.type)
        if handler is None:
            return ToolResult(ok=False, error=f"unregistered tool: {action.type}")

        try:
            return handler(dict(action.arguments))
        except Exception as exc:
            return ToolResult(ok=False, error=f"tool {action.type} failed: {exc}")


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve_inside(self, requested_path: str | Path = ".") -> Path:
        candidate = (self.root / requested_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"path is outside workspace: {requested_path}")
        return candidate

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()


def create_file_tool_registry(workspace_root: str | Path) -> ToolRegistry:
    workspace = Workspace(workspace_root)
    registry = ToolRegistry()

    def list_files(arguments: dict[str, Any]) -> ToolResult:
        base = workspace.resolve_inside(arguments.get("path", "."))
        if not base.exists():
            return ToolResult(ok=False, error=f"path does not exist: {arguments.get('path', '.')}")
        files = sorted(
            workspace.relative(path)
            for path in base.rglob("*")
            if path.is_file()
        )
        return ToolResult(ok=True, data={"files": files})

    def read_file(arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path")
        if not raw_path:
            return ToolResult(ok=False, error="missing required field: path")
        path = workspace.resolve_inside(raw_path)
        if not path.is_file():
            return ToolResult(ok=False, error=f"file does not exist: {raw_path}")
        return ToolResult(
            ok=True,
            data={"path": workspace.relative(path), "content": path.read_text(encoding="utf-8")},
        )

    def write_file(arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path")
        if not raw_path:
            return ToolResult(ok=False, error="missing required field: path")
        content = str(arguments.get("content", ""))
        path = workspace.resolve_inside(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            ok=True,
            data={"path": workspace.relative(path), "bytes_written": len(content.encode("utf-8"))},
        )

    registry.register("list_files", list_files)
    registry.register("read_file", read_file)
    registry.register("write_file", write_file)
    return registry


def create_command_tool_registry(workspace_root: str | Path, timeout_seconds: float = 10.0) -> ToolRegistry:
    workspace = Workspace(workspace_root)
    registry = ToolRegistry()

    def run_command(arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command")
        if not command:
            return ToolResult(ok=False, error="missing required field: command")

        try:
            completed = subprocess.run(
                str(command),
                cwd=workspace.root,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                ok=False,
                data={
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                    "timeout_seconds": timeout_seconds,
                },
                error="command timed out",
            )

        data = {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return ToolResult(
                ok=False,
                data=data,
                error=f"command exited with code {completed.returncode}",
            )
        return ToolResult(ok=True, data=data)

    registry.register("run_command", run_command)
    return registry
