import subprocess
import sys


def run_module(*args):
    return subprocess.run(
        [sys.executable, "-m", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cli_help_exits_zero():
    result = run_module("safecodeloop.cli", "--help")

    assert result.returncode == 0
    assert "SafeCodeLoop" in result.stdout


def test_cli_version_exits_zero():
    result = run_module("safecodeloop.cli", "--version")

    assert result.returncode == 0
    assert "safecodeloop 0.1.0" in result.stdout


def test_python_m_safecodeloop_exits_zero():
    result = run_module("safecodeloop", "--help")

    assert result.returncode == 0
    assert "SafeCodeLoop" in result.stdout
