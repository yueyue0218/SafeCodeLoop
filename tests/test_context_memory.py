from safecodeloop.llm import MockLLM
from safecodeloop.loop import AgentLoop
from safecodeloop.memory import MemoryStore


def test_relevant_memory_appears_in_llm_context(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json")
    memory.remember("pytest is the required test command", kind="testing", priority=3)
    memory.remember("docker release happens later", kind="release", priority=9)
    llm = MockLLM(['{"type": "finish", "message": "done"}'])
    loop = AgentLoop(llm=llm, memory_store=memory)

    result = loop.run("run pytest after editing code")

    assert result.status == "success"
    first_call = llm.calls[0]
    assert first_call[0]["role"] == "system"
    assert "memory_context" in first_call[0]["content"]
    assert "pytest is the required test command" in first_call[0]["content"]
    assert "docker release happens later" not in first_call[0]["content"]


def test_memory_context_budget_omits_lower_ranked_items(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json")
    memory.remember("pytest important", kind="testing", priority=1)
    memory.remember("pytest second detail that should be omitted", kind="testing", priority=1)
    llm = MockLLM(['{"type": "finish", "message": "done"}'])
    loop = AgentLoop(llm=llm, memory_store=memory, memory_context_budget=35)

    loop.run("pytest")

    memory_message = llm.calls[0][0]["content"]
    assert "pytest important" in memory_message
    assert "pytest second detail that should be omitted" not in memory_message


def test_no_memory_message_when_no_relevant_memory(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json")
    memory.remember("docker release happens later", kind="release", priority=9)
    llm = MockLLM(['{"type": "finish", "message": "done"}'])
    loop = AgentLoop(llm=llm, memory_store=memory)

    loop.run("run tests")

    assert llm.calls[0] == [{"role": "user", "content": "run tests"}]
