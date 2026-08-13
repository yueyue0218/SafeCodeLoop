from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SafeCodeLoopConfig:
    workspace_root: str = "."
    max_steps: int = 5
    allowed_tools: tuple[str, ...] = (
        "list_files",
        "read_file",
        "write_file",
        "run_command",
        "run_validation",
    )
    blocked_command_patterns: tuple[str, ...] = ()
    approval_required_patterns: tuple[str, ...] = ()
    test_command: str = "python -m pytest"
    model_provider: str = "mock"
    model: str = "glm-5.2"
    base_url: str = "https://njusehub.info/v1"
    request_timeout: float = 60
    credential_provider: str = "njusehub"
    memory_path: str = ".safecodeloop/memory.json"


CONFIG_FIELD_MAP = {
    "workspaceRoot": "workspace_root",
    "maxSteps": "max_steps",
    "allowedTools": "allowed_tools",
    "blockedCommandPatterns": "blocked_command_patterns",
    "approvalRequiredPatterns": "approval_required_patterns",
    "testCommand": "test_command",
    "modelProvider": "model_provider",
    "model": "model",
    "baseUrl": "base_url",
    "requestTimeout": "request_timeout",
    "credentialProvider": "credential_provider",
    "memoryPath": "memory_path",
}


def load_config(path: str | Path | None) -> SafeCodeLoopConfig:
    if path is None:
        return SafeCodeLoopConfig()

    config_path = Path(path)
    if not config_path.exists():
        return SafeCodeLoopConfig()

    raw = config_path.read_text(encoding="utf-8").strip()
    if not raw:
        return SafeCodeLoopConfig()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid config JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ConfigError("config file must contain a JSON object")

    normalized: dict[str, Any] = {}
    for raw_key, value in payload.items():
        if raw_key not in CONFIG_FIELD_MAP:
            raise ConfigError(f"unknown config field: {raw_key}")
        normalized[CONFIG_FIELD_MAP[raw_key]] = value

    return _validate_config(SafeCodeLoopConfig(**normalized))


def _validate_config(config: SafeCodeLoopConfig) -> SafeCodeLoopConfig:
    if not isinstance(config.max_steps, int):
        raise ConfigError("maxSteps must be an integer")
    if config.max_steps < 1:
        raise ConfigError("maxSteps must be at least 1")
    if not isinstance(config.request_timeout, (int, float)) or config.request_timeout <= 0:
        raise ConfigError("requestTimeout must be a positive number")

    tuple_fields = {
        "allowed_tools",
        "blocked_command_patterns",
        "approval_required_patterns",
    }
    replacements: dict[str, Any] = {}
    field_names = {field.name for field in fields(config)}
    for name in tuple_fields & field_names:
        value = getattr(config, name)
        if not isinstance(value, (list, tuple)):
            raise ConfigError(f"{_to_external_name(name)} must be a list")
        if not all(isinstance(item, str) and item for item in value):
            raise ConfigError(f"{_to_external_name(name)} must contain non-empty strings")
        replacements[name] = tuple(value)

    for name in (
        "workspace_root",
        "test_command",
        "model_provider",
        "model",
        "base_url",
        "credential_provider",
        "memory_path",
    ):
        value = getattr(config, name)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{_to_external_name(name)} must be a non-empty string")

    if replacements:
        return SafeCodeLoopConfig(**{**config.__dict__, **replacements})
    return config


def _to_external_name(internal_name: str) -> str:
    for external, internal in CONFIG_FIELD_MAP.items():
        if internal == internal_name:
            return external
    return internal_name
