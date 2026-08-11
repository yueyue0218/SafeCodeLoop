import json

from safecodeloop.memory import MemoryItem, MemoryStore


def test_memory_item_persists_to_json(tmp_path):
    path = tmp_path / "memory.json"
    store = MemoryStore(path)

    item = store.remember("project uses pytest", kind="project", priority=2)
    reloaded = MemoryStore(path)

    assert item.id
    assert reloaded.all()[0].content == "project uses pytest"
    assert json.loads(path.read_text(encoding="utf-8"))[0]["kind"] == "project"


def test_retrieve_returns_recent_and_high_priority_matches(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")

    store.remember("python package name is safecodeloop", kind="project", priority=1)
    important = store.remember("pytest is the required test command", kind="testing", priority=5)
    recent = store.remember("pytest failures should become feedback", kind="testing", priority=2)
    store.remember("docker is a later release task", kind="release", priority=10)

    results = store.retrieve("pytest feedback", limit=2)

    assert results == [recent, important]


def test_secret_like_memory_content_is_redacted(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")

    item = store.remember("OPENAI_API_KEY=sk-test-secret", kind="credential", priority=1)

    assert "sk-test-secret" not in item.content
    assert "[REDACTED]" in item.content
    assert "sk-test-secret" not in (tmp_path / "memory.json").read_text(encoding="utf-8")


def test_empty_memory_file_loads_as_empty_list(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("", encoding="utf-8")

    store = MemoryStore(path)

    assert store.all() == []


def test_memory_item_round_trips_from_dict():
    item = MemoryItem(
        id="m1",
        content="remember this",
        kind="note",
        priority=3,
        created_at="2026-08-11T00:00:00Z",
    )

    assert MemoryItem.from_dict(item.to_dict()) == item
