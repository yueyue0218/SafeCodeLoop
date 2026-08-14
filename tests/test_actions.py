import pytest

from safecodeloop.actions import MAX_ACTION_RESPONSE_CHARS, ActionParseError, parse_action


def test_parse_valid_read_file_action():
    action = parse_action('{"type": "read_file", "path": "README.md"}')

    assert action.type == "read_file"
    assert action.arguments == {"path": "README.md"}


def test_parse_valid_run_command_action():
    action = parse_action('{"type": "run_command", "command": "python -m pytest"}')

    assert action.type == "run_command"
    assert action.arguments == {"command": "python -m pytest"}


def test_parse_valid_run_validation_action():
    action = parse_action('{"type": "run_validation", "command": "python -m pytest"}')

    assert action.type == "run_validation"
    assert action.arguments == {"command": "python -m pytest"}


def test_unknown_action_type_is_rejected():
    with pytest.raises(ActionParseError, match="unknown action type"):
        parse_action('{"type": "delete_everything"}')


def test_missing_required_path_is_rejected():
    with pytest.raises(ActionParseError, match="missing required field"):
        parse_action('{"type": "read_file"}')


def test_missing_required_command_is_rejected():
    with pytest.raises(ActionParseError, match="missing required field"):
        parse_action('{"type": "run_command"}')


def test_invalid_json_is_rejected():
    with pytest.raises(ActionParseError, match="invalid JSON"):
        parse_action("not json")


def test_finish_action_allows_message():
    action = parse_action('{"type": "finish", "message": "done"}')

    assert action.type == "finish"
    assert action.arguments == {"message": "done"}


def test_single_json_markdown_fence_is_accepted():
    action = parse_action('```json\n{"type": "read_file", "path": "README.md"}\n```')

    assert action.type == "read_file"
    assert action.arguments == {"path": "README.md"}


def test_single_json_object_with_surrounding_text_is_accepted():
    action = parse_action(
        'I will inspect the file.\n{"type": "read_file", "path": "README.md"}\nProceeding now.'
    )

    assert action.type == "read_file"


def test_multiple_json_objects_are_rejected_as_ambiguous():
    with pytest.raises(ActionParseError, match="exactly one JSON action object"):
        parse_action('{"type": "list_files"}\n{"type": "finish"}')


def test_extra_action_fields_are_rejected():
    with pytest.raises(ActionParseError, match="unexpected field: recursive"):
        parse_action('{"type": "list_files", "recursive": true}')


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        ('{"type": "read_file", "path": 3}', "path"),
        ('{"type": "write_file", "path": "x.py", "content": false}', "content"),
        ('{"type": "run_command", "command": ["pytest"]}', "command"),
        ('{"type": "finish", "message": 7}', "message"),
        ('{"type": "list_files", "path": null}', "path"),
    ],
)
def test_action_field_types_are_strict(raw, field):
    with pytest.raises(ActionParseError, match=f"field {field} must be a string"):
        parse_action(raw)


def test_required_string_fields_cannot_be_empty():
    with pytest.raises(ActionParseError, match="field command must not be empty"):
        parse_action('{"type": "run_command", "command": "   "}')


def test_remember_requires_content_but_kind_is_optional():
    with pytest.raises(ActionParseError, match="missing required field: content"):
        parse_action('{"type": "remember", "kind": "fact"}')

    action = parse_action('{"type": "remember", "content": "Python 3.11"}')
    assert action.arguments == {"content": "Python 3.11"}


def test_duplicate_json_fields_are_rejected():
    with pytest.raises(ActionParseError, match="duplicate field: path"):
        parse_action('{"type": "read_file", "path": "safe", "path": "changed"}')


def test_duplicate_object_cannot_be_hidden_before_a_valid_action():
    raw = (
        '{"type": "read_file", "path": "safe", "path": "changed"}\n'
        '{"type": "finish", "message": "ignore the first object"}'
    )

    with pytest.raises(ActionParseError, match="duplicate field: path"):
        parse_action(raw)


def test_oversized_response_is_rejected_before_json_parsing():
    oversized = "x" * (MAX_ACTION_RESPONSE_CHARS + 1)

    with pytest.raises(ActionParseError, match="exceeds maximum size"):
        parse_action(oversized)
