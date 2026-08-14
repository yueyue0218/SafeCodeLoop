import pytest

from safecodeloop.redaction import SecretRedactor, redact_value


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("OPENAI_API_KEY=sk-test-secret-value", "sk-test-secret-value"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1Ni.test.signature", "eyJhbGciOiJIUzI1Ni.test.signature"),
        ('{"api_key": "plain-api-secret-value"}', "plain-api-secret-value"),
        ("password=hunter2-secret", "hunter2-secret"),
        ("access_token: opaque-access-token", "opaque-access-token"),
    ],
)
def test_common_secret_forms_are_redacted(text, secret):
    redacted = SecretRedactor().redact_text(text)

    assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_known_runtime_secret_is_redacted_recursively_without_mutating_input():
    payload = {
        "final_message": "runtime-opaque-secret",
        "steps": [
            {
                "action": {"arguments": {"content": "runtime-opaque-secret"}},
                "observation": {"details": ["prefix runtime-opaque-secret suffix"]},
            }
        ],
        "ok": True,
        "count": 2,
    }
    redactor = SecretRedactor(["runtime-opaque-secret"])

    sanitized = redact_value(payload, redactor=redactor)

    assert "runtime-opaque-secret" in str(payload)
    assert "runtime-opaque-secret" not in str(sanitized)
    assert sanitized["ok"] is True
    assert sanitized["count"] == 2


def test_quoted_secret_field_with_spaces_is_fully_redacted():
    redacted = SecretRedactor().redact_text('{"password": "two words secret"}')

    assert redacted == '{"password": "[REDACTED]"}'


def test_secret_in_mapping_key_is_redacted_for_structured_logs():
    secret = "runtime-secret-mapping-key"
    sanitized = SecretRedactor([secret]).redact({secret: "value"})

    assert secret not in str(sanitized)
    assert sanitized == {"[REDACTED]": "value"}


def test_short_known_values_are_not_registered_to_avoid_broad_false_positives():
    redactor = SecretRedactor(["test", "1234567"])

    assert redactor.redact_text("test 1234567") == "test 1234567"


def test_redaction_is_idempotent():
    redactor = SecretRedactor(["runtime-opaque-secret"])
    once = redactor.redact_text("Bearer runtime-opaque-secret")

    assert redactor.redact_text(once) == once
