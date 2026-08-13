from dataclasses import dataclass
from pathlib import Path
import re

from safecodeloop.actions import Action


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    reason: str = ""

    @classmethod
    def allow(cls) -> "GuardrailDecision":
        return cls(status="allowed")

    @classmethod
    def block(cls, reason: str) -> "GuardrailDecision":
        return cls(status="blocked", reason=reason)

    @classmethod
    def require_approval(cls, reason: str) -> "GuardrailDecision":
        return cls(status="needs_approval", reason=reason)


class GuardrailEngine:
    def __init__(self, workspace_root: str | Path, blocked_command_patterns: tuple[str, ...] = ()):
        self.workspace_root = Path(workspace_root).resolve()
        self.blocked_command_patterns = blocked_command_patterns

    def check(self, action: Action) -> GuardrailDecision:
        if action.type in {"run_command", "run_validation"}:
            return self._check_command(str(action.arguments.get("command", "")))

        if action.type in {"read_file", "write_file"}:
            return self._check_workspace_path(str(action.arguments.get("path", "")))

        return GuardrailDecision.allow()

    def _check_workspace_path(self, raw_path: str) -> GuardrailDecision:
        if not raw_path:
            return GuardrailDecision.block("missing workspace path")

        candidate = (self.workspace_root / raw_path).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            return GuardrailDecision.block(f"path outside workspace: {raw_path}")
        return GuardrailDecision.allow()

    def _check_command(self, command: str) -> GuardrailDecision:
        normalized = " ".join(command.lower().split())

        for pattern in self.blocked_command_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return GuardrailDecision.block(f"configured blocked command pattern matched: {pattern}")

        if re.search(r"\brm\s+-[^\n;]*r[^\n;]*f\s+/", normalized):
            return GuardrailDecision.block("dangerous command: recursive root deletion")

        if re.search(r"\b(drop|delete)\s+database\b", normalized):
            return GuardrailDecision.block("database deletion command is blocked")

        if re.search(r"\b(pip|npm|pnpm|yarn|poetry)\s+(install|add)\b", normalized):
            return GuardrailDecision.require_approval("dependency install requires approval")

        if " -m pip install " in f" {normalized} ":
            return GuardrailDecision.require_approval("dependency install requires approval")

        return GuardrailDecision.allow()
