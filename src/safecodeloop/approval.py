from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from safecodeloop.actions import Action


class ApprovalError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    action: Action
    action_hash: str
    reason: str
    status: str


def canonical_action_hash(action: Action, signing_key: bytes) -> str:
    payload = {"type": action.type, "arguments": action.arguments}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


class ApprovalStore:
    def __init__(self, path: str | Path, signing_key: bytes):
        if not signing_key:
            raise ApprovalError("approval signing key must not be empty")
        self.path = Path(path)
        self.signing_key = signing_key

    def create(self, action: Action, reason: str) -> ApprovalRecord:
        record = ApprovalRecord(
            id=uuid4().hex,
            action=action,
            action_hash=canonical_action_hash(action, self.signing_key),
            reason=reason,
            status="pending",
        )
        data = self._load()
        data[record.id] = self._to_dict(record)
        self._save(data)
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        raw = self._load().get(approval_id)
        if raw is None:
            raise ApprovalError(f"approval not found: {approval_id}")
        return self._from_dict(approval_id, raw)

    def approve(self, approval_id: str) -> ApprovalRecord:
        return self._transition(approval_id, expected="pending", target="approved")

    def reject(self, approval_id: str) -> ApprovalRecord:
        return self._transition(approval_id, expected="pending", target="rejected")

    def consume(self, approval_id: str, action: Action | None = None) -> ApprovalRecord:
        record = self.get(approval_id)
        if record.status == "consumed":
            raise ApprovalError("approval already consumed")
        if record.status == "rejected":
            raise ApprovalError("approval was rejected")
        if record.status != "approved":
            raise ApprovalError("approval is not approved")

        if not hmac.compare_digest(
            canonical_action_hash(record.action, self.signing_key), record.action_hash
        ):
            raise ApprovalError("approval integrity check failed")
        requested_action = action or record.action
        if not hmac.compare_digest(
            canonical_action_hash(requested_action, self.signing_key), record.action_hash
        ):
            raise ApprovalError("approved action does not match requested action")
        return self._transition(approval_id, expected="approved", target="consumed")

    def _transition(self, approval_id: str, expected: str, target: str) -> ApprovalRecord:
        data = self._load()
        raw = data.get(approval_id)
        if raw is None:
            raise ApprovalError(f"approval not found: {approval_id}")
        record = self._from_dict(approval_id, raw)
        if not hmac.compare_digest(
            canonical_action_hash(record.action, self.signing_key), record.action_hash
        ):
            raise ApprovalError("approval integrity check failed")
        if record.status != expected:
            raise ApprovalError(
                f"cannot change approval from {record.status} to {target}"
            )
        updated = ApprovalRecord(
            id=record.id,
            action=record.action,
            action_hash=record.action_hash,
            reason=record.reason,
            status=target,
        )
        data[approval_id] = self._to_dict(updated)
        self._save(data)
        return updated

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApprovalError("approval store is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ApprovalError("approval store must contain an object")
        return payload

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _to_dict(record: ApprovalRecord) -> dict[str, Any]:
        return {
            "action": {"type": record.action.type, "arguments": record.action.arguments},
            "action_hash": record.action_hash,
            "reason": record.reason,
            "status": record.status,
        }

    @staticmethod
    def _from_dict(approval_id: str, raw: Any) -> ApprovalRecord:
        try:
            action_raw = raw["action"]
            action = Action(type=action_raw["type"], arguments=action_raw["arguments"])
            return ApprovalRecord(
                id=approval_id,
                action=action,
                action_hash=raw["action_hash"],
                reason=raw["reason"],
                status=raw["status"],
            )
        except (KeyError, TypeError) as exc:
            raise ApprovalError("approval record is invalid") from exc
