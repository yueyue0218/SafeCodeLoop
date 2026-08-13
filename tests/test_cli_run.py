import json

import pytest

from safecodeloop.approval import ApprovalStore
from safecodeloop.cli import main
from safecodeloop.llm import LLMResponse


@pytest.fixture(autouse=True)
def isolated_approval_store(tmp_path, monkeypatch):
    store = ApprovalStore(
        tmp_path / "isolated-approvals.json",
        b"test-only-approval-signing-key",
    )
    monkeypatch.setattr("safecodeloop.cli._approval_store", lambda workspace: store)
    return store


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
