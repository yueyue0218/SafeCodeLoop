import json
from datetime import datetime

from safecodeloop.cli import main


def test_main_contribution_demo_approves_and_writes_audit_log(
    tmp_path, capsys, monkeypatch
) -> None:
    def fail_if_production_approval_store_is_used(_workspace):
        raise AssertionError("demo must not access the production credential store")

    monkeypatch.setattr(
        "safecodeloop.cli._approval_store",
        fail_if_production_approval_store_is_used,
    )

    exit_code = main(
        [
            "demo",
            "main-contribution",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    audit_path = tmp_path / "main-contribution-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "feedback: test_failure -> pass" in output
    assert "approval: pending -> approved -> consumed" in output
    assert f"audit_log: {audit_path}" in output
    assert audit["schema_version"] == 1
    assert audit["demo"] == "main-contribution"
    assert audit["decision"] == "approve"
    assert audit["feedback_sequence"] == ["test_failure", "pass"]
    assert audit["approval"]["transitions"] == [
        "pending",
        "approved",
        "consumed",
    ]
    assert len(audit["approval"]["action_hash"]) == 64
    assert audit["approval"]["action_hash_algorithm"] == "HMAC-SHA256"
    assert audit["approval"]["rule_id"] == "config.approval.0"
    assert len(audit["approval"]["run_id"]) == 32
    assert audit["approval"]["step_id"] == 5
    assert "configured approval command pattern" in audit["approval"]["reason"]
    assert datetime.fromisoformat(audit["approval"]["created_at"])
    assert datetime.fromisoformat(audit["approval"]["updated_at"])
    assert audit["initial_run"]["status"] == "needs_approval"
    assert audit["resumed_run"]["status"] == "success"
    resumed_observation = audit["resumed_run"]["steps"][0]["observation"]
    assert resumed_observation["approval_status"] == "consumed"
    assert "approved-demo-action" in resumed_observation["data"]["stdout"]
    assert audit["final_status"] == "success"


def test_main_contribution_demo_can_reject_without_resuming(
    tmp_path, capsys
) -> None:
    exit_code = main(
        [
            "demo",
            "main-contribution",
            "--decision",
            "reject",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    audit = json.loads(
        (tmp_path / "main-contribution-audit.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert "approval: pending -> rejected" in output
    assert audit["decision"] == "reject"
    assert audit["approval"]["transitions"] == ["pending", "rejected"]
    assert audit["resumed_run"] is None
    assert audit["final_status"] == "rejected"
