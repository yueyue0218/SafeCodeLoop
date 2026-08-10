from safecodeloop.actions import Action
from safecodeloop.guardrails import GuardrailDecision, GuardrailEngine


def test_guardrail_blocks_rm_rf_root(tmp_path):
    engine = GuardrailEngine(tmp_path)

    decision = engine.check(Action(type="run_command", arguments={"command": "rm -rf /"}))

    assert decision.status == "blocked"
    assert "dangerous command" in decision.reason


def test_guardrail_blocks_database_delete_command(tmp_path):
    engine = GuardrailEngine(tmp_path)

    decision = engine.check(
        Action(type="run_command", arguments={"command": "psql app -c \"DROP DATABASE production\""})
    )

    assert decision.status == "blocked"
    assert "database deletion" in decision.reason


def test_guardrail_blocks_write_outside_workspace(tmp_path):
    engine = GuardrailEngine(tmp_path)
    outside = tmp_path.parent / "outside.txt"

    decision = engine.check(Action(type="write_file", arguments={"path": str(outside), "content": "bad"}))

    assert decision.status == "blocked"
    assert "outside workspace" in decision.reason


def test_guardrail_marks_dependency_install_as_needs_approval(tmp_path):
    engine = GuardrailEngine(tmp_path)

    decision = engine.check(Action(type="run_command", arguments={"command": "python -m pip install requests"}))

    assert decision.status == "needs_approval"
    assert "dependency install" in decision.reason


def test_guardrail_allows_safe_workspace_read(tmp_path):
    engine = GuardrailEngine(tmp_path)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    decision = engine.check(Action(type="read_file", arguments={"path": "README.md"}))

    assert decision == GuardrailDecision.allow()
