import pytest

from safecodeloop.feedback import Feedback, Validator, classify_tool_result
from safecodeloop.tools import ToolResult


def test_exit_code_zero_is_classified_as_pass():
    result = ToolResult(ok=True, data={"exit_code": 0, "stdout": "3 passed", "stderr": ""})

    feedback = classify_tool_result(result)

    assert feedback.kind == "pass"
    assert feedback.passed is True
    assert "exit code 0" in feedback.summary


def test_pytest_failure_output_is_classified_as_test_failure():
    result = ToolResult(
        ok=False,
        data={
            "exit_code": 1,
            "stdout": "FAILED tests/test_app.py::test_add - AssertionError",
            "stderr": "",
        },
        error="command exited with code 1",
    )

    feedback = classify_tool_result(result)

    assert feedback.kind == "test_failure"
    assert feedback.passed is False
    assert "FAILED tests/test_app.py::test_add" in feedback.details


def test_syntax_error_output_is_classified_as_syntax_error():
    result = ToolResult(
        ok=False,
        data={
            "exit_code": 1,
            "stdout": "",
            "stderr": "SyntaxError: invalid syntax",
        },
        error="command exited with code 1",
    )

    feedback = classify_tool_result(result)

    assert feedback.kind == "syntax_error"
    assert feedback.passed is False
    assert "SyntaxError" in feedback.details


def test_timeout_result_is_classified_as_timeout():
    result = ToolResult(
        ok=False,
        data={"stdout": "", "stderr": "", "timeout_seconds": 0.1},
        error="command timed out",
    )

    feedback = classify_tool_result(result)

    assert feedback.kind == "timeout"
    assert feedback.passed is False
    assert "0.1" in feedback.summary


def test_validator_classifies_tool_result():
    validator = Validator()
    result = ToolResult(ok=True, data={"exit_code": 0, "stdout": "", "stderr": ""})

    assert validator.validate(result) == Feedback(
        kind="pass",
        passed=True,
        summary="Command completed with exit code 0.",
        details="",
    )


@pytest.mark.parametrize(
    ("stdout", "stderr", "expected_kind"),
    [
        ("", "error: Incompatible types in assignment  [assignment]", "type_error"),
        ("src/app.py:1:1: F401 unused import", "", "lint_failure"),
        ("", "ModuleNotFoundError: No module named 'missing_package'", "environment_error"),
        ("", "command stopped for an unrecognized reason", "unknown_failure"),
    ],
)
def test_failure_categories_are_specific(stdout, stderr, expected_kind):
    result = ToolResult(
        ok=False,
        data={"exit_code": 1, "stdout": stdout, "stderr": stderr},
        error="command exited with code 1",
    )

    assert classify_tool_result(result).kind == expected_kind


def test_feedback_context_is_bounded_but_full_details_are_preserved():
    marker = "FAILED tests/test_app.py::test_add - AssertionError"
    raw_output = "x" * 800 + "\n" + marker + "\n" + "y" * 800
    feedback = classify_tool_result(
        ToolResult(
            ok=False,
            data={"exit_code": 1, "stdout": raw_output, "stderr": ""},
            error="command exited with code 1",
        )
    )

    context = feedback.to_context_observation(max_details_chars=240)

    assert feedback.details == raw_output
    assert len(context["details"]) <= 240
    assert marker in context["details"]
    assert context["details_truncated"] is True
    assert context["evidence_chars"] == len(raw_output)
    assert len(context["evidence_sha256"]) == 64
    assert context["evidence_location"] == "run_log.steps[].observation.details"
