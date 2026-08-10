from dataclasses import dataclass, field
from typing import Any

from safecodeloop.actions import Action, ActionParseError, parse_action
from safecodeloop.llm import LLMClient


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
    def __init__(self, llm: LLMClient, max_steps: int = 5):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.llm = llm
        self.max_steps = max_steps

    def run(self, task: str) -> RunResult:
        steps: list[LoopStep] = []
        messages = [{"role": "user", "content": task}]

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

            observation = {"kind": "action_parsed", "action_type": action.type}
            steps.append(
                LoopStep(
                    index=index,
                    llm_response=response.content,
                    action=action,
                    observation=observation,
                )
            )

            if action.type == "finish":
                return RunResult(
                    status="success",
                    final_message=str(action.arguments.get("message", "")),
                    steps=steps,
                )

            messages.append(
                {
                    "role": "system",
                    "content": f"observation: parsed action {action.type}; tools are not connected yet",
                }
            )

        return RunResult(
            status="max_steps",
            final_message="Reached max steps without finish action.",
            steps=steps,
        )
