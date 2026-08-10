from collections.abc import Callable
from dataclasses import dataclass, field
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
