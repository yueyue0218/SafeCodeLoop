import json
from pathlib import Path

from safecodeloop.cli import main


def test_main_contribution_demo_combines_feedback_and_guardrail(tmp_path, capsys):
    repo_root = Path(__file__).resolve().parents[1]
    demo_script = repo_root / "demos" / "governance_feedback_depth.json"
    log_path = tmp_path / "main-contribution-log.json"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"maxSteps": 6}), encoding="utf-8")

    exit_code = main(
        [
            "run",
            "--mock-script",
            str(demo_script),
            "--config",
            str(config_path),
            "--workspace",
            str(tmp_path / "workspace"),
            "--log",
            str(log_path),
            "demonstrate",
            "feedback",
            "and",
            "guardrails",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    observations = [step["observation"] for step in payload["steps"]]

    assert exit_code == 1
    assert "status: blocked" in output
    assert payload["status"] == "blocked"
    assert any(
        observation.get("kind") == "feedback"
        and observation.get("feedback_kind") == "test_failure"
        for observation in observations
    )
    assert any(
        observation.get("kind") == "feedback"
        and observation.get("feedback_kind") == "pass"
        for observation in observations
    )
    assert observations[-1]["kind"] == "guardrail_result"
    assert observations[-1]["status"] == "blocked"
    assert "recursive root deletion" in payload["final_message"]
