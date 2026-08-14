import json
from dataclasses import dataclass
from typing import Any


MAX_ACTION_RESPONSE_CHARS = 64 * 1024


class ActionParseError(ValueError):
    pass


class _DuplicateFieldError(ValueError):
    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


@dataclass(frozen=True)
class Action:
    type: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class _ActionSchema:
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    non_empty: frozenset[str] = frozenset()

    @property
    def fields(self) -> frozenset[str]:
        return self.required | self.optional


ACTION_SCHEMAS = {
    "read_file": _ActionSchema(
        required=frozenset({"path"}),
        non_empty=frozenset({"path"}),
    ),
    "write_file": _ActionSchema(
        required=frozenset({"path", "content"}),
        non_empty=frozenset({"path"}),
    ),
    "run_command": _ActionSchema(
        required=frozenset({"command"}),
        non_empty=frozenset({"command"}),
    ),
    "run_validation": _ActionSchema(
        required=frozenset({"command"}),
        non_empty=frozenset({"command"}),
    ),
    "finish": _ActionSchema(optional=frozenset({"message"})),
    "request_approval": _ActionSchema(optional=frozenset({"reason"})),
    "remember": _ActionSchema(
        required=frozenset({"content"}),
        optional=frozenset({"kind"}),
        non_empty=frozenset({"content", "kind"}),
    ),
    "list_files": _ActionSchema(
        optional=frozenset({"path"}),
        non_empty=frozenset({"path"}),
    ),
}

SUPPORTED_ACTIONS = frozenset(ACTION_SCHEMAS)


def parse_action(raw_response: str) -> Action:
    if not isinstance(raw_response, str):
        raise ActionParseError("action response must be a string")
    if len(raw_response) > MAX_ACTION_RESPONSE_CHARS:
        raise ActionParseError(
            f"action response exceeds maximum size of {MAX_ACTION_RESPONSE_CHARS} characters"
        )

    payload = _extract_single_json_value(raw_response)
    if not isinstance(payload, dict):
        raise ActionParseError("action must be a JSON object")

    action_type = payload.get("type")
    if not isinstance(action_type, str) or not action_type:
        raise ActionParseError("missing required field: type")
    if action_type not in SUPPORTED_ACTIONS:
        raise ActionParseError(f"unknown action type: {action_type}")

    schema = ACTION_SCHEMAS[action_type]
    unexpected = sorted(set(payload) - {"type"} - schema.fields)
    if unexpected:
        label = "field" if len(unexpected) == 1 else "fields"
        raise ActionParseError(f"unexpected {label}: {', '.join(unexpected)}")

    missing = sorted(schema.required - set(payload))
    if missing:
        raise ActionParseError(f"missing required field: {missing[0]}")

    arguments: dict[str, str] = {}
    for field in sorted(schema.fields):
        if field not in payload:
            continue
        value = payload[field]
        if not isinstance(value, str):
            raise ActionParseError(f"field {field} must be a string")
        if field in schema.non_empty and not value.strip():
            raise ActionParseError(f"field {field} must not be empty")
        arguments[field] = value

    return Action(type=action_type, arguments=arguments)


def _extract_single_json_value(raw_response: str) -> Any:
    text = raw_response.strip()
    if not text:
        raise ActionParseError("invalid JSON action")

    decoder = json.JSONDecoder(object_pairs_hook=_object_without_duplicate_fields)
    try:
        value, end = decoder.raw_decode(text)
        if not text[end:].strip():
            return value
    except _DuplicateFieldError as exc:
        raise ActionParseError(f"duplicate field: {exc.field}") from exc
    except json.JSONDecodeError:
        pass

    candidates: list[Any] = []
    duplicate_field: str | None = None
    offset = 0
    while True:
        start = text.find("{", offset)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text, start)
        except _DuplicateFieldError as exc:
            duplicate_field = duplicate_field or exc.field
            offset = start + 1
            continue
        except json.JSONDecodeError:
            offset = start + 1
            continue
        candidates.append(value)
        offset = end

    if len(candidates) > 1:
        raise ActionParseError("response must contain exactly one JSON action object")
    if duplicate_field is not None:
        raise ActionParseError(f"duplicate field: {duplicate_field}")
    if len(candidates) == 1:
        return candidates[0]
    raise ActionParseError("invalid JSON action")


def _object_without_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateFieldError(key)
        result[key] = value
    return result
