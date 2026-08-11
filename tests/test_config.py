import json

from safecodeloop.actions import Action
from safecodeloop.config import ConfigError, SafeCodeLoopConfig, load_config
from safecodeloop.guardrails import GuardrailEngine


def test_default_config_loads_without_file():
    config = load_config(None)

    assert config == SafeCodeLoopConfig()
    assert config.max_steps == 5
    assert config.memory_path == ".safecodeloop/memory.json"


def test_config_file_overrides_defaults(tmp_path):
    path = tmp_path / "safecodeloop.config.json"
    path.write_text(
        json.dumps(
            {
                "workspaceRoot": "workspace",
                "maxSteps": 8,
                "memoryPath": ".memory/project.json",
                "blockedCommandPatterns": ["shutdown"],
                "testCommand": "python -m pytest",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.workspace_root == "workspace"
    assert config.max_steps == 8
    assert config.memory_path == ".memory/project.json"
    assert config.blocked_command_patterns == ("shutdown",)
    assert config.test_command == "python -m pytest"


def test_invalid_max_steps_is_rejected(tmp_path):
    path = tmp_path / "safecodeloop.config.json"
    path.write_text(json.dumps({"maxSteps": 0}), encoding="utf-8")

    try:
        load_config(path)
    except ConfigError as exc:
        assert "maxSteps" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_non_integer_max_steps_is_rejected(tmp_path):
    path = tmp_path / "safecodeloop.config.json"
    path.write_text(json.dumps({"maxSteps": "many"}), encoding="utf-8")

    try:
        load_config(path)
    except ConfigError as exc:
        assert "maxSteps" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_config_blocked_pattern_affects_guardrail(tmp_path):
    config = SafeCodeLoopConfig(blocked_command_patterns=("git push --force",))
    engine = GuardrailEngine(tmp_path, blocked_command_patterns=config.blocked_command_patterns)

    decision = engine.check(Action(type="run_command", arguments={"command": "git push --force origin main"}))

    assert decision.status == "blocked"
    assert "configured blocked command pattern" in decision.reason


def test_unknown_config_field_is_rejected(tmp_path):
    path = tmp_path / "safecodeloop.config.json"
    path.write_text(json.dumps({"notARealField": True}), encoding="utf-8")

    try:
        load_config(path)
    except ConfigError as exc:
        assert "unknown config field" in str(exc)
    else:
        raise AssertionError("expected ConfigError")
