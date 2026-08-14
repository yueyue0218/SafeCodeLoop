import argparse
import json
import secrets
from collections.abc import Callable
from getpass import getpass
from pathlib import Path

from safecodeloop import __version__
from safecodeloop.approval import ApprovalError, ApprovalStore
from safecodeloop.config import ConfigError, load_config
from safecodeloop.credentials import CredentialError, CredentialStore
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import LLMError, MockLLM, OpenAICompatibleLLM
from safecodeloop.loop import AgentLoop, RunResult
from safecodeloop.memory import MemoryStore
from safecodeloop.redaction import SecretRedactor, redact_secrets, redact_value
from safecodeloop.tools import create_agent_tool_registry


class _LazyApprovalStore:
    def __init__(self, factory: Callable[[], ApprovalStore]):
        self._factory = factory
        self._store: ApprovalStore | None = None

    def _get_store(self) -> ApprovalStore:
        if self._store is None:
            self._store = self._factory()
        return self._store

    def __getattr__(self, name):
        return getattr(self._get_store(), name)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="safecodeloop",
        description="SafeCodeLoop: a minimal coding agent harness.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"safecodeloop {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run a task through the harness.")
    run_parser.add_argument("task", nargs="+")
    run_parser.add_argument("--mock-script")
    run_parser.add_argument("--workspace")
    run_parser.add_argument("--config")
    run_parser.add_argument("--log")
    run_parser.add_argument("--resume", help="Resume an approved action by approval ID.")

    key_parser = subparsers.add_parser("key", help="Manage LLM API credentials.")
    key_subparsers = key_parser.add_subparsers(dest="key_command")

    key_status = key_subparsers.add_parser("status", help="Show credential status.")
    key_status.add_argument("provider", nargs="?", default="openai")

    key_set = key_subparsers.add_parser("set", help="Store an API key.")
    key_set.add_argument("provider")

    key_clear = key_subparsers.add_parser("clear", help="Clear a stored API key.")
    key_clear.add_argument("provider", nargs="?", default="openai")

    approval_parser = subparsers.add_parser("approval", help="Inspect and decide pending actions.")
    approval_subparsers = approval_parser.add_subparsers(dest="approval_command")
    for command in ("status", "approve", "reject"):
        command_parser = approval_subparsers.add_parser(command)
        command_parser.add_argument("approval_id")
        command_parser.add_argument("--workspace", default=".")

    subparsers.add_parser("demo", help="Run deterministic mock-LLM demos.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "key":
        return _handle_key_command(args, parser)
    if args.command == "run":
        return _handle_run_command(args)
    if args.command == "approval":
        return _handle_approval_command(args, parser)

    return 0


def _handle_run_command(args) -> int:
    redactor = SecretRedactor()
    try:
        config = load_config(args.config)
        workspace = Path(args.workspace or config.workspace_root)
        workspace.mkdir(parents=True, exist_ok=True)
        approval_store = _LazyApprovalStore(lambda: _approval_store(workspace))

        llm = _create_llm(config, args.mock_script, redactor)
        loop = AgentLoop(
            llm=llm,
            max_steps=config.max_steps,
            tool_registry=create_agent_tool_registry(workspace),
            guardrail_engine=GuardrailEngine(
                workspace,
                blocked_command_patterns=config.blocked_command_patterns,
                approval_required_patterns=config.approval_required_patterns,
            ),
            validator=Validator(),
            memory_store=MemoryStore(workspace / config.memory_path),
            approval_store=approval_store,
            max_validations=config.max_validations,
            max_repeated_failures=config.max_repeated_failures,
            redactor=redactor,
        )
        task = " ".join(args.task)
        result = loop.resume(args.resume, task) if args.resume else loop.run(task)
    except (ApprovalError, ConfigError, CredentialError, LLMError, OSError, ValueError) as exc:
        print(f"run error: {redactor.redact_text(str(exc))}")
        return 2

    print(f"status: {result.status}")
    if result.final_message:
        print(redactor.redact_text(result.final_message))
    if result.approval_id:
        print(f"approval_id: {result.approval_id}")

    if args.log:
        _write_run_log(Path(args.log), result, redactor=redactor)

    return 0 if result.status == "success" else 1


def _approval_store(workspace: Path) -> ApprovalStore:
    credential_store = CredentialStore()
    signing_provider = "safecodeloop-approval-signing-key"
    signing_key = credential_store.get_key(signing_provider)
    if signing_key is None:
        signing_key = secrets.token_hex(32)
        credential_store.set_key(signing_provider, signing_key)
    return ApprovalStore(
        workspace / ".safecodeloop" / "approvals.json",
        signing_key=signing_key.encode("utf-8"),
    )


def _handle_approval_command(args, parser) -> int:
    if args.approval_command is None:
        parser.error("approval requires a subcommand: status, approve, or reject")
    store = _approval_store(Path(args.workspace))
    try:
        if args.approval_command == "status":
            record = store.get(args.approval_id)
        elif args.approval_command == "approve":
            record = store.approve(args.approval_id)
        else:
            record = store.reject(args.approval_id)
    except ApprovalError as exc:
        print(f"approval error: {redact_secrets(str(exc))}")
        return 2
    print(f"approval {record.id}: {record.status}")
    print(f"reason: {redact_secrets(record.reason)}")
    print(f"action_hash: {record.action_hash}")
    return 0


def _create_llm(config, mock_script, redactor: SecretRedactor | None = None):
    active_redactor = redactor or SecretRedactor()
    if config.model_provider == "mock":
        if not mock_script:
            raise ConfigError("--mock-script is required when modelProvider is mock")
        return MockLLM(
            _load_mock_script(Path(mock_script)),
            redactor=active_redactor,
        )

    if config.model_provider == "openai-compatible":
        api_key = CredentialStore().get_key(config.credential_provider)
        if not api_key:
            raise CredentialError(
                f"credential is not configured for provider: {config.credential_provider}"
            )
        active_redactor.add_secret(api_key)
        return OpenAICompatibleLLM(
            api_key=api_key,
            model=config.model,
            base_url=config.base_url,
            timeout=config.request_timeout,
        )

    raise ConfigError(f"unsupported modelProvider: {config.model_provider}")


def _load_mock_script(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "responses" in payload:
        payload = payload["responses"]
    if not isinstance(payload, list):
        raise ValueError("mock script must be a JSON list or an object with responses")

    responses = []
    for item in payload:
        if isinstance(item, str):
            responses.append(item)
        elif isinstance(item, dict):
            responses.append(json.dumps(item))
        else:
            raise ValueError("mock script responses must be strings or objects")
    return responses


def _write_run_log(
    path: Path,
    result: RunResult,
    redactor: SecretRedactor | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_run_result_to_dict(result, redactor=redactor), indent=2),
        encoding="utf-8",
    )


def _run_result_to_dict(
    result: RunResult,
    redactor: SecretRedactor | None = None,
) -> dict:
    payload = {
        "status": result.status,
        "final_message": result.final_message,
        "approval_id": result.approval_id,
        "steps": [
            {
                "index": step.index,
                "llm_response": step.llm_response,
                "action": None
                if step.action is None
                else {"type": step.action.type, "arguments": step.action.arguments},
                "observation": step.observation,
            }
            for step in result.steps
        ],
    }
    return redact_value(payload, redactor=redactor)


def _handle_key_command(args, parser):
    if args.key_command is None:
        parser.error("key requires a subcommand: status, set, or clear")

    store = CredentialStore()
    try:
        if args.key_command == "status":
            status = store.status(args.provider)
            if status["configured"]:
                print(f"{status['provider']}: configured")
            else:
                print(f"{status['provider']}: not configured")
                print(status["hint"])
            return 0

        if args.key_command == "set":
            value = getpass("API key: ")
            store.set_key(args.provider, value)
            print(f"{args.provider}: stored")
            return 0

        if args.key_command == "clear":
            store.clear_key(args.provider)
            print(f"{args.provider}: cleared")
            return 0
    except CredentialError as exc:
        print(f"credential error: {redact_secrets(str(exc))}")
        return 2

    parser.error(f"unknown key subcommand: {args.key_command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
