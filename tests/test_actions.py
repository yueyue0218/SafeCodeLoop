import pytest

from safecodeloop.actions import ActionParseError, parse_action


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
