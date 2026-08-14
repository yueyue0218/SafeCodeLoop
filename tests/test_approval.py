import json
from datetime import datetime

import pytest

from safecodeloop.actions import Action
from safecodeloop.approval import ApprovalError, ApprovalStore, canonical_action_hash


SIGNING_KEY = b"test-only-approval-signing-key"


def test_canonical_action_hash_is_stable_across_argument_order():
    first = Action(
        type="run_command",
        arguments={"command": "echo governed", "environment": {"B": "2", "A": "1"}},
    )
    reordered = Action(
        type="run_command",
        arguments={"environment": {"A": "1", "B": "2"}, "command": "echo governed"},
    )

    assert canonical_action_hash(first, SIGNING_KEY) == canonical_action_hash(
        reordered, SIGNING_KEY
    )


def test_pending_approval_persists_canonical_action_and_hash(tmp_path):
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})

    record = store.create(
        action,
        "dependency install requires approval",
        run_id="run-123",
        step_id=4,
        rule_id="command.dependency_install",
    )
    reloaded = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY).get(record.id)

    assert reloaded.status == "pending"
    assert reloaded.action == action
    assert reloaded.action_hash == canonical_action_hash(action, SIGNING_KEY)
    assert reloaded.reason == "dependency install requires approval"
    assert reloaded.run_id == "run-123"
    assert reloaded.step_id == 4
    assert reloaded.rule_id == "command.dependency_install"
    assert datetime.fromisoformat(reloaded.created_at)
    assert datetime.fromisoformat(reloaded.updated_at)


def test_approval_is_bound_to_original_action(tmp_path):
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    original = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    changed = Action(type="run_command", arguments={"command": "python -m pip install malware"})
    record = store.create(original, "approval required")
    store.approve(record.id)

    with pytest.raises(ApprovalError, match="does not match"):
        store.consume(record.id, changed)


def test_approved_action_can_be_consumed_only_once(tmp_path):
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "approval required")
    store.approve(record.id)

    assert store.consume(record.id, action).status == "consumed"
    with pytest.raises(ApprovalError, match="already consumed"):
        store.consume(record.id, action)


def test_rejected_action_cannot_be_consumed(tmp_path):
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "approval required")

    store.reject(record.id)

    with pytest.raises(ApprovalError, match="rejected"):
        store.consume(record.id, action)


def test_tampered_persisted_action_is_detected(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "approval required")
    store.approve(record.id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[record.id]["action"]["arguments"]["command"] = "python -m pip install malware"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ApprovalError, match="integrity check failed"):
        ApprovalStore(path, SIGNING_KEY).consume(record.id)


def test_attacker_cannot_recompute_signature_without_key(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})
    record = store.create(action, "approval required")
    store.approve(record.id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[record.id]["action"]["arguments"]["command"] = "python -m pip install malware"
    payload[record.id]["action_hash"] = canonical_action_hash(
        Action(type="run_command", arguments={"command": "python -m pip install malware"}),
        b"attacker-controlled-key",
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ApprovalError, match="integrity check failed"):
        ApprovalStore(path, SIGNING_KEY).consume(record.id)


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("status", "approved"),
        ("reason", "attacker-approved without a human decision"),
        ("run_id", "attacker-run"),
        ("step_id", 99),
        ("rule_id", "attacker.rule"),
        ("created_at", "2000-01-01T00:00:00+00:00"),
        ("updated_at", "2000-01-01T00:00:00+00:00"),
    ],
)
def test_tampered_persisted_record_metadata_is_detected(
    tmp_path, field, tampered_value
):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "echo governed"})
    record = store.create(action, "approval required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[record.id][field] = tampered_value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ApprovalError, match="integrity check failed"):
        ApprovalStore(path, SIGNING_KEY).get(record.id)


def test_copying_record_under_a_different_id_is_detected(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "echo governed"})
    record = store.create(action, "approval required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    copied_id = "attacker-controlled-approval-id"
    payload[copied_id] = payload.pop(record.id)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ApprovalError, match="integrity check failed"):
        ApprovalStore(path, SIGNING_KEY).get(copied_id)


def test_each_state_transition_resigns_the_complete_record(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "echo governed"})

    record = store.create(action, "approval required")
    pending_signature = json.loads(path.read_text(encoding="utf-8"))[record.id][
        "record_signature"
    ]
    store.approve(record.id)
    approved_signature = json.loads(path.read_text(encoding="utf-8"))[record.id][
        "record_signature"
    ]
    store.consume(record.id, action)
    consumed_signature = json.loads(path.read_text(encoding="utf-8"))[record.id][
        "record_signature"
    ]

    assert len(pending_signature) == 64
    assert len({pending_signature, approved_signature, consumed_signature}) == 3


def test_malformed_record_signature_type_fails_with_controlled_error(tmp_path):
    path = tmp_path / "approvals.json"
    store = ApprovalStore(path, SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "echo governed"})
    record = store.create(action, "approval required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[record.id]["record_signature"] = {"attacker": "controlled"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ApprovalError, match="approval record is invalid"):
        ApprovalStore(path, SIGNING_KEY).get(record.id)
