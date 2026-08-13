import json
from dataclasses import dataclass
from typing import Any


class ActionParseError(ValueError):
    pass


@dataclass(frozen=True)
class Action:
    type: str
    arguments: dict[str, Any]


REQUIRED_FIELDS = {
    "read_file": ("path",),
    "write_file": ("path", "content"),
    "run_command": ("command",),
    "run_validation": ("command",),
}

OPTIONAL_ARGUMENT_FIELDS = {
    "finish": ("message",),
    "request_approval": ("reason",),
    "remember": ("content", "kind"),
    "list_files": ("path",),
}

SUPPORTED_ACTIONS = set(REQUIRED_FIELDS) | set(OPTIONAL_ARGUMENT_FIELDS)


def parse_action(raw_response: str) -> Action:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ActionParseError("invalid JSON action") from exc

    if not isinstance(payload, dict):
        raise ActionParseError("action must be a JSON object")

    action_type = payload.get("type")
    if not isinstance(action_type, str) or not action_type:
        raise ActionParseError("missing required field: type")

    if action_type not in SUPPORTED_ACTIONS:
        raise ActionParseError(f"unknown action type: {action_type}")

    required = REQUIRED_FIELDS.get(action_type, ())
    for field in required:
        if field not in payload:
            raise ActionParseError(f"missing required field: {field}")

    fields = required or OPTIONAL_ARGUMENT_FIELDS.get(action_type, ())
    arguments = {field: payload[field] for field in fields if field in payload}
    return Action(type=action_type, arguments=arguments)
