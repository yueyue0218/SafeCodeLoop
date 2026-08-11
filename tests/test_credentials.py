from safecodeloop.cli import main
from safecodeloop.credentials import CredentialStore


def test_status_does_not_show_plaintext_key(tmp_path, capsys):
    store = CredentialStore(tmp_path / "credentials.json")
    store.set_key("openai", "sk-test-secret")

    status = store.status("openai")

    assert status["configured"] is True
    assert status["masked_key"] == "sk-t...cret"
    assert "sk-test-secret" not in str(status)


def test_clear_removes_stored_key(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")
    store.set_key("openai", "sk-test-secret")

    store.clear_key("openai")

    assert store.get_key("openai") is None
    assert store.status("openai")["configured"] is False


def test_missing_key_status_gives_configuration_hint(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")

    status = store.status("openai")

    assert status["configured"] is False
    assert "key set openai" in status["hint"]


def test_cli_key_status_omits_plaintext(tmp_path, monkeypatch, capsys):
    credentials_path = tmp_path / "credentials.json"
    monkeypatch.setenv("SAFECODELOOP_CREDENTIALS_PATH", str(credentials_path))
    store = CredentialStore(credentials_path)
    store.set_key("openai", "sk-test-secret")

    exit_code = main(["key", "status", "openai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "configured" in captured.out
    assert "sk-t...cret" in captured.out
    assert "sk-test-secret" not in captured.out


def test_cli_key_set_and_clear(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SAFECODELOOP_CREDENTIALS_PATH", str(tmp_path / "credentials.json"))

    assert main(["key", "set", "openai", "--value", "sk-test-secret"]) == 0
    set_output = capsys.readouterr().out
    assert "stored" in set_output
    assert "sk-test-secret" not in set_output

    assert main(["key", "clear", "openai"]) == 0
    clear_output = capsys.readouterr().out
    assert "cleared" in clear_output
