from dataclasses import dataclass, field
from typing import Any

from safecodeloop.actions import Action, ActionParseError, parse_action
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import LLMClient
from safecodeloop.memory import MemoryStore
from safecodeloop.tools import ToolRegistry


ACTION_PROTOCOL = """You are the decision component of SafeCodeLoop.
Return exactly one JSON action object and no markdown or explanatory text.
Allowed actions:
- {"type":"list_files","path":"optional/relative/path"}
- {"type":"read_file","path":"relative/path"}
- {"type":"write_file","path":"relative/path","content":"file content"}
- {"type":"run_command","command":"command to execute"}
- {"type":"remember","content":"fact","kind":"optional kind"}
- {"type":"request_approval","reason":"reason"}
- {"type":"finish","message":"result summary"}
Use only relative paths inside the workspace. Use finish only when the task is complete."""


@dataclass(frozen=True)
class LoopStep:
    index: int
    llm_response: str
    action: Action | None = None
    observation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    status: str
    final_message: str
    steps: list[LoopStep]


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        max_steps: int = 5,
        tool_registry: ToolRegistry | None = None,
        guardrail_engine: GuardrailEngine | None = None,
        validator: Validator | None = None,
        memory_store: MemoryStore | None = None,
        memory_context_budget: int = 1000,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.llm = llm
        self.max_steps = max_steps
        self.tool_registry = tool_registry
        self.guardrail_engine = guardrail_engine
        self.validator = validator
        self.memory_store = memory_store
        self.memory_context_budget = memory_context_budget

    def run(self, task: str) -> RunResult:
        steps: list[LoopStep] = []
        messages = self._initial_messages(task)

        for index in range(self.max_steps):
            response = self.llm.generate(messages)
            try:
                action = parse_action(response.content)
            except ActionParseError as exc:
                observation = {
                    "kind": "parse_error",
                    "message": str(exc),
                    "raw_response": response.content,
                }
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        observation=observation,
                    )
                )
                messages.append(
                    {
                        "role": "system",
                        "content": f"parse_error: {observation['message']}",
                    }
                )
                continue

            if action.type == "finish":
                observation = {"kind": "action_parsed", "action_type": action.type}
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation=observation,
                    )
                )
                return RunResult(
                    status="success",
                    final_message=str(action.arguments.get("message", "")),
                    steps=steps,
                )

            if self.guardrail_engine is not None:
                decision = self.guardrail_engine.check(action)
                if decision.status != "allowed":
                    observation = {
                        "kind": "guardrail_result",
                        "status": decision.status,
                        "reason": decision.reason,
                    }
                    steps.append(
                        LoopStep(
                            index=index,
                            llm_response=response.content,
                            action=action,
                            observation=observation,
                        )
                    )
                    return RunResult(
                        status=decision.status,
                        final_message=decision.reason,
                        steps=steps,
                    )

            if self.tool_registry is None:
                observation = {"kind": "action_parsed", "action_type": action.type}
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation=observation,
                    )
                )
                messages.append(
                    {
                        "role": "system",
                        "content": f"observation: parsed action {action.type}; tools are not connected yet",
                    }
                )
                continue

            tool_result = self.tool_registry.dispatch(action)
            if self.validator is not None and action.type == "run_command":
                observation = self.validator.validate(tool_result).to_observation()
            else:
                observation = tool_result.to_observation(action.type)
            steps.append(
                LoopStep(
                    index=index,
                    llm_response=response.content,
                    action=action,
                    observation=observation,
                )
            )
            messages.append(
                {
                    "role": "system",
                    "content": f"tool_result: {observation}",
                }
            )

        return RunResult(
            status="max_steps",
            final_message="Reached max steps without finish action.",
            steps=steps,
        )

    def _initial_messages(self, task: str) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": ACTION_PROTOCOL},
            {"role": "user", "content": task},
        ]
        if self.memory_store is None:
            return messages

        memory_context = self._build_memory_context(task)
        if not memory_context:
            return messages
        return [messages[0], {"role": "system", "content": memory_context}, *messages[1:]]

    def _build_memory_context(self, task: str) -> str:
        if self.memory_context_budget < len("memory_context:\n"):
            return ""

        lines = []
        used = len("memory_context:\n")
        for item in self.memory_store.retrieve(task):
            line = f"- {item.content}"
            projected = used + len(line) + 1
            if projected > self.memory_context_budget:
                continue
            lines.append(line)
            used = projected

        if not lines:
            return ""
        return "memory_context:\n" + "\n".join(lines)
