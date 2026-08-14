from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from safecodeloop.actions import Action


class ApprovalError(ValueError):
    pass


_ALLOWED_STATUSES = frozenset({"pending", "approved", "rejected", "consumed"})


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    action: Action
    action_hash: str
    reason: str
    status: str
    run_id: str
    step_id: int
    rule_id: str
    created_at: str
    updated_at: str
    record_signature: str


def canonical_action_hash(action: Action, signing_key: bytes) -> str:
    payload = {"type": action.type, "arguments": action.arguments}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _record_signature(
    approval_id: str,
    action: Action,
    action_hash: str,
    reason: str,
    status: str,
    run_id: str,
    step_id: int,
    rule_id: str,
    created_at: str,
    updated_at: str,
    signing_key: bytes,
) -> str:
    payload = {
        "id": approval_id,
        "action": {"type": action.type, "arguments": action.arguments},
        "action_hash": action_hash,
        "reason": reason,
        "status": status,
        "run_id": run_id,
        "step_id": step_id,
        "rule_id": rule_id,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    message = b"safecodeloop:approval-record:v1\0" + canonical.encode("utf-8")
    return hmac.new(signing_key, message, hashlib.sha256).hexdigest()


class ApprovalStore:
    def __init__(self, path: str | Path, signing_key: bytes):
        if not signing_key:
            raise ApprovalError("approval signing key must not be empty")
        self.path = Path(path)
        self.signing_key = signing_key

    def create(
        self,
        action: Action,
        reason: str,
        *,
        run_id: str | None = None,
        step_id: int = 0,
        rule_id: str = "unspecified",
    ) -> ApprovalRecord:
        if not isinstance(reason, str) or not reason:
            raise ApprovalError("approval reason must not be empty")
        if not isinstance(run_id, (str, type(None))) or run_id == "":
            raise ApprovalError("approval run id must not be empty")
        if not isinstance(step_id, int) or isinstance(step_id, bool) or step_id < 0:
            raise ApprovalError("approval step id must be a non-negative integer")
        if not isinstance(rule_id, str) or not rule_id:
            raise ApprovalError("approval rule id must not be empty")
        approval_id = uuid4().hex
        resolved_run_id = run_id or uuid4().hex
        action_hash = canonical_action_hash(action, self.signing_key)
        status = "pending"
        now = datetime.now(timezone.utc).isoformat()
        record = ApprovalRecord(
            id=approval_id,
            action=action,
            action_hash=action_hash,
            reason=reason,
            status=status,
            run_id=resolved_run_id,
            step_id=step_id,
            rule_id=rule_id,
            created_at=now,
            updated_at=now,
            record_signature=_record_signature(
                approval_id,
                action,
                action_hash,
                reason,
                status,
                resolved_run_id,
                step_id,
                rule_id,
                now,
                now,
                self.signing_key,
            ),
        )
        data = self._load()
        data[record.id] = self._to_dict(record)
        self._save(data)
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        raw = self._load().get(approval_id)
        if raw is None:
            raise ApprovalError(f"approval not found: {approval_id}")
        record = self._from_dict(approval_id, raw)
        self._verify_record(record)
        return record

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
        self._verify_record(record)
        if record.status != expected:
            raise ApprovalError(
                f"cannot change approval from {record.status} to {target}"
            )
        updated_at = datetime.now(timezone.utc).isoformat()
        record_signature = _record_signature(
            record.id,
            record.action,
            record.action_hash,
            record.reason,
            target,
            record.run_id,
            record.step_id,
            record.rule_id,
            record.created_at,
            updated_at,
            self.signing_key,
        )
        updated = ApprovalRecord(
            id=record.id,
            action=record.action,
            action_hash=record.action_hash,
            reason=record.reason,
            status=target,
            run_id=record.run_id,
            step_id=record.step_id,
            rule_id=record.rule_id,
            created_at=record.created_at,
            updated_at=updated_at,
            record_signature=record_signature,
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
            "run_id": record.run_id,
            "step_id": record.step_id,
            "rule_id": record.rule_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "record_signature": record.record_signature,
        }

    @staticmethod
    def _from_dict(approval_id: str, raw: Any) -> ApprovalRecord:
        try:
            action_raw = raw["action"]
            action_type = action_raw["type"]
            arguments = action_raw["arguments"]
            action_hash = raw["action_hash"]
            reason = raw["reason"]
            status = raw["status"]
            run_id = raw["run_id"]
            step_id = raw["step_id"]
            rule_id = raw["rule_id"]
            created_at = raw["created_at"]
            updated_at = raw["updated_at"]
            record_signature = raw["record_signature"]
            if (
                not isinstance(approval_id, str)
                or not approval_id
                or not isinstance(action_type, str)
                or not action_type
                or not isinstance(arguments, dict)
                or not isinstance(action_hash, str)
                or not isinstance(reason, str)
                or not isinstance(status, str)
                or not isinstance(run_id, str)
                or not run_id
                or not isinstance(step_id, int)
                or isinstance(step_id, bool)
                or step_id < 0
                or not isinstance(rule_id, str)
                or not rule_id
                or not isinstance(created_at, str)
                or not created_at
                or not isinstance(updated_at, str)
                or not updated_at
                or not isinstance(record_signature, str)
            ):
                raise ApprovalError("approval record is invalid")
            action = Action(type=action_type, arguments=arguments)
            return ApprovalRecord(
                id=approval_id,
                action=action,
                action_hash=action_hash,
                reason=reason,
                status=status,
                run_id=run_id,
                step_id=step_id,
                rule_id=rule_id,
                created_at=created_at,
                updated_at=updated_at,
                record_signature=record_signature,
            )
        except (KeyError, TypeError) as exc:
            raise ApprovalError("approval record is invalid") from exc

    def _verify_record(self, record: ApprovalRecord) -> None:
        expected_signature = _record_signature(
            record.id,
            record.action,
            record.action_hash,
            record.reason,
            record.status,
            record.run_id,
            record.step_id,
            record.rule_id,
            record.created_at,
            record.updated_at,
            self.signing_key,
        )
        if not hmac.compare_digest(expected_signature, record.record_signature):
            raise ApprovalError("approval integrity check failed")
        if not hmac.compare_digest(
            canonical_action_hash(record.action, self.signing_key), record.action_hash
        ):
            raise ApprovalError("approval integrity check failed")
        if record.status not in _ALLOWED_STATUSES:
            raise ApprovalError("approval record has invalid status")
