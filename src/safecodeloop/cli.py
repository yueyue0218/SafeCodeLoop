import argparse

from safecodeloop import __version__


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
    subparsers.add_parser("key", help="Manage LLM API credentials.")
    subparsers.add_parser("demo", help="Run deterministic mock-LLM demos.")
    return parser


def main(argv=None):
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
