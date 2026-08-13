import json
from pathlib import Path

from safecodeloop.cli import main


def test_feedback_demo_corrects_after_failure(tmp_path):
    root = Path(__file__).resolve().parents[1]
    log = tmp_path / "feedback.json"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"maxSteps": 6}), encoding="utf-8")

    exit_code = main(
        [
            "run",
            "--mock-script",
            str(root / "demos" / "feedback_correction.json"),
            "--config",
            str(config),
            "--workspace",
            str(tmp_path / "workspace"),
            "--log",
            str(log),
            "correct",
            "a",
            "failing",
            "implementation",
        ]
    )

    payload = json.loads(log.read_text(encoding="utf-8"))
    feedback = [step["observation"].get("feedback_kind") for step in payload["steps"]]

    assert exit_code == 0
    assert payload["status"] == "success"
    assert "test_failure" in feedback
    assert "pass" in feedback
    assert (tmp_path / "workspace" / "calc.py").read_text(encoding="utf-8").endswith("a + b\n")
