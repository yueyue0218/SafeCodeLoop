import json
from pathlib import Path

from safecodeloop.cli import main


def test_dangerous_action_demo_is_blocked(tmp_path, capsys):
    repo_root = Path(__file__).resolve().parents[1]
    demo_script = repo_root / "demos" / "dangerous_action.json"
    log_path = tmp_path / "dangerous-action-log.json"

    exit_code = main(
        [
            "run",
            "--mock-script",
            str(demo_script),
            "--workspace",
            str(tmp_path / "workspace"),
            "--log",
            str(log_path),
            "demonstrate",
            "dangerous",
            "command",
            "blocking",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(log_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert "status: blocked" in output
    assert payload["status"] == "blocked"
    assert payload["steps"][0]["action"]["type"] == "run_command"
    assert payload["steps"][0]["observation"]["kind"] == "guardrail_result"
    assert payload["steps"][0]["observation"]["status"] == "blocked"
    assert "recursive root deletion" in payload["final_message"]
