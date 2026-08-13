import pytest

from safecodeloop.approval import ApprovalStore


@pytest.fixture(autouse=True)
def isolated_cli_approval_store(tmp_path, monkeypatch):
    """Keep CLI tests independent from the host OS keyring."""
    store = ApprovalStore(
        tmp_path / "isolated-approvals.json",
        b"test-only-approval-signing-key",
    )
    monkeypatch.setattr("safecodeloop.cli._approval_store", lambda workspace: store)
    return store
