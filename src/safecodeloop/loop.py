from dataclasses import dataclass, field
from typing import Any

from safecodeloop.actions import Action, ActionParseError, parse_action
from safecodeloop.feedback import Validator
from safecodeloop.guardrails import GuardrailEngine
from safecodeloop.llm import LLMClient
from safecodeloop.tools import ToolRegistry


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
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.llm = llm
        self.max_steps = max_steps
        self.tool_registry = tool_registry
        self.guardrail_engine = guardrail_engine
        self.validator = validator

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
