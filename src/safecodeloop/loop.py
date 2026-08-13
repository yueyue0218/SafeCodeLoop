from dataclasses import dataclass, field
from typing import Any

from safecodeloop.actions import Action, ActionParseError, parse_action
from safecodeloop.approval import ApprovalError, ApprovalStore
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
- {"type":"run_validation","command":"test, lint, or typecheck command"}
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
    approval_id: str | None = None


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
        approval_store: ApprovalStore | None = None,
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
        self.approval_store = approval_store

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
                    approval_id = None
                    if decision.status == "needs_approval" and self.approval_store is not None:
                        approval_id = self.approval_store.create(action, decision.reason).id
                    observation = {
                        "kind": "guardrail_result",
                        "status": decision.status,
                        "reason": decision.reason,
                    }
                    if approval_id is not None:
                        observation["approval_id"] = approval_id
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
                        approval_id=approval_id,
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
            if self.validator is not None and action.type == "run_validation":
                feedback = self.validator.validate(tool_result)
                observation = feedback.to_observation()
                context_observation = self.validator.context_observation(feedback)
            else:
                observation = tool_result.to_observation(action.type)
                context_observation = observation
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
                    "content": f"tool_result: {context_observation}",
                }
            )

        return RunResult(
            status="max_steps",
            final_message="Reached max steps without finish action.",
            steps=steps,
        )

    def resume(self, approval_id: str, task: str) -> RunResult:
        if self.approval_store is None:
            raise ApprovalError("approval store is not configured")
        if self.tool_registry is None:
            raise ApprovalError("tools are not connected")

        record = self.approval_store.get(approval_id)
        self.approval_store.consume(approval_id, record.action)
        tool_result = self.tool_registry.dispatch(record.action)
        if self.validator is not None and record.action.type == "run_validation":
            feedback = self.validator.validate(tool_result)
            observation = feedback.to_observation()
            context_observation = self.validator.context_observation(feedback)
        else:
            observation = tool_result.to_observation(record.action.type)
            context_observation = observation

        messages = self._initial_messages(task)
        messages.append(
            {
                "role": "system",
                "content": f"approved_tool_result: {context_observation}",
            }
        )
        steps = [
            LoopStep(
                index=0,
                llm_response="[approved action resumed]",
                action=record.action,
                observation={
                    **observation,
                    "approval_id": approval_id,
                    "approval_status": "consumed",
                },
            )
        ]

        for index in range(1, self.max_steps + 1):
            response = self.llm.generate(messages)
            try:
                action = parse_action(response.content)
            except ActionParseError as exc:
                observation = {"kind": "parse_error", "message": str(exc)}
                steps.append(LoopStep(index=index, llm_response=response.content, observation=observation))
                messages.append({"role": "system", "content": f"parse_error: {exc}"})
                continue

            if action.type == "finish":
                steps.append(
                    LoopStep(
                        index=index,
                        llm_response=response.content,
                        action=action,
                        observation={"kind": "action_parsed", "action_type": "finish"},
                    )
                )
                return RunResult(
                    status="success",
                    final_message=str(action.arguments.get("message", "")),
                    steps=steps,
                )

            decision = self.guardrail_engine.check(action) if self.guardrail_engine else None
            if decision is not None and decision.status != "allowed":
                next_id = None
                if decision.status == "needs_approval":
                    next_id = self.approval_store.create(action, decision.reason).id
                guardrail_observation = {
                    "kind": "guardrail_result",
                    "status": decision.status,
                    "reason": decision.reason,
                }
                if next_id:
                    guardrail_observation["approval_id"] = next_id
                steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=guardrail_observation))
                return RunResult(decision.status, decision.reason, steps, approval_id=next_id)

            next_result = self.tool_registry.dispatch(action)
            if self.validator is not None and action.type == "run_validation":
                next_feedback = self.validator.validate(next_result)
                next_observation = next_feedback.to_observation()
                next_context_observation = self.validator.context_observation(next_feedback)
            else:
                next_observation = next_result.to_observation(action.type)
                next_context_observation = next_observation
            steps.append(LoopStep(index=index, llm_response=response.content, action=action, observation=next_observation))
            messages.append({"role": "system", "content": f"tool_result: {next_context_observation}"})

        return RunResult("max_steps", "Reached max steps without finish action.", steps)

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
