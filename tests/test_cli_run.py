import json

from safecodeloop.approval import ApprovalStore
from safecodeloop.actions import Action
from safecodeloop.cli import _write_run_log, main
from safecodeloop.llm import LLMError, LLMResponse
from safecodeloop.loop import LoopStep, RunResult
from safecodeloop.redaction import SecretRedactor


def test_run_cli_with_mock_script_succeeds_and_writes_file(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps(
            [
                {"type": "write_file", "path": "result.txt", "content": "done"},
                {"type": "finish", "message": "completed"},
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["run", "--mock-script", str(script), "--workspace", str(workspace), "write", "file"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "status: success" in output
    assert "completed" in output
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "done"


def test_safe_mock_run_does_not_initialize_approval_keyring(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    script.write_text(json.dumps([{"type": "finish", "message": "offline"}]), encoding="utf-8")

    def unavailable_store(workspace):
        raise AssertionError("safe mock run must not initialize approval storage")

    monkeypatch.setattr("safecodeloop.cli._approval_store", unavailable_store)

    assert main(["run", "--mock-script", str(script), "--workspace", str(workspace), "offline"]) == 0


def test_risky_mock_run_still_initializes_approval_store(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps([{"type": "run_command", "command": "python -m pip install requests"}]),
        encoding="utf-8",
    )
    calls = []
    real_store = ApprovalStore(tmp_path / "approvals.json", b"test-only-approval-signing-key")

    def tracked_store(workspace):
        calls.append(workspace)
        return real_store

    monkeypatch.setattr("safecodeloop.cli._approval_store", tracked_store)

    exit_code = main(["run", "--mock-script", str(script), "--workspace", str(workspace), "install"])

    assert exit_code == 1
    assert calls == [workspace]
    assert "approval_id:" in capsys.readouterr().out


def test_run_cli_applies_configured_approval_pattern(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    config = tmp_path / "config.json"
    script.write_text(
        json.dumps([{"type": "run_command", "command": "git status --short"}]),
        encoding="utf-8",
    )
    config.write_text(
        json.dumps({"approvalRequiredPatterns": [r"git status"]}),
        encoding="utf-8",
    )
    store = ApprovalStore(tmp_path / "approvals.json", b"test-only-approval-signing-key")
    monkeypatch.setattr("safecodeloop.cli._approval_store", lambda workspace: store)

    exit_code = main(
        [
            "run",
            "--mock-script",
            str(script),
            "--workspace",
            str(workspace),
            "--config",
            str(config),
            "inspect status",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "status: needs_approval" in output
    assert "approval_id:" in output


def test_run_cli_writes_log_file(tmp_path):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    log_path = tmp_path / "run-log.json"
    script.write_text(json.dumps([{"type": "finish", "message": "ok"}]), encoding="utf-8")

    exit_code = main(
        [
            "run",
            "--mock-script",
            str(script),
            "--workspace",
            str(workspace),
            "--log",
            str(log_path),
            "finish",
        ]
    )

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "success"
    assert payload["final_message"] == "ok"
    assert payload["steps"][0]["action"]["type"] == "finish"


def test_run_log_redacts_final_message_llm_action_and_observation(tmp_path):
    secret = "runtime-opaque-log-secret"
    result = RunResult(
        status="success",
        final_message=f"finished with {secret}",
        steps=[
            LoopStep(
                index=0,
                llm_response=f'{{"type":"write_file","content":"{secret}"}}',
                action=Action(
                    type="write_file",
                    arguments={"path": "result.txt", "content": secret},
                ),
                observation={
                    "kind": "tool_result",
                    "details": f"Bearer {secret}",
                    "nested": [f"OPENAI_API_KEY={secret}"],
                },
            )
        ],
    )
    path = tmp_path / "run-log.json"

    _write_run_log(path, result, redactor=SecretRedactor([secret]))

    serialized = path.read_text(encoding="utf-8")
    assert secret not in serialized
    assert serialized.count("[REDACTED]") >= 5


def test_cli_redacts_secret_like_final_message(tmp_path, capsys):
    secret = "sk-cli-final-message-secret"
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps([{"type": "finish", "message": secret}]),
        encoding="utf-8",
    )

    exit_code = main(
        ["run", "--mock-script", str(script), "--workspace", str(tmp_path / "work"), "finish"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert secret not in output
    assert "[REDACTED]" in output


def test_cli_redacts_secret_like_configuration_error(tmp_path, capsys):
    secret = "sk-cli-config-error-secret"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({secret: True}), encoding="utf-8")

    exit_code = main(["run", "--config", str(config), "inspect"])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert secret not in output
    assert "[REDACTED]" in output


def test_cli_redacts_registered_runtime_secret_from_exception(monkeypatch, capsys):
    secret = "runtime-opaque-cli-error-secret"

    def failing_llm_factory(config, mock_script, redactor):
        redactor.add_secret(secret)
        raise LLMError(f"provider failed while handling {secret}")

    monkeypatch.setattr("safecodeloop.cli._create_llm", failing_llm_factory)

    exit_code = main(["run", "inspect"])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert secret not in output
    assert "[REDACTED]" in output


def test_run_cli_returns_nonzero_for_blocked_action(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    script = tmp_path / "script.json"
    script.write_text(json.dumps([{"type": "run_command", "command": "rm -rf /"}]), encoding="utf-8")

    exit_code = main(["run", "--mock-script", str(script), "--workspace", str(workspace), "danger"])

    output = capsys.readouterr().out
    assert exit_code != 0
    assert "status: blocked" in output
    assert "recursive root deletion" in output


def test_run_cli_uses_configured_real_provider_without_mock_script(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "modelProvider": "openai-compatible",
                "model": "glm-5.2",
                "baseUrl": "https://njusehub.info/v1",
                "credentialProvider": "njusehub",
            }
        ),
        encoding="utf-8",
    )

    class FakeStore:
        def get_key(self, provider):
            return {
                "njusehub": "provider-secret",
                "safecodeloop-approval-signing-key": "approval-signing-secret",
            }.get(provider)

        def set_key(self, provider, value):
            raise AssertionError("existing fake credentials should not be overwritten")

    class FakeLLM:
        def generate(self, messages):
            return LLMResponse(
                content=json.dumps({"type": "finish", "message": "real provider selected"}),
                provider="fake",
            )

    monkeypatch.setattr("safecodeloop.cli.CredentialStore", FakeStore)
    monkeypatch.setattr("safecodeloop.cli.OpenAICompatibleLLM", lambda **kwargs: FakeLLM())

    exit_code = main(["run", "--config", str(config), "finish", "task"])

    assert exit_code == 0
    assert "real provider selected" in capsys.readouterr().out


def test_cli_approval_status_approve_and_reject(tmp_path, monkeypatch, capsys):
    from safecodeloop.actions import Action

    store = ApprovalStore(tmp_path / "approvals.json", b"test-only-approval-signing-key")
    first = store.create(
        Action(type="run_command", arguments={"command": "python -m pip install requests"}),
        "approval required",
    )
    second = store.create(
        Action(type="run_command", arguments={"command": "npm install"}),
        "approval required",
    )
    monkeypatch.setattr("safecodeloop.cli._approval_store", lambda workspace: store)

    assert main(["approval", "status", first.id, "--workspace", str(tmp_path)]) == 0
    assert "pending" in capsys.readouterr().out
    assert main(["approval", "approve", first.id, "--workspace", str(tmp_path)]) == 0
    assert "approved" in capsys.readouterr().out
    assert main(["approval", "reject", second.id, "--workspace", str(tmp_path)]) == 0
    assert "rejected" in capsys.readouterr().out


def test_cli_persists_approval_and_resumes_in_later_invocation(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    store = ApprovalStore(tmp_path / "approvals.json", b"test-only-approval-signing-key")
    monkeypatch.setattr("safecodeloop.cli._approval_store", lambda workspace: store)
    request_script = tmp_path / "request.json"
    request_script.write_text(
        json.dumps([{"type": "run_command", "command": "python -m pip install --version"}]),
        encoding="utf-8",
    )

    first_exit = main(
        [
            "run",
            "--mock-script",
            str(request_script),
            "--workspace",
            str(workspace),
            "inspect pip install command",
        ]
    )
    first_output = capsys.readouterr().out
    approval_id = first_output.split("approval_id: ", 1)[1].splitlines()[0]

    assert first_exit == 1
    assert "status: needs_approval" in first_output
    assert main(["approval", "approve", approval_id, "--workspace", str(workspace)]) == 0
    capsys.readouterr()

    resume_script = tmp_path / "resume.json"
    resume_script.write_text(
        json.dumps([{"type": "finish", "message": "resumed through CLI"}]),
        encoding="utf-8",
    )
    resumed_exit = main(
        [
            "run",
            "--resume",
            approval_id,
            "--mock-script",
            str(resume_script),
            "--workspace",
            str(workspace),
            "inspect pip install command",
        ]
    )

    resumed_output = capsys.readouterr().out
    assert resumed_exit == 0
    assert "status: success" in resumed_output
    assert "resumed through CLI" in resumed_output
