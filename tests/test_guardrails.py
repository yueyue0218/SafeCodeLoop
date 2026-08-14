import pytest

from safecodeloop.actions import Action
from safecodeloop.guardrails import GuardrailDecision, GuardrailEngine


def test_guardrail_blocks_rm_rf_root(tmp_path):
    engine = GuardrailEngine(tmp_path)

    decision = engine.check(Action(type="run_command", arguments={"command": "rm -rf /"}))

    assert decision.status == "blocked"
    assert "dangerous command" in decision.reason


def test_validation_action_cannot_bypass_command_guardrail(tmp_path):
    engine = GuardrailEngine(tmp_path)

    decision = engine.check(Action(type="run_validation", arguments={"command": "rm -rf /"}))

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


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf ./build",
        "rm -fr ./build",
        "rm --recursive --force ./build",
        "Remove-Item -Recurse -Force .\\build",
        "REMOVE-ITEM   -FORCE   -RECURSE   .\\build",
        "rmdir /s /q build",
        "del /f /q artifact.txt",
        "echo safe; rm -r -f ./build",
        "Write-Output safe | Remove-Item -Recurse -Force .\\build",
    ],
)
def test_guardrail_blocks_cross_shell_destructive_variants(tmp_path, command):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": command})
    )

    assert decision.status == "blocked"
    assert decision.rule_id.startswith("command.destructive")
    assert decision.severity == "critical"


def test_block_has_priority_over_approval(tmp_path):
    engine = GuardrailEngine(
        tmp_path,
        blocked_command_patterns=(r"pip install",),
        approval_required_patterns=(r"pip install",),
    )

    decision = engine.check(
        Action(type="run_command", arguments={"command": "python -m pip install requests"})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "config.blocked.0"


def test_configured_approval_pattern_is_applied(tmp_path):
    engine = GuardrailEngine(tmp_path, approval_required_patterns=(r"git status",))

    decision = engine.check(
        Action(type="run_command", arguments={"command": "git status --short"})
    )

    assert decision.status == "needs_approval"
    assert decision.rule_id == "config.approval.0"
    assert decision.severity == "medium"


@pytest.mark.parametrize(
    "command",
    [
        "git status && echo inspected",
        "pytest | tee results.txt",
        "Write-Output one; Write-Output two",
        "cmd /c echo nested",
        'bash -c "echo nested"',
        "echo $(whoami)",
    ],
)
def test_ambiguous_or_compound_shell_constructs_require_approval(tmp_path, command):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": command})
    )

    assert decision.status == "needs_approval"
    assert decision.rule_id in {"command.compound", "command.indirect_shell"}


@pytest.mark.parametrize(
    "command",
    [
        "powershell -EncodedCommand ZQBjAGgAbwAgAGgAaQA=",
        "pwsh -enc ZQBjAGgAbwAgAGgAaQA=",
        "powershell -Command Invoke-Expression $payload",
    ],
)
def test_obfuscated_shell_commands_are_blocked(tmp_path, command):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": command})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "command.obfuscated"


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "npm publish",
        "twine upload dist/*",
        "docker push example/image:latest",
        "kubectl apply -f deployment.yaml",
        "terraform apply",
        "curl -X POST https://example.invalid/api",
        "npm install -g typescript",
    ],
)
def test_external_writes_and_installations_require_approval(tmp_path, command):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": command})
    )

    assert decision.status == "needs_approval"
    assert decision.rule_id in {"command.external_write", "command.dependency_install"}


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        ".ssh/id_rsa",
        "credentials.json",
        ".git-credentials",
        ".safecodeloop/approvals.json",
    ],
)
def test_sensitive_file_paths_are_blocked(tmp_path, path):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="read_file", arguments={"path": path})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "path.sensitive"


def test_env_example_is_not_treated_as_a_secret_file(tmp_path):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="read_file", arguments={"path": ".env.example"})
    )

    assert decision == GuardrailDecision.allow()


def test_list_files_cannot_escape_workspace(tmp_path):
    outside = tmp_path.parent / "outside-list"
    decision = GuardrailEngine(tmp_path).check(
        Action(type="list_files", arguments={"path": str(outside)})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "path.outside_workspace"


def test_symlink_escape_is_blocked(tmp_path):
    outside = tmp_path.parent / "outside-symlink-target"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    decision = GuardrailEngine(tmp_path).check(
        Action(type="read_file", arguments={"path": "linked/secret.txt"})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "path.outside_workspace"


def test_symlink_alias_cannot_hide_sensitive_file(tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("TOKEN=secret", encoding="utf-8")
    link = tmp_path / "public.txt"
    try:
        link.symlink_to(secret)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    decision = GuardrailEngine(tmp_path).check(
        Action(type="read_file", arguments={"path": "public.txt"})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "path.sensitive"


@pytest.mark.parametrize(
    "command",
    [
        "Get-Content .env",
        "cat ~/.ssh/id_ed25519",
        "type credentials.json",
    ],
)
def test_commands_cannot_read_sensitive_paths(tmp_path, command):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": command})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "command.sensitive_path"


def test_command_parent_traversal_is_blocked(tmp_path):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": "type ..\\secret.txt"})
    )

    assert decision.status == "blocked"
    assert decision.rule_id == "command.outside_workspace"


def test_safe_single_command_has_explicit_allow_metadata(tmp_path):
    decision = GuardrailEngine(tmp_path).check(
        Action(type="run_command", arguments={"command": "git status --short"})
    )

    assert decision == GuardrailDecision.allow()
    assert decision.rule_id == "default.allow"
    assert decision.severity == "none"
