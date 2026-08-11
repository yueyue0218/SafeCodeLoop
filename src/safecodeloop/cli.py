import argparse

from safecodeloop import __version__
from safecodeloop.credentials import CredentialError, CredentialStore


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
    subparsers.add_parser("run", help="Run a task through the harness.")

    key_parser = subparsers.add_parser("key", help="Manage LLM API credentials.")
    key_subparsers = key_parser.add_subparsers(dest="key_command")

    key_status = key_subparsers.add_parser("status", help="Show credential status.")
    key_status.add_argument("provider", nargs="?", default="openai")

    key_set = key_subparsers.add_parser("set", help="Store an API key.")
    key_set.add_argument("provider")
    key_set.add_argument("--value", required=True)

    key_clear = key_subparsers.add_parser("clear", help="Clear a stored API key.")
    key_clear.add_argument("provider", nargs="?", default="openai")

    subparsers.add_parser("demo", help="Run deterministic mock-LLM demos.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "key":
        return _handle_key_command(args, parser)

    return 0


def _handle_key_command(args, parser):
    if args.key_command is None:
        parser.error("key requires a subcommand: status, set, or clear")

    store = CredentialStore()
    try:
        if args.key_command == "status":
            status = store.status(args.provider)
            if status["configured"]:
                print(f"{status['provider']}: configured ({status['masked_key']})")
            else:
                print(f"{status['provider']}: not configured")
                print(status["hint"])
            return 0

        if args.key_command == "set":
            store.set_key(args.provider, args.value)
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
