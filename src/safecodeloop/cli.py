import argparse
import json
from getpass import getpass
from pathlib import Path

from safecodeloop import __version__
from safecodeloop.config import ConfigError, load_config
from safecodeloop.credentials import CredentialError, CredentialStore
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import LLMError, MockLLM, OpenAICompatibleLLM
from safecodeloop.loop import AgentLoop, RunResult
from safecodeloop.memory import MemoryStore
from safecodeloop.tools import create_agent_tool_registry


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

    key_parser = subparsers.add_parser("key", help="Manage LLM API credentials.")
    key_subparsers = key_parser.add_subparsers(dest="key_command")

    key_status = key_subparsers.add_parser("status", help="Show credential status.")
    key_status.add_argument("provider", nargs="?", default="openai")

    key_set = key_subparsers.add_parser("set", help="Store an API key.")
    key_set.add_argument("provider")

    key_clear = key_subparsers.add_parser("clear", help="Clear a stored API key.")
    key_clear.add_argument("provider", nargs="?", default="openai")

    subparsers.add_parser("demo", help="Run deterministic mock-LLM demos.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "key":
        return _handle_key_command(args, parser)
    if args.command == "run":
        return _handle_run_command(args)

    return 0


def _handle_run_command(args) -> int:
    try:
        config = load_config(args.config)
        workspace = Path(args.workspace or config.workspace_root)
        workspace.mkdir(parents=True, exist_ok=True)

        llm = _create_llm(config, args.mock_script)
        loop = AgentLoop(
            llm=llm,
            max_steps=config.max_steps,
            tool_registry=create_agent_tool_registry(workspace),
            guardrail_engine=GuardrailEngine(
                workspace,
                blocked_command_patterns=config.blocked_command_patterns,
            ),
            validator=Validator(),
            memory_store=MemoryStore(workspace / config.memory_path),
        )
        result = loop.run(" ".join(args.task))
    except (ConfigError, CredentialError, LLMError, OSError, ValueError) as exc:
        print(f"run error: {exc}")
        return 2

    print(f"status: {result.status}")
    if result.final_message:
        print(result.final_message)

    if args.log:
        _write_run_log(Path(args.log), result)

    return 0 if result.status == "success" else 1


def _create_llm(config, mock_script):
    if config.model_provider == "mock":
        if not mock_script:
            raise ConfigError("--mock-script is required when modelProvider is mock")
        return MockLLM(_load_mock_script(Path(mock_script)))

    if config.model_provider == "openai-compatible":
        api_key = CredentialStore().get_key(config.credential_provider)
        if not api_key:
            raise CredentialError(
                f"credential is not configured for provider: {config.credential_provider}"
            )
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


def _write_run_log(path: Path, result: RunResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_run_result_to_dict(result), indent=2), encoding="utf-8")


def _run_result_to_dict(result: RunResult) -> dict:
    return {
        "status": result.status,
        "final_message": result.final_message,
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
        print(f"credential error: {exc}")
        return 2

    parser.error(f"unknown key subcommand: {args.key_command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
