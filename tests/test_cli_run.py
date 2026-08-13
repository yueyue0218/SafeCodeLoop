import json

from safecodeloop.cli import main


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
