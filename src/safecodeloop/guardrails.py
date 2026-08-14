from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re

from safecodeloop.actions import Action


_STATUS_PRIORITY = {"allowed": 0, "needs_approval": 1, "blocked": 2}
_SEVERITY_PRIORITY = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    reason: str = ""
    rule_id: str = "default.allow"
    severity: str = "none"

    @classmethod
    def allow(cls) -> "GuardrailDecision":
        return cls(status="allowed")

    @classmethod
    def block(
        cls,
        reason: str,
        rule_id: str = "command.blocked",
        severity: str = "critical",
    ) -> "GuardrailDecision":
        return cls(status="blocked", reason=reason, rule_id=rule_id, severity=severity)

    @classmethod
    def require_approval(
        cls,
        reason: str,
        rule_id: str = "command.approval_required",
        severity: str = "medium",
    ) -> "GuardrailDecision":
        return cls(
            status="needs_approval",
            reason=reason,
            rule_id=rule_id,
            severity=severity,
        )


class GuardrailEngine:
    def __init__(
        self,
        workspace_root: str | Path,
        blocked_command_patterns: tuple[str, ...] = (),
        approval_required_patterns: tuple[str, ...] = (),
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.blocked_command_patterns = tuple(blocked_command_patterns)
        self.approval_required_patterns = tuple(approval_required_patterns)
        self._blocked_patterns = tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in self.blocked_command_patterns
        )
        self._approval_patterns = tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in self.approval_required_patterns
        )

    def check(self, action: Action) -> GuardrailDecision:
        if action.type in {"run_command", "run_validation"}:
            return self._check_command(str(action.arguments.get("command", "")))

        if action.type in {"list_files", "read_file", "write_file"}:
            default_path = "." if action.type == "list_files" else ""
            return self._check_workspace_path(str(action.arguments.get("path", default_path)))

        return GuardrailDecision.allow()

    def _check_workspace_path(self, raw_path: str) -> GuardrailDecision:
        if not raw_path:
            return GuardrailDecision.block(
                "missing workspace path", "path.missing", "high"
            )

        try:
            candidate = (self.workspace_root / raw_path).resolve()
        except (OSError, RuntimeError, ValueError):
            return GuardrailDecision.block(
                f"invalid workspace path: {raw_path}", "path.invalid", "high"
            )

        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            return GuardrailDecision.block(
                f"path outside workspace: {raw_path}",
                "path.outside_workspace",
                "critical",
            )
        relative_candidate = candidate.relative_to(self.workspace_root)
        if _is_sensitive_path(raw_path) or _is_sensitive_path(str(relative_candidate)):
            return GuardrailDecision.block(
                f"sensitive path access is blocked: {raw_path}",
                "path.sensitive",
                "critical",
            )
        return GuardrailDecision.allow()

    def _check_command(self, command: str) -> GuardrailDecision:
        normalized = " ".join(command.lower().split())
        decisions: list[GuardrailDecision] = []

        for index, pattern in enumerate(self._blocked_patterns):
            if pattern.search(command):
                decisions.append(
                    GuardrailDecision.block(
                        f"configured blocked command pattern matched: {self.blocked_command_patterns[index]}",
                        f"config.blocked.{index}",
                        "critical",
                    )
                )

        for index, pattern in enumerate(self._approval_patterns):
            if pattern.search(command):
                decisions.append(
                    GuardrailDecision.require_approval(
                        f"configured approval command pattern matched: {self.approval_required_patterns[index]}",
                        f"config.approval.{index}",
                        "medium",
                    )
                )

        if _is_recursive_root_delete(normalized):
            decisions.append(
                GuardrailDecision.block(
                    "dangerous command: recursive root deletion",
                    "command.destructive.root_delete",
                    "critical",
                )
            )
        elif _contains_destructive_delete(command):
            decisions.append(
                GuardrailDecision.block(
                    "dangerous command: destructive recursive or forced deletion",
                    "command.destructive.recursive_delete",
                    "critical",
                )
            )

        if re.search(r"\b(drop|delete)\s+database\b", normalized):
            decisions.append(
                GuardrailDecision.block(
                    "database deletion command is blocked",
                    "command.destructive.database_delete",
                    "critical",
                )
            )

        if re.search(
            r"(?:\b(?:powershell|pwsh)\b[^\r\n]*(?:-(?:enc|encodedcommand)\b|\b(?:invoke-expression|iex)\b)|\bfrombase64string\b)",
            command,
            re.IGNORECASE,
        ):
            decisions.append(
                GuardrailDecision.block(
                    "obfuscated or dynamically evaluated shell command is blocked",
                    "command.obfuscated",
                    "critical",
                )
            )

        if _command_mentions_sensitive_path(command):
            decisions.append(
                GuardrailDecision.block(
                    "command access to a sensitive path is blocked",
                    "command.sensitive_path",
                    "critical",
                )
            )

        if re.search(r"(?:^|[\s\"'])(?:\.\.[\\/])", command):
            decisions.append(
                GuardrailDecision.block(
                    "command path outside workspace is blocked",
                    "command.outside_workspace",
                    "critical",
                )
            )

        if _is_dependency_install(normalized):
            decisions.append(
                GuardrailDecision.require_approval(
                    "dependency install requires approval",
                    "command.dependency_install",
                    "high",
                )
            )

        if _is_external_write(normalized):
            decisions.append(
                GuardrailDecision.require_approval(
                    "external state-changing command requires approval",
                    "command.external_write",
                    "high",
                )
            )

        if re.search(
            r"(?:^|\s)(?:cmd(?:\.exe)?\s+/[ck]|(?:powershell|pwsh)(?:\.exe)?\s+-(?:command|c)\b|(?:ba|z|k|c)?sh\s+-c\b)|\$\(|`",
            command,
            re.IGNORECASE,
        ):
            decisions.append(
                GuardrailDecision.require_approval(
                    "indirect shell execution requires approval",
                    "command.indirect_shell",
                    "high",
                )
            )

        if re.search(r"&&|\|\||(?<!\|)\|(?!\|)|;|[\r\n]", command):
            decisions.append(
                GuardrailDecision.require_approval(
                    "compound shell command requires approval",
                    "command.compound",
                    "medium",
                )
            )

        if not decisions:
            return GuardrailDecision.allow()
        return max(
            decisions,
            key=lambda decision: (
                _STATUS_PRIORITY[decision.status],
                _SEVERITY_PRIORITY[decision.severity],
            ),
        )


def _is_recursive_root_delete(command: str) -> bool:
    return bool(
        re.search(
            r"\brm\s+(?=[^\r\n;&|]*(?:--recursive|-[a-z]*r))(?=[^\r\n;&|]*(?:--force|-[a-z]*f))[^\r\n;&|]*\s/(?:\s|$)",
            command,
        )
    )


def _contains_destructive_delete(command: str) -> bool:
    for match in re.finditer(
        r"(?:^|[;&|]\s*)rm\s+([^\r\n;&|]+)", command, re.IGNORECASE
    ):
        args = match.group(1)
        flags = re.findall(r"(?<!\S)(--?[a-z-]+)", args, re.IGNORECASE)
        recursive = any(
            flag.lower() == "--recursive"
            or (flag.startswith("-") and "r" in flag[1:].lower())
            for flag in flags
        )
        force = any(
            flag.lower() == "--force"
            or (flag.startswith("-") and "f" in flag[1:].lower())
            for flag in flags
        )
        if recursive and force:
            return True

    for match in re.finditer(
        r"(?:^|[;&|]\s*)(?:remove-item|ri|rm)\s+([^\r\n;&|]+)",
        command,
        re.IGNORECASE,
    ):
        args = match.group(1)
        if re.search(r"-recurse\b", args, re.IGNORECASE) and re.search(
            r"-force\b", args, re.IGNORECASE
        ):
            return True

    if re.search(
        r"(?:^|[;&|]\s*)(?:rmdir|rd)\s+[^\r\n;&|]*\/s\b",
        command,
        re.IGNORECASE,
    ):
        return True
    return bool(re.search(r"(?:^|[;&|]\s*)(?:del|erase)\s+", command, re.IGNORECASE))


def _is_dependency_install(command: str) -> bool:
    return bool(
        re.search(r"\b(?:pip|pipx|npm|pnpm|yarn|poetry|uv)\s+(?:install|add)\b", command)
        or re.search(r"\bpython(?:\.exe)?\s+-m\s+pip\s+install\b", command)
        or re.search(
            r"\b(?:apt(?:-get)?|dnf|yum|winget|choco|scoop|brew)\s+(?:install|add)\b",
            command,
        )
    )


def _is_external_write(command: str) -> bool:
    patterns = (
        r"\bgit\s+push\b",
        r"\bgh\s+(?:release|pr)\s+(?:create|edit|delete|merge|close|reopen|upload)\b",
        r"\b(?:npm|cargo)\s+publish\b",
        r"\btwine\s+upload\b",
        r"\bdocker\s+push\b",
        r"\bkubectl\s+(?:apply|create|delete|patch|replace|set|scale|rollout)\b",
        r"\bterraform\s+(?:apply|destroy|import)\b",
        r"\bhelm\s+(?:install|upgrade|uninstall)\b",
        r"\bcurl\b[^\r\n]*(?:\s-x\s*(?:post|put|patch|delete)\b|\s--request\s+(?:post|put|patch|delete)\b)",
    )
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in patterns)


def _is_sensitive_path(raw_path: str) -> bool:
    normalized = str(PurePosixPath(raw_path.replace("\\", "/"))).lower()
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if not parts:
        return False
    name = parts[-1]
    if name in {".env.example", ".env.sample", ".env.template"}:
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if ".ssh" in parts or ".safecodeloop" in parts:
        return True
    return name in {
        "credentials.json",
        ".git-credentials",
        "id_rsa",
        "id_ed25519",
    }


def _command_mentions_sensitive_path(command: str) -> bool:
    normalized = command.replace("\\", "/").lower()
    return bool(
        re.search(
            r"(?:^|[\s\"'/])\.env(?:\.(?!example\b|sample\b|template\b)[\w.-]+)?(?:$|[\s\"'])",
            normalized,
        )
        or re.search(r"(?:^|[\s\"'~/])\.ssh(?:/|$)", normalized)
        or re.search(r"(?:^|[\s\"'/])\.safecodeloop(?:/|$)", normalized)
        or re.search(r"\b(?:credentials\.json|\.git-credentials|id_rsa|id_ed25519)\b", normalized)
    )
