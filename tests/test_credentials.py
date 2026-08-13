from safecodeloop.cli import main
from safecodeloop.credentials import CredentialStore, KeyringBackend


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_keyring_backend_stores_updates_and_clears_without_plaintext_file(tmp_path):
    keyring = FakeKeyring()
    store = CredentialStore(backend=KeyringBackend(keyring_module=keyring))

    store.set_key("OpenAI", "sk-first-secret")
    assert store.get_key("openai") == "sk-first-secret"

    store.set_key("openai", "sk-updated-secret")
    assert store.get_key("openai") == "sk-updated-secret"
    assert list(tmp_path.iterdir()) == []

    store.clear_key("openai")
    assert store.get_key("openai") is None


def test_default_store_uses_keyring_backend(monkeypatch):
    store = CredentialStore()

    assert isinstance(store.backend, KeyringBackend)


def test_status_does_not_show_plaintext_key(tmp_path, capsys):
    store = CredentialStore(tmp_path / "credentials.json")
    store.set_key("openai", "sk-test-secret")

    status = store.status("openai")

    assert status["configured"] is True
    assert "masked_key" not in status
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
    assert "--value" not in status["hint"]


def test_cli_key_status_omits_plaintext(tmp_path, monkeypatch, capsys):
    store = CredentialStore(tmp_path / "credentials.json")
    store.set_key("openai", "sk-test-secret")
    monkeypatch.setattr("safecodeloop.cli.CredentialStore", lambda: store)

    exit_code = main(["key", "status", "openai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "configured" in captured.out
    assert "sk-test-secret" not in captured.out


def test_cli_key_set_and_clear(tmp_path, monkeypatch, capsys):
    store = CredentialStore(tmp_path / "credentials.json")
    monkeypatch.setattr("safecodeloop.cli.CredentialStore", lambda: store)
    monkeypatch.setattr("safecodeloop.cli.getpass", lambda prompt: "sk-test-secret")

    assert main(["key", "set", "openai"]) == 0
    set_output = capsys.readouterr().out
    assert "stored" in set_output
    assert "sk-test-secret" not in set_output

    assert main(["key", "clear", "openai"]) == 0
    clear_output = capsys.readouterr().out
    assert "cleared" in clear_output


def test_cli_key_set_prompts_without_echoing_secret(tmp_path, monkeypatch, capsys):
    store = CredentialStore(tmp_path / "credentials.json")
    monkeypatch.setattr("safecodeloop.cli.CredentialStore", lambda: store)
    monkeypatch.setattr("safecodeloop.cli.getpass", lambda prompt: "sk-hidden-secret")

    assert main(["key", "set", "openai"]) == 0

    captured = capsys.readouterr()
    assert "stored" in captured.out
    assert "sk-hidden-secret" not in captured.out
    assert store.get_key("openai") == "sk-hidden-secret"


def test_cli_rejects_command_line_key_value(capsys):
    try:
        main(["key", "set", "openai", "--value", "must-not-enter-history"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("CLI unexpectedly accepted a command-line secret")

    assert "must-not-enter-history" not in capsys.readouterr().out
