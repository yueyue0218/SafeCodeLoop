from dataclasses import dataclass

from safecodeloop.tools import ToolResult


@dataclass(frozen=True)
class Feedback:
    kind: str
    passed: bool
    summary: str
    details: str = ""

    def to_observation(self) -> dict[str, str | bool]:
        return {
            "kind": "feedback",
            "feedback_kind": self.kind,
            "passed": self.passed,
            "summary": self.summary,
            "details": self.details,
        }


class Validator:
    def validate(self, result: ToolResult) -> Feedback:
        return classify_tool_result(result)


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
        kind="command_failure",
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
