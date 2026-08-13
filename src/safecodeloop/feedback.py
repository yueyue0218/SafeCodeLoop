from dataclasses import dataclass
import hashlib
import re

from safecodeloop.tools import ToolResult


@dataclass(frozen=True)
class Feedback:
    kind: str
    passed: bool
    summary: str
    details: str = ""

    def to_observation(self) -> dict[str, str | bool | int]:
        return {
            "kind": "feedback",
            "feedback_kind": self.kind,
            "passed": self.passed,
            "summary": self.summary,
            "details": self.details,
            "evidence_sha256": hashlib.sha256(self.details.encode("utf-8")).hexdigest(),
            "evidence_chars": len(self.details),
            "evidence_location": "run_log.steps[].observation.details",
        }

    def to_context_observation(self, max_details_chars: int = 1200) -> dict[str, str | bool | int]:
        observation = self.to_observation()
        details, truncated = _bounded_details(self.details, max_details_chars)
        observation["details"] = details
        observation["details_truncated"] = truncated
        return observation


class Validator:
    def __init__(self, max_context_details_chars: int = 1200):
        if max_context_details_chars < 80:
            raise ValueError("max_context_details_chars must be at least 80")
        self.max_context_details_chars = max_context_details_chars

    def validate(self, result: ToolResult) -> Feedback:
        return classify_tool_result(result)

    def context_observation(self, feedback: Feedback) -> dict[str, str | bool | int]:
        return feedback.to_context_observation(self.max_context_details_chars)


def classify_tool_result(result: ToolResult) -> Feedback:
    stdout = str(result.data.get("stdout", ""))
    stderr = str(result.data.get("stderr", ""))
    combined_output = "\n".join(part for part in (stdout, stderr) if part)

    if result.error == "command timed out" or "timeout_seconds" in result.data:
        timeout = result.data.get("timeout_seconds", "unknown")
        return Feedback(
            kind="timeout",
            passed=False,
            summary=f"Command timed out after {timeout} seconds.",
            details=combined_output,
        )

    if "SyntaxError" in combined_output:
        return Feedback(
            kind="syntax_error",
            passed=False,
            summary="Python syntax error detected.",
            details=combined_output,
        )

    if _looks_like_type_error(combined_output):
        return Feedback(
            kind="type_error",
            passed=False,
            summary="Static type checking failure detected.",
            details=combined_output,
        )

    if _looks_like_lint_failure(combined_output):
        return Feedback(
            kind="lint_failure",
            passed=False,
            summary="Lint failure detected.",
            details=combined_output,
        )

    if _looks_like_environment_error(combined_output, result.error):
        return Feedback(
            kind="environment_error",
            passed=False,
            summary="Validation environment failure detected.",
            details=combined_output or result.error,
        )

    if _looks_like_pytest_failure(combined_output):
        return Feedback(
            kind="test_failure",
            passed=False,
            summary="Test failure detected.",
            details=combined_output,
        )

    if result.ok and result.data.get("exit_code") == 0:
        return Feedback(
            kind="pass",
            passed=True,
            summary="Command completed with exit code 0.",
            details=combined_output,
        )

    exit_code = result.data.get("exit_code", "unknown")
    return Feedback(
        kind="unknown_failure",
        passed=False,
        summary=f"Command failed with exit code {exit_code}.",
        details=combined_output or result.error,
    )


def _looks_like_pytest_failure(output: str) -> bool:
    return (
        "FAILED " in output
        or "== FAILURES ==" in output
        or " short test summary info " in output
        or "AssertionError" in output
    )


def _looks_like_type_error(output: str) -> bool:
    lowered = output.lower()
    return (
        "mypy" in lowered
        or "pyright" in lowered
        or "incompatible types" in lowered
        or bool(re.search(r"error: .+\[[a-z-]+\]", output, re.IGNORECASE))
    )


def _looks_like_lint_failure(output: str) -> bool:
    return bool(re.search(r"(?:^|\n).+?:\d+:\d+:\s+[A-Z]\d{3,4}\b", output))


def _looks_like_environment_error(output: str, error: str) -> bool:
    combined = f"{output}\n{error}".lower()
    markers = (
        "modulenotfounderror",
        "no module named",
        "command not found",
        "is not recognized as an internal or external command",
        "no such file or directory",
        "permission denied",
    )
    return any(marker in combined for marker in markers)


def _bounded_details(details: str, limit: int) -> tuple[str, bool]:
    if len(details) <= limit:
        return details, False

    diagnostic_lines = [
        line
        for line in details.splitlines()
        if re.search(
            r"FAILED |Error|error:|warning:|\b[A-Z]\d{3,4}\b|No module named|not found|timed out",
            line,
        )
    ]
    marker = "[output truncated]"
    selected = "\n".join(diagnostic_lines)
    if selected:
        bounded = f"{marker}\n{selected}"
        return bounded[:limit], True

    head_size = max(1, (limit - len(marker) - 2) // 2)
    tail_size = max(1, limit - len(marker) - 2 - head_size)
    return f"{details[:head_size]}\n{marker}\n{details[-tail_size:]}", True
