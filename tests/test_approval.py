import json

import pytest

from safecodeloop.actions import Action
from safecodeloop.approval import ApprovalError, ApprovalStore, canonical_action_hash


SIGNING_KEY = b"test-only-approval-signing-key"


def test_pending_approval_persists_canonical_action_and_hash(tmp_path):
    store = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY)
    action = Action(type="run_command", arguments={"command": "python -m pip install requests"})

    record = store.create(action, "dependency install requires approval")
    reloaded = ApprovalStore(tmp_path / "approvals.json", SIGNING_KEY).get(record.id)

    assert reloaded.status == "pending"
    assert reloaded.action == action
    assert reloaded.action_hash == canonical_action_hash(action, SIGNING_KEY)
    assert reloaded.reason == "dependency install requires approval"


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
